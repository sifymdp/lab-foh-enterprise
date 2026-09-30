"""
Real-time Annotated MJPEG Stream Router
───────────────────────────────────────
Streams live CCTV camera frames with YOLO11 detection bounding boxes,
persistent ByteTrack IDs, table ROI seating zones, occupancy labels,
and live AI performance HUD.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core import camera_utils
from app.core.temporal_occupancy import temporal_tracker
from app.core.vision_engine import PersonTrack, TableZoneMatch, vision_engine
from app.database import SessionLocal, get_db
from app.models import Floor, Table
from app.models.vision import Camera, TableROI
from app.services.mismatch_service import mismatch_service
from app.services.table_detector import table_detector
from app.services.video_sources import is_youtube_url, video_source_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stream"])

OUTPUT_FRAME_SIZE = (960, 540)
OUTPUT_FPS = 25
CONFIG_REFRESH_SECONDS = 1.5


@dataclass
class StreamWorkerState:
    floor_id: str
    camera_url: str
    source_type: str = "RTSP"
    frame: bytes | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    running: bool = False
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    config_signature: Any = None
    last_error: str | None = None
    latest_tracks: list[PersonTrack] = field(default_factory=list)
    latest_table_matches: dict[str, TableZoneMatch] = field(default_factory=dict)
    latest_candidate_tables: list[Any] = field(default_factory=list)
    processed_frames: int = 0
    inference_ms: float = 0.0
    fps: float = 0.0


_stream_workers: dict[str, StreamWorkerState] = {}
_stream_workers_lock = threading.Lock()


def _get_rois_for_floor(floor_id: str) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        tables = db.query(Table).filter(Table.floor_id == floor_id).all()
        rois: list[dict[str, Any]] = []
        for t in tables:
            bounds = camera_utils.parse_roi(t.roi_coords)
            if bounds:
                rois.append({
                    "table_id": t.id,
                    "table_number": str(t.number),
                    "capacity": t.capacity,
                    "status": t.status,
                    "bounds": bounds,
                    "camera_url": t.camera_url,
                })
        return rois
    finally:
        db.close()


def _draw_hud(frame: np.ndarray, state: StreamWorkerState) -> None:
    h, w = frame.shape[:2]
    # Dark translucent HUD pill in top-left
    hud_w, hud_h = 320, 60
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (10 + hud_w, 10 + hud_h), (15, 23, 42), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    cv2.rectangle(frame, (10, 10), (10 + hud_w, 10 + hud_h), (51, 65, 85), 1)

    # Text telemetry
    model_str = f"AI: {vision_engine.model_name} (ByteTrack)"
    perf_str = f"FPS: {state.fps:.1f} | Latency: {state.inference_ms:.1f}ms | People: {len(state.latest_tracks)}"
    cv2.putText(frame, model_str, (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (56, 189, 248), 1, cv2.LINE_AA)
    cv2.putText(frame, perf_str, (20, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (226, 232, 240), 1, cv2.LINE_AA)


def _make_standby_frame_bytes(camera_url: str, source_type: str, message: str = "Connecting to Camera Stream...") -> bytes:
    standby = np.full((OUTPUT_FRAME_SIZE[1], OUTPUT_FRAME_SIZE[0], 3), (15, 23, 42), dtype=np.uint8)
    for y in range(0, OUTPUT_FRAME_SIZE[1], 40):
        cv2.line(standby, (0, y), (OUTPUT_FRAME_SIZE[0], y), (22, 30, 48), 1)

    box_w, box_h = 580, 160
    bx = (OUTPUT_FRAME_SIZE[0] - box_w) // 2
    by = (OUTPUT_FRAME_SIZE[1] - box_h) // 2
    cv2.rectangle(standby, (bx, by), (bx + box_w, by + box_h), (20, 28, 45), -1)
    cv2.rectangle(standby, (bx, by), (bx + box_w, by + box_h), (56, 189, 248), 2)

    cv2.putText(standby, message, (bx + 28, by + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)
    url_disp = camera_url if len(camera_url) <= 45 else (camera_url[:42] + "...")
    cv2.putText(standby, f"Mode: {source_type}  |  Target: {url_disp}", (bx + 28, by + 90), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (148, 163, 184), 1, cv2.LINE_AA)
    cv2.putText(standby, "YOLO11 Vision Pipeline Engine Active", (bx + 28, by + 125), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (56, 189, 248), 1, cv2.LINE_AA)

    ok, buf = cv2.imencode(".jpg", standby, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes() if ok else b""


def _draw_stream_overlays(
    frame: np.ndarray,
    rois: list[dict[str, Any]],
    state: StreamWorkerState,
    raw_w: int,
    raw_h: int,
    show_boxes: bool = True,
    show_rois: bool = True,
) -> None:
    scale_x = OUTPUT_FRAME_SIZE[0] / max(raw_w, 1)
    scale_y = OUTPUT_FRAME_SIZE[1] / max(raw_h, 1)

    # 1. Draw Table ROIs or Candidate Table Detections
    # 1. Draw Table ROIs & Candidate Tables
    registered_bboxes: list[tuple[int, int, int, int]] = []
    if show_rois and rois:
        for r in rois:
            b = r.get("bounds")
            if not b:
                continue
            ox = int(round(b["x"] * scale_x))
            oy = int(round(b["y"] * scale_y))
            ow = max(int(round(b["width"] * scale_x)), 1)
            oh = max(int(round(b["height"] * scale_y)), 1)
            registered_bboxes.append((b["x"], b["y"], b["width"], b["height"]))

            tid = str(r["table_id"])
            match = state.latest_table_matches.get(tid)
            count = match.people_count if match else 0
            cap = r.get("capacity", 4)
            digital_status = r.get("status", "AVAILABLE")

            # Determine color based on occupancy and mismatch
            if count > 0:
                roi_color = (0, 0, 230) if count > cap else (0, 180, 240)  # Red / Orange
                label = f"T{r['table_number']} ({count}/{cap})"
            else:
                roi_color = (34, 197, 94) if digital_status == "AVAILABLE" else (148, 163, 184)
                label = f"T{r['table_number']} ({digital_status.capitalize()})"

            # ROI box
            cv2.rectangle(frame, (ox, oy), (ox + ow, oy + oh), roi_color, 2)
            # Label badge
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(frame, (ox, max(oy - th - 6, 0)), (ox + tw + 8, oy), roi_color, -1)
            cv2.putText(
                frame,
                label,
                (ox + 4, max(oy - 4, 12)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

    # Draw Candidate New Tables discovered by YOLO11 (shown in Blue per legend)
    if show_rois and state.latest_candidate_tables:
        for idx, cand in enumerate(state.latest_candidate_tables):
            bx, by, bw, bh = cand.bbox
            # Check if this candidate overlaps an existing registered table
            matched_reg = False
            for rx, ry, rw, rh in registered_bboxes:
                # Centroid distance or IoU
                if abs((bx + bw / 2) - (rx + rw / 2)) < max(bw, rw) * 0.55 and abs((by + bh / 2) - (ry + rh / 2)) < max(bh, rh) * 0.55:
                    matched_reg = True
                    break

            if matched_reg:
                continue

            ox = int(round(bx * scale_x))
            oy = int(round(by * scale_y))
            ow = max(int(round(bw * scale_x)), 1)
            oh = max(int(round(bh * scale_y)), 1)

            # Vibrant Blue for Candidate New Table (BGR: 235, 160, 30)
            roi_color = (235, 160, 30)
            label = f"Cand T{idx + 1} [{cand.shape}] {int(cand.confidence * 100)}%"
            cv2.rectangle(frame, (ox, oy), (ox + ow, oy + oh), roi_color, 2)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
            cv2.rectangle(frame, (ox, max(oy - th - 6, 0)), (ox + tw + 8, oy), roi_color, -1)
            cv2.putText(
                frame,
                label,
                (ox + 4, max(oy - 4, 12)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

    # 2. Draw Person Tracking Bounding Boxes
    if show_boxes:
        for trk in state.latest_tracks:
            x1, y1, x2, y2 = trk.bbox
            ox1 = int(round(x1 * scale_x))
            oy1 = int(round(y1 * scale_y))
            ox2 = int(round(x2 * scale_x))
            oy2 = int(round(y2 * scale_y))

            # Person Box
            cv2.rectangle(frame, (ox1, oy1), (ox2, oy2), (244, 114, 182), 2)  # Pinkish purple
            # Anchor point (feet)
            cx, cy = trk.bottom_center
            ocx = int(round(cx * scale_x))
            ocy = int(round(cy * scale_y))
            cv2.circle(frame, (ocx, ocy), 4, (59, 130, 246), -1)

            # Track Tag
            tag = f"#{trk.track_id} ({int(trk.confidence * 100)}%)" if trk.track_id >= 0 else f"Person ({int(trk.confidence * 100)}%)"
            (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
            cv2.rectangle(frame, (ox1, max(oy1 - th - 6, 0)), (ox1 + tw + 6, oy1), (244, 114, 182), -1)
            cv2.putText(
                frame,
                tag,
                (ox1 + 3, max(oy1 - 4, 12)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (15, 23, 42),
                1,
                cv2.LINE_AA,
            )

    # 3. Draw Telemetry HUD
    _draw_hud(frame, state)


def _stream_worker_loop(state: StreamWorkerState) -> None:
    source = None
    last_refresh = 0.0
    cached_rois: list[dict[str, Any]] = []

    try:
        while not state.stop_event.is_set():
            try:
                now = time.time()
                if source is None or now - last_refresh >= CONFIG_REFRESH_SECONDS:
                    rois = _get_rois_for_floor(state.floor_id)
                    sig = (state.camera_url, state.source_type, len(rois))
                    if source is None or sig != state.config_signature:
                        source = video_source_manager.get_or_create(
                            f"stream_{state.floor_id}", state.camera_url, state.source_type
                        )
                        state.config_signature = sig
                    cached_rois = rois
                    last_refresh = now

                if source is None:
                    time.sleep(0.1)
                    continue

                try:
                    ok, raw_frame = source.read_frame()
                except (cv2.error, Exception) as read_err:
                    logger.warning("Stream worker read_frame error for floor %s: %s", state.floor_id, read_err)
                    ok, raw_frame = False, None

                if not ok or raw_frame is None or getattr(raw_frame, "size", 0) == 0:
                    # Generate a clean standby frame with status indicator
                    standby = np.full((OUTPUT_FRAME_SIZE[1], OUTPUT_FRAME_SIZE[0], 3), (15, 23, 42), dtype=np.uint8)
                    cv2.putText(
                        standby,
                        "Connecting to Camera Stream...",
                        (180, 240),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (226, 232, 240),
                        2,
                        cv2.LINE_AA,
                    )
                    url_display = state.camera_url if len(state.camera_url) <= 50 else (state.camera_url[:47] + "...")
                    cv2.putText(
                        standby,
                        f"Source ({state.source_type}): {url_display}",
                        (180, 280),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (148, 163, 184),
                        1,
                        cv2.LINE_AA,
                    )
                    _draw_hud(standby, state)
                    s_ok, s_buf = cv2.imencode(".jpg", standby, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    if s_ok:
                        with state.lock:
                            state.frame = s_buf.tobytes()
                    time.sleep(0.08)
                    continue

                raw_h, raw_w = raw_frame.shape[:2]
                state.processed_frames += 1

                # Run candidate table detector periodically so live candidate boxes appear on the video feed
                if state.processed_frames % 20 == 1 or not state.latest_candidate_tables:
                    try:
                        cands = table_detector.detect_candidate_tables(raw_frame, min_confidence=0.10)
                        state.latest_candidate_tables = cands
                    except Exception as e:
                        logger.debug("Candidate table detection in stream error: %s", e)

                stride = max(settings.stream_inference_stride, 1)
                if state.processed_frames % stride == 0 or state.processed_frames == 1:
                    # Run YOLO11 + ByteTrack
                    res = vision_engine.process_frame(
                        raw_frame,
                        table_rois=cached_rois,
                        apply_privacy_blur=settings.cv_face_blur,
                    )
                    state.latest_tracks = res.tracks
                    state.latest_table_matches = res.table_matches
                    state.inference_ms = res.inference_time_ms
                    state.fps = res.fps

                    # Update temporal states for tables
                    for roi in cached_rois:
                        tid = str(roi["table_id"])
                        match = res.table_matches.get(tid)
                        cnt = match.people_count if match else 0
                        c = match.confidence if match else 0.0
                        ids = [t.track_id for t in match.matched_tracks] if match else []
                        temporal_tracker.update(tid, cnt, c, ids)

                output_frame = cv2.resize(raw_frame, OUTPUT_FRAME_SIZE)
                _draw_stream_overlays(output_frame, cached_rois, state, raw_w, raw_h)

                ok, buf = cv2.imencode(".jpg", output_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if not ok:
                    continue

                with state.lock:
                    state.frame = buf.tobytes()
                    state.last_error = None
                time.sleep(1.0 / OUTPUT_FPS)
            except Exception as loop_err:
                logger.warning("Recoverable error in stream worker loop for floor %s: %s", state.floor_id, loop_err)
                time.sleep(0.1)
    finally:
        state.running = False


def _ensure_stream_worker(floor_id: str, camera_url: str, source_type: str = "RTSP") -> StreamWorkerState:
    with _stream_workers_lock:
        state = _stream_workers.get(floor_id)
        if state is None:
            state = StreamWorkerState(
                floor_id=floor_id,
                camera_url=camera_url,
                source_type=source_type,
                frame=_make_standby_frame_bytes(camera_url, source_type, "Connecting to YOLO11 Stream..."),
            )
            _stream_workers[floor_id] = state

        if (state.camera_url != camera_url or state.source_type != source_type) and state.running:
            state.stop_event.set()
            if state.thread is not None:
                state.thread.join(timeout=1.5)
            state.running = False
            state.thread = None
            state.frame = _make_standby_frame_bytes(camera_url, source_type, f"Switching Mode to {source_type}...")
            state.stop_event = threading.Event()
            state.config_signature = None

        state.camera_url = camera_url
        state.source_type = source_type
        if state.frame is None:
            state.frame = _make_standby_frame_bytes(camera_url, source_type, "Connecting to Camera Stream...")

        if not state.running:
            state.stop_event.clear()
            state.running = True
            state.thread = threading.Thread(
                target=_stream_worker_loop,
                args=(state,),
                name=f"yolo11-stream-{floor_id}",
                daemon=True,
            )
            state.thread.start()
        return state


async def _generate(state: StreamWorkerState):
    frame_interval = 1.0 / OUTPUT_FPS
    try:
        while not state.stop_event.is_set():
            with state.lock:
                frame = state.frame

            if frame is None:
                await asyncio.sleep(0.04)
                continue

            chunk = (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(frame)).encode("ascii") + b"\r\n\r\n"
                + frame
                + b"\r\n"
            )
            yield chunk
            await asyncio.sleep(frame_interval)
    except (asyncio.CancelledError, GeneratorExit):
        # Client closed or refreshed page cleanly
        pass
    except Exception as e:
        logger.debug("Live stream client disconnected: %s", e)


def stop_all_stream_workers() -> None:
    """Stops all background camera stream worker threads on shutdown."""
    with _stream_workers_lock:
        states = list(_stream_workers.values())
        _stream_workers.clear()
    for state in states:
        try:
            state.stop_event.set()
            if state.thread is not None:
                state.thread.join(timeout=1.0)
        except Exception:
            pass  # Suppress errors during forced shutdown
    logger.info("All stream workers stopped (%d workers cleaned up)", len(states))


@router.get("/stream/{floor_id}")
async def live_stream(
    floor_id: str,
    request: Request,
    camera_id: str | None = None,
    stream_url: str | None = None,
    source_type: str | None = None,
    db: Session = Depends(get_db),
):
    camera_url = (stream_url or "").strip()
    effective_source_type = (source_type or "").upper()

    # 1. If explicit camera_id provided, look up camera
    if not camera_url and camera_id:
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if cam and cam.stream_url:
            camera_url = cam.stream_url
            if not effective_source_type and getattr(cam, "source_type", None):
                effective_source_type = cam.source_type

    # 2. Check camera configured for this floor
    if not camera_url:
        cam = db.query(Camera).filter(Camera.floor_id == floor_id).first()
        if cam and cam.stream_url:
            camera_url = cam.stream_url
            if not effective_source_type and getattr(cam, "source_type", None):
                effective_source_type = cam.source_type

    # 3. Check any table on this floor with camera_url
    if not camera_url:
        tables = db.query(Table).filter(Table.floor_id == floor_id).all()
        for t in tables:
            if t.camera_url:
                camera_url = t.camera_url
                break

    # 4. Check any camera in database
    if not camera_url:
        first_cam = db.query(Camera).first()
        if first_cam and first_cam.stream_url:
            camera_url = first_cam.stream_url
            if not effective_source_type and getattr(first_cam, "source_type", None):
                effective_source_type = first_cam.source_type

    # 5. Check default camera url in settings
    if not camera_url and settings.default_camera_url:
        camera_url = settings.default_camera_url

    # 6. Fallback to uploaded video sample or synthetic simulation
    if not camera_url:
        sample_path = Path("camera_uploads/table_t-1.mp4")
        if sample_path.exists():
            camera_url = str(sample_path)
            effective_source_type = "VIDEO_FILE"
        else:
            camera_url = "SYNTHETIC"
            effective_source_type = "SYNTHETIC"

    # Infer source_type if still blank
    if not effective_source_type or effective_source_type == "UNDEFINED":
        if is_youtube_url(camera_url):
            effective_source_type = "DEMO_STREAM"
        elif camera_url == "SYNTHETIC":
            effective_source_type = "SYNTHETIC"
        elif camera_url.isdigit() or camera_url in ("0", "1", "2"):
            effective_source_type = "WEBCAM"
        elif camera_url.endswith((".mp4", ".avi", ".mov", ".mkv")):
            effective_source_type = "VIDEO_FILE"
        else:
            effective_source_type = "RTSP"

    state = _ensure_stream_worker(floor_id, camera_url, effective_source_type)
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate, pre-check=0, post-check=0, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "*",
    }
    return StreamingResponse(
        _generate(state),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers=headers,
    )


@router.get("/stream/{floor_id}/frame")
async def stream_single_frame(
    floor_id: str,
    camera_id: str | None = None,
    stream_url: str | None = None,
    source_type: str | None = None,
    db: Session = Depends(get_db),
):
    """Returns the latest single JPEG frame from the floor camera stream."""
    camera_url = (stream_url or "").strip()
    effective_source_type = (source_type or "").upper()

    if not camera_url and camera_id:
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if cam and cam.stream_url:
            camera_url = cam.stream_url
            if not effective_source_type and getattr(cam, "source_type", None):
                effective_source_type = cam.source_type

    if not camera_url:
        cam = db.query(Camera).filter(Camera.floor_id == floor_id).first()
        if cam and cam.stream_url:
            camera_url = cam.stream_url
            if not effective_source_type and getattr(cam, "source_type", None):
                effective_source_type = cam.source_type

    if not camera_url:
        sample_path = Path("camera_uploads/table_t-1.mp4")
        if sample_path.exists():
            camera_url = str(sample_path)
            effective_source_type = "VIDEO_FILE"
        else:
            camera_url = "SYNTHETIC"
            effective_source_type = "SYNTHETIC"

    if not effective_source_type or effective_source_type == "UNDEFINED":
        if camera_url.endswith((".mp4", ".avi", ".mov", ".mkv")):
            effective_source_type = "VIDEO_FILE"
        else:
            effective_source_type = "RTSP"

    state = _ensure_stream_worker(floor_id, camera_url, effective_source_type)
    with state.lock:
        frame = state.frame

    if frame is None:
        frame = _make_standby_frame_bytes(camera_url, effective_source_type)

    return Response(
        content=frame,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Access-Control-Allow-Origin": "*",
        },
    )

