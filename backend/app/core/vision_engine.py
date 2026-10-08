"""
YOLO11 & ByteTrack Computer Vision Engine
──────────────────────────────────────────
Detects people on the restaurant floor using YOLO11 and tracks them persistently
across video frames using ByteTrack. Associates detected people with table ROIs
using the bottom-center anchor point (feet/seating ground-truth location).

- CPU / GPU fallback (auto-detects CUDA)
- Configurable model path (yolo11n.pt / yolo11m.pt / custom fine-tuned weights)
- Native ByteTrack multi-object tracking (lapx)
- Point-in-polygon and bounding-box ROI matching
- Optional face/head blurring for privacy compliance
- Telemetry: inference latency, tracking count, and FPS
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PersonTrack:
    track_id: int
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    bottom_center: tuple[int, int]   # (cx, cy)
    class_name: str = "person"


@dataclass
class TableZoneMatch:
    table_id: str
    table_number: str
    matched_tracks: list[PersonTrack] = field(default_factory=list)
    people_count: int = 0
    confidence: float = 0.0


@dataclass
class FrameQuality:
    brightness: float          # 0-255 mean pixel intensity
    contrast: float            # standard deviation of gray channel
    blur_score: float          # Laplacian variance
    is_blurred: bool           # blur_score < 55
    is_low_light: bool         # brightness < 45
    is_low_contrast: bool      # contrast < 25
    quality_status: str        # GOOD | LOW_LIGHT | BLURRED | LOW_CONTRAST
    quality_score: float       # normalized 0.0 - 1.0


def assess_frame_quality(frame: np.ndarray) -> FrameQuality:
    if frame is None or frame.size == 0:
        return FrameQuality(0.0, 0.0, 0.0, True, True, True, "OFFLINE", 0.0)

    try:
        small = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_NEAREST)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        mean_b = float(np.mean(gray))
        std_c = float(np.std(gray))
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        is_low_light = mean_b < 45.0
        is_low_contrast = std_c < 25.0
        is_blur = lap_var < 55.0

        b_score = min(1.0, mean_b / 100.0) if mean_b < 100 else max(0.0, 1.0 - (mean_b - 200) / 55.0)
        c_score = min(1.0, std_c / 50.0)
        blur_score_norm = min(1.0, lap_var / 150.0)
        overall_score = round(float(0.35 * b_score + 0.35 * c_score + 0.30 * blur_score_norm), 2)

        status = "GOOD"
        if is_low_light:
            status = "LOW_LIGHT"
        elif is_blur:
            status = "BLURRED"
        elif is_low_contrast:
            status = "LOW_CONTRAST"

        return FrameQuality(
            brightness=round(mean_b, 1),
            contrast=round(std_c, 1),
            blur_score=round(lap_var, 1),
            is_blurred=is_blur,
            is_low_light=is_low_light,
            is_low_contrast=is_low_contrast,
            quality_status=status,
            quality_score=overall_score,
        )
    except Exception:
        return FrameQuality(128.0, 50.0, 100.0, False, False, False, "GOOD", 0.85)


def enhance_low_light(frame: np.ndarray) -> np.ndarray:
    """
    Lightweight CLAHE enhancement on luminance channel.
    Only executed when frame brightness is low (< 45).
    """
    if frame is None or frame.size == 0:
        return frame
    try:
        ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        ycrcb[:, :, 0] = clahe.apply(ycrcb[:, :, 0])
        return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)
    except Exception:
        return frame


@dataclass
class VisionFrameResult:
    tracks: list[PersonTrack]
    table_matches: dict[str, TableZoneMatch]  # table_id -> TableZoneMatch
    inference_time_ms: float
    fps: float
    total_people_detected: int
    total_people_tracked: int
    quality: FrameQuality = field(default_factory=lambda: FrameQuality(128.0, 50.0, 100.0, False, False, False, "GOOD", 0.85))


class VisionEngine:
    _instance: VisionEngine | None = None

    def __init__(self) -> None:
        self.model: Any | None = None
        self.device: str = "cpu"
        self._is_ready: bool = False
        self._last_inference_time: float = 0.0
        self._fps_history: list[float] = []
        self._model_path: str = ""
        self._tracker: str = getattr(settings, "cv_tracker", "bytetrack.yaml") or "bytetrack.yaml"
        self._init_engine()

    @classmethod
    def get_instance(cls) -> VisionEngine:
        if cls._instance is None:
            cls._instance = VisionEngine()
        return cls._instance

    def _ensure_writable_cache(self) -> None:
        base_dir = Path(tempfile.gettempdir()) / "foh_ml_cache"
        yolo_dir = base_dir / "ultralytics"
        yolo_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("YOLO_CONFIG_DIR", str(yolo_dir))

    def _resolve_model_path(self, raw_path: str) -> str:
        path = Path(raw_path)
        if path.exists():
            return str(path)

        backend_dir = Path(__file__).resolve().parents[2]
        candidates = [
            backend_dir / raw_path,
            backend_dir.parent / raw_path,
            backend_dir / "models" / path.name,
            backend_dir / path.name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return raw_path

    def _init_engine(self) -> None:
        if not settings.camera_enabled:
            logger.info("Camera pipeline disabled in settings")
            return

        self._ensure_writable_cache()

        try:
            import torch
            from ultralytics import YOLO
        except ImportError:
            logger.warning("ultralytics or torch not installed — computer vision engine unavailable")
            return

        try:
            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
            model_target = self._resolve_model_path(settings.cv_model_name)
            logger.info("Initializing YOLO11 model '%s' on %s", model_target, self.device.upper())
            self.model = YOLO(model_target)
            self._model_path = model_target
            self._is_ready = True
            logger.info("YOLO11 Vision Engine initialized successfully")
        except Exception:
            logger.exception("Failed to initialize YOLO11 vision model")
            self.model = None
            self._is_ready = False

    @property
    def is_ready(self) -> bool:
        return self._is_ready and self.model is not None

    @property
    def model_name(self) -> str:
        return Path(self._model_path).name if self._model_path else "YOLO11"

    @property
    def current_fps(self) -> float:
        if not self._fps_history:
            return 0.0
        return round(sum(self._fps_history) / len(self._fps_history), 1)

    def reload_model(self, model_name: str | None = None) -> bool:
        if model_name:
            settings.cv_model_name = model_name
        self._init_engine()
        return self.is_ready

    def point_in_roi(self, point: tuple[int, int], roi: dict[str, Any]) -> bool:
        """
        Tests if an anchor point (px, py) lies inside a Table ROI polygon or rectangle.
        Supports both rectangular bounds {"x", "y", "width", "height"} and
        arbitrary polygons [{"x":..,"y":..}, ...].
        """
        px, py = point

        # 1. Polygon check
        polygon = roi.get("polygon") or roi.get("polygon_points")
        if polygon:
            if isinstance(polygon, str):
                try:
                    polygon = json.loads(polygon)
                except Exception:
                    polygon = None
            if isinstance(polygon, list) and len(polygon) >= 3:
                pts = np.array([[int(pt["x"]), int(pt["y"])] for pt in polygon], dtype=np.int32)
                # cv2.pointPolygonTest: returns >= 0 if inside or on edge
                return cv2.pointPolygonTest(pts, (float(px), float(py)), False) >= 0

        # 2. Rectangle bounding box check
        bounds = roi.get("bounds") or roi
        if isinstance(bounds, str):
            try:
                bounds = json.loads(bounds)
            except Exception:
                bounds = None

        if isinstance(bounds, dict) and "x" in bounds and "y" in bounds:
            rx = int(bounds["x"])
            ry = int(bounds["y"])
            rw = int(bounds.get("width", 0))
            rh = int(bounds.get("height", 0))
            return rx <= px <= rx + rw and ry <= py <= ry + rh

        return False

    def process_frame(
        self,
        frame: np.ndarray,
        table_rois: list[dict[str, Any]] | None = None,
        apply_privacy_blur: bool = False,
    ) -> VisionFrameResult:
        """
        Executes YOLO11 person detection + ByteTrack tracking on a raw frame,
        associates detected people with table ROIs, and returns structured result.
        """
        start_time = time.perf_counter()

        if not self.is_ready or frame is None or frame.size == 0:
            return VisionFrameResult(
                tracks=[],
                table_matches={},
                inference_time_ms=0.0,
                fps=0.0,
                total_people_detected=0,
                total_people_tracked=0,
                quality=assess_frame_quality(frame),
            )

        # 1. Evaluate image quality (blur, low light, contrast)
        quality = assess_frame_quality(frame)
        if quality.is_low_light:
            frame = enhance_low_light(frame)

        # 2. Run YOLO11 tracking (classes=[0] is 'person' in COCO dataset)
        try:
            tracker_file = self._tracker or settings.cv_tracker or "bytetrack.yaml"
            results = self.model.track(
                frame,
                persist=True,
                tracker=tracker_file,
                conf=settings.cv_confidence_threshold,
                classes=[0],
                imgsz=settings.cv_img_size,
                verbose=False,
                device=self.device,
            )
        except Exception:
            logger.exception("Inference error in YOLO11 tracking")
            return VisionFrameResult(
                tracks=[],
                table_matches={},
                inference_time_ms=0.0,
                fps=0.0,
                total_people_detected=0,
                total_people_tracked=0,
                quality=quality,
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        fps = 1000.0 / max(elapsed_ms, 1.0)
        self._fps_history.append(fps)
        if len(self._fps_history) > 30:
            self._fps_history.pop(0)

        tracks: list[PersonTrack] = []
        if results and results[0].boxes:
            for box in results[0].boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                track_id = int(box.id[0]) if box.id is not None else -1

                # Bottom-center point represents person's feet / physical table contact point
                cx = int((x1 + x2) / 2)
                cy = int(y2)

                track = PersonTrack(
                    track_id=track_id,
                    bbox=(x1, y1, x2, y2),
                    confidence=conf,
                    bottom_center=(cx, cy),
                )
                tracks.append(track)

                # Optional privacy face/head blur (top 25% of person box)
                if apply_privacy_blur or settings.cv_face_blur:
                    head_h = max(int((y2 - y1) * 0.25), 10)
                    head_y2 = min(y1 + head_h, y2)
                    head_roi = frame[max(0, y1) : head_y2, max(0, x1) : max(0, x2)]
                    if head_roi.size > 0:
                        blurred = cv2.GaussianBlur(head_roi, (25, 25), 30)
                        frame[max(0, y1) : head_y2, max(0, x1) : max(0, x2)] = blurred

        # Associate tracks with table ROIs
        table_matches: dict[str, TableZoneMatch] = {}
        if table_rois:
            for r in table_rois:
                tid = str(r["table_id"])
                tnum = str(r.get("table_number", tid))
                match = TableZoneMatch(table_id=tid, table_number=tnum)

                for trk in tracks:
                    if self.point_in_roi(trk.bottom_center, r):
                        match.matched_tracks.append(trk)

                match.people_count = len(match.matched_tracks)
                if match.matched_tracks:
                    match.confidence = sum(t.confidence for t in match.matched_tracks) / len(match.matched_tracks)
                else:
                    match.confidence = 0.0

                table_matches[tid] = match

        return VisionFrameResult(
            tracks=tracks,
            table_matches=table_matches,
            inference_time_ms=round(elapsed_ms, 1),
            fps=round(fps, 1),
            total_people_detected=len(tracks),
            total_people_tracked=len([t for t in tracks if t.track_id >= 0]),
            quality=quality,
        )

    def set_tracker(self, tracker_name: str) -> None:
        """Sets tracking algorithm: 'bytetrack' or 'botsort'"""
        if "botsort" in tracker_name.lower():
            self._tracker = "botsort.yaml"
        else:
            self._tracker = "bytetrack.yaml"
        logger.info("VisionEngine tracker updated to %s", self._tracker)

    def get_tracker(self) -> str:
        return self._tracker


vision_engine = VisionEngine.get_instance()
