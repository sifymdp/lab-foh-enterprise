"""
Real-time Annotated MJPEG Stream Router
───────────────────────────────────────
Streams live CCTV camera frames with YOLO11 detection bounding boxes,
persistent ByteTrack IDs, table ROI seating zones, occupancy labels,
and live AI performance HUD.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core import camera_utils
from app.core.temporal_occupancy import temporal_tracker
from app.core.vision_engine import PersonTrack, TableZoneMatch, vision_engine
from app.database import SessionLocal, get_db
from app.models import Floor, Table
from app.models.vision import Camera, TableROI
from app.services.mismatch_service import mismatch_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stream"])

OUTPUT_FRAME_SIZE = (960, 540)
OUTPUT_FPS = 25
CONFIG_REFRESH_SECONDS = 1.5


@dataclass
class StreamWorkerState:
    floor_id: str
    camera_url: str
    frame: bytes | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    running: bool = False
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    config_signature: Any = None
    last_error: str | None = None
    latest_tracks: list[PersonTrack] = field(default_factory=list)
    latest_table_matches: dict[str, TableZoneMatch] = field(default_factory=dict)
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

    # 1. Draw Table ROIs
    if show_rois:
        for r in rois:
            b = r.get("bounds")
            if not b:
                continue
            ox = int(round(b["x"] * scale_x))
            oy = int(round(b["y"] * scale_y))
            ow = max(int(round(b["width"] * scale_x)), 1)
            oh = max(int(round(b["height"] * scale_y)), 1)

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
    cap = None
    last_refresh = 0.0
    cached_rois: list[dict[str, Any]] = []

    try:
        while not state.stop_event.is_set():
            now = time.time()
            if cap is None or now - last_refresh >= CONFIG_REFRESH_SECONDS:
                rois = _get_rois_for_floor(state.floor_id)
                sig = (state.camera_url, len(rois))
                if cap is None or sig != state.config_signature:
                    if cap is not None:
                        cap.release()
                    cap = cv2.VideoCapture(camera_utils.resolve_camera_source(state.camera_url))
                    state.config_signature = sig
                cached_rois = rois
                last_refresh = now

            if cap is None or not cap.isOpened():
                state.last_error = f"Camera source unavailable: {state.camera_url}"
                time.sleep(0.2)
                continue

            ret, raw_frame = cap.read()
            if not ret or raw_frame is None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                time.sleep(0.02)
                continue

            raw_h, raw_w = raw_frame.shape[:2]
            state.processed_frames += 1

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
    finally:
        if cap is not None:
            cap.release()
        state.running = False


def _ensure_stream_worker(floor_id: str, camera_url: str) -> StreamWorkerState:
    with _stream_workers_lock:
        state = _stream_workers.get(floor_id)
        if state is None:
            state = StreamWorkerState(floor_id=floor_id, camera_url=camera_url)
            _stream_workers[floor_id] = state

        if state.camera_url != camera_url and state.running:
            state.stop_event.set()
            if state.thread is not None:
                state.thread.join(timeout=1.5)
            state.running = False
            state.thread = None
            state.frame = None
            state.stop_event = threading.Event()
            state.config_signature = None

        state.camera_url = camera_url
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


def _generate(state: StreamWorkerState):
    frame_interval = 1.0 / OUTPUT_FPS
    while True:
        with state.lock:
            frame = state.frame

        if frame is None:
            time.sleep(0.04)
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        )
        time.sleep(frame_interval)


def stop_all_stream_workers() -> None:
    """Stops all background camera stream worker threads on shutdown."""
    with _stream_workers_lock:
        states = list(_stream_workers.values())
        _stream_workers.clear()
    for state in states:
        state.stop_event.set()
        if state.thread is not None:
            state.thread.join(timeout=1.5)


@router.get("/stream/{floor_id}")
def live_stream(
    floor_id: str,
    db: Session = Depends(get_db),
):
    tables = db.query(Table).filter(Table.floor_id == floor_id).all()
    camera_url = None
    for t in tables:
        if t.camera_url:
            camera_url = t.camera_url
            break
    if not camera_url:
        camera_url = settings.default_camera_url
    if not camera_url:
        raise HTTPException(404, "No camera configured for this floor")
    state = _ensure_stream_worker(floor_id, camera_url)
    return StreamingResponse(
        _generate(state),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

