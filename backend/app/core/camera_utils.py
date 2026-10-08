"""OpenCV helpers for frame capture and ROI cropping."""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

CAMERA_UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "camera_uploads"

# Shared latest annotated frame for MJPEG stream (BGR numpy array)
latest_stream_frame: np.ndarray | None = None


def parse_roi(roi_coords: str | None) -> dict[str, int] | None:
    if not roi_coords:
        return None
    try:
        data = json.loads(roi_coords)
        return {
            "x": int(data["x"]),
            "y": int(data["y"]),
            "width": int(data["width"]),
            "height": int(data["height"]),
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def crop_roi(frame: np.ndarray, roi: dict[str, int]) -> np.ndarray | None:
    h_frame, w_frame = frame.shape[:2]
    x = max(0, min(roi["x"], w_frame - 1))
    y = max(0, min(roi["y"], h_frame - 1))
    w = min(roi["width"], w_frame - x)
    h = min(roi["height"], h_frame - y)
    if w <= 0 or h <= 0:
        return None
    return frame[y : y + h, x : x + w]


def resolve_camera_source(camera_url: str) -> str:
    path = Path(camera_url)
    if path.exists():
        return str(path)

    candidates: list[Path] = []
    if path.name:
        candidates.append(CAMERA_UPLOADS_DIR / path.name)
    if settings.default_camera_url:
        default_name = Path(settings.default_camera_url).name
        if default_name:
            candidates.append(CAMERA_UPLOADS_DIR / default_name)
    candidates.extend(sorted(CAMERA_UPLOADS_DIR.glob("*.mp4")))

    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate)

    return camera_url


def capture_frame(camera_url: str) -> np.ndarray | None:
    cap = cv2.VideoCapture(resolve_camera_source(camera_url))
    if not cap.isOpened():
        logger.warning("Could not open camera: %s", camera_url)
        return None
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        logger.warning("Failed to read frame from: %s", camera_url)
        return None
    return frame


# Captures are held open between scan ticks, keyed by resolved source.
# Reopening a file source every tick would rewind it to frame 0, so the
# pipeline would judge the same opening moment forever and table status would
# never advance. Keeping the handle open lets playback move through the
# recording tick by tick, the way a live camera would.
_capture_cache: dict[str, cv2.VideoCapture] = {}
# Wall-clock moment each recording "started playing", so a file can be
# positioned by elapsed real time instead of by how many frames the pipeline
# happened to consume.
_playback_started: dict[str, float] = {}
_capture_lock = threading.Lock()


def _get_capture(source: str) -> cv2.VideoCapture | None:
    cap = _capture_cache.get(source)
    if cap is not None:
        if cap.isOpened():
            return cap
        cap.release()
        _capture_cache.pop(source, None)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        cap.release()
        return None
    _capture_cache[source] = cap
    return cap


def release_captures() -> None:
    """Close cached captures (called on shutdown)."""
    with _capture_lock:
        for cap in _capture_cache.values():
            cap.release()
        _capture_cache.clear()
        _playback_started.clear()


def _seek_to_wall_clock(cap: cv2.VideoCapture, source: str) -> None:
    """Position a recorded source at the point matching elapsed real time.

    Sampling a handful of frames per tick would crawl through a recording far
    slower than real time — an 8-minute video would take hours to play out, so
    table states would barely change during a demo. Seeking by wall clock makes
    a file behave like a live camera, looping when it reaches the end. Live
    streams (no frame count) are left alone; they are already realtime.
    """
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if total <= 0 or fps <= 0:
        return

    started = _playback_started.get(source)
    now = time.monotonic()
    if started is None:
        _playback_started[source] = now
        return

    target = int((now - started) * fps) % int(total)
    cap.set(cv2.CAP_PROP_POS_FRAMES, target)


def capture_frame_sequence(
    camera_url: str,
    sample_frames: int,
    frame_stride: int = 1,
) -> list[np.ndarray]:
    """Capture a short sequence of frames for temporal smoothing.

    Playback continues from where the previous call left off and loops at the
    end of a recording, so successive scan ticks see the footage progress.
    Empty results mean the source could not provide any readable frames.
    """
    source = resolve_camera_source(camera_url)
    frames: list[np.ndarray] = []
    stride = max(frame_stride, 1)

    with _capture_lock:
        cap = _get_capture(source)
        if cap is None:
            logger.warning("Could not open camera for sequence capture: %s", camera_url)
            return []

        _seek_to_wall_clock(cap, source)

        rewound = False
        while len(frames) < max(sample_frames, 1):
            ok, frame = cap.read()
            if not ok or frame is None:
                if rewound:
                    break  # looped once already and still no frames — give up
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                rewound = True
                continue
            frames.append(frame)
            for _ in range(stride - 1):
                if not cap.grab():
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    break

    return frames


def set_stream_frame(frame: np.ndarray) -> None:
    global latest_stream_frame
    latest_stream_frame = frame


def encode_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return buf.tobytes()


def draw_table_overlay(
    frame: np.ndarray,
    roi: dict[str, int],
    table_number: str,
    label: str,
    color_bgr: tuple[int, int, int],
    sub_label: str | None = None,
) -> None:
    x, y, w, h = roi["x"], roi["y"], roi["width"], roi["height"]
    cv2.rectangle(frame, (x, y), (x + w, y + h), color_bgr, 2)
    cv2.putText(
        frame,
        f"T{table_number}",
        (x, max(y - 8, 16)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        color_bgr,
        2,
    )
    cv2.putText(
        frame,
        label,
        (x + 4, y + 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        color_bgr,
        1,
    )
    if sub_label:
        cv2.putText(
            frame,
            sub_label,
            (x + 4, y + h - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color_bgr,
            1,
        )


STATUS_COLORS: dict[str, tuple[int, int, int]] = {
    "AVAILABLE": (0, 200, 0),      # green
    "SEATED": (0, 0, 220),         # red
    "ACTIVE": (0, 0, 220),         # red — Occupied
    "RESERVED": (0, 140, 255),     # orange
    "BILLING": (180, 0, 180),      # purple
    "CLEANING": (0, 140, 255),     # orange
    "PAID": (200, 180, 0),         # teal-ish
}


def status_label(status: str, dirty: bool = False) -> str:
    if status == "AVAILABLE":
        return "Available"
    if status in ("SEATED", "ACTIVE"):
        return "Occupied"
    if status == "RESERVED":
        return "Reserved"
    if status == "BILLING":
        return "Billing"
    if status == "CLEANING":
        return "Dirty" if dirty else "Cleaning"
    if status == "PAID":
        return "Paid"
    return status
