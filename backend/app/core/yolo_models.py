"""Global YOLO model holder for table-state detection."""

from __future__ import annotations

import logging
import os
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from app.config import settings

if TYPE_CHECKING:
    from ultralytics import YOLO

logger = logging.getLogger(__name__)

EXPECTED_TABLE_STATE_CLASSES = {"clean", "dirty", "occupied"}

table_state_model: YOLO | None = None


@dataclass(frozen=True)
class TableStateDetection:
    label: str
    confidence: float


def _ensure_writable_ml_cache_dirs() -> None:
    base_dir = Path(tempfile.gettempdir()) / "foh_ml_cache"
    mpl_dir = base_dir / "matplotlib"
    yolo_dir = base_dir / "ultralytics"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    yolo_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir))
    os.environ.setdefault("YOLO_CONFIG_DIR", str(yolo_dir))


def _resolve_model_path(raw_path: str) -> str:
    path = Path(raw_path)
    if path.exists():
        return str(path)

    backend_dir = Path(__file__).resolve().parents[2]
    candidates = [
        backend_dir / raw_path,
        backend_dir.parent / raw_path,
        backend_dir / "models" / path.name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return raw_path


def load_models() -> bool:
    """Load the table-state YOLO model. Returns False if ML should stay disabled."""
    global table_state_model

    if not settings.camera_enabled:
        logger.info("Camera pipeline disabled (CAMERA_ENABLED=false)")
        return False

    _ensure_writable_ml_cache_dirs()

    try:
        from ultralytics import YOLO as YOLOClass
    except ImportError:
        logger.warning("ultralytics not installed — camera pipeline disabled")
        return False

    try:
        resolved_model_path = _resolve_model_path(settings.yolo_table_state_model_path)
        logger.info("Loading table-state detection model: %s", resolved_model_path)
        model = YOLOClass(resolved_model_path)
        names = {str(name).lower() for name in model.names.values()}
        missing = EXPECTED_TABLE_STATE_CLASSES - names
        if missing:
            logger.warning("Table-state YOLO model is missing expected classes: %s", sorted(missing))
        table_state_model = model
        return True
    except Exception:
        logger.exception("Failed to load table-state YOLO model — camera pipeline disabled")
        table_state_model = None
        return False


def unload_models() -> None:
    global table_state_model
    table_state_model = None


def is_table_state_model_ready() -> bool:
    return table_state_model is not None


def detect_table_state(frame: Any, threshold: float | None = None) -> TableStateDetection | None:
    """Run table-state inference and return the highest-confidence detection.

    ``None`` means no model box passed threshold; callers should treat that as
    clean for the ROI workflow.
    """
    if table_state_model is None:
        return None

    conf = threshold if threshold is not None else settings.table_state_confidence_threshold
    results = table_state_model(frame, verbose=False, conf=conf)
    if not results or not results[0].boxes:
        return None

    best = max(results[0].boxes, key=lambda box: float(box.conf))
    confidence = float(best.conf)
    label = str(table_state_model.names[int(best.cls)]).lower()
    if confidence < conf:
        return None
    return TableStateDetection(label=label, confidence=confidence)


def detect_table_states(
    frames: Sequence[Any],
    threshold: float | None = None,
) -> list[TableStateDetection | None]:
    """Run batched table-state inference for several ROIs at once."""
    if table_state_model is None:
        return [None for _ in frames]

    if not frames:
        return []

    conf = threshold if threshold is not None else settings.table_state_confidence_threshold
    results = table_state_model(list(frames), verbose=False, conf=conf)
    detections: list[TableStateDetection | None] = []
    for result in results:
        if not result.boxes:
            detections.append(None)
            continue
        best = max(result.boxes, key=lambda box: float(box.conf))
        confidence = float(best.conf)
        if confidence < conf:
            detections.append(None)
            continue
        label = str(table_state_model.names[int(best.cls)]).lower()
        detections.append(TableStateDetection(label=label, confidence=confidence))
    return detections


def smooth_table_state(
    detections: Sequence[TableStateDetection | None],
    treat_none_as_clean: bool = True,
) -> TableStateDetection | None:
    """Collapse several nearby frame detections into one stable label."""
    if not detections:
        return None

    grouped: dict[str, list[float]] = defaultdict(list)
    for detection in detections:
        if detection is None:
            if treat_none_as_clean:
                grouped["clean"].append(0.0)
            continue
        grouped[detection.label].append(detection.confidence)

    if not grouped:
        return None

    best_label = max(
        grouped.items(),
        key=lambda item: (len(item[1]), sum(item[1]) / max(len(item[1]), 1)),
    )[0]
    confidences = grouped[best_label]
    return TableStateDetection(
        label=best_label,
        confidence=sum(confidences) / len(confidences) if confidences else 0.0,
    )


def detect_table_state_consensus(
    frames: Sequence[Any],
    threshold: float | None = None,
) -> TableStateDetection | None:
    """Run table-state inference over several frames and return a stable result."""
    return smooth_table_state(
        [detect_table_state(frame, threshold=threshold) for frame in frames],
        treat_none_as_clean=True,
    )


def iter_full_frame_detections(frame: Any, threshold: float | None = None) -> list[tuple[int, int, int, int, TableStateDetection]]:
    """Return filtered full-frame boxes for demo streams before ROIs exist."""
    if table_state_model is None:
        return []

    conf = threshold if threshold is not None else settings.table_state_confidence_threshold
    results = table_state_model(frame, verbose=False, conf=conf)
    if not results or not results[0].boxes:
        return []

    detections: list[tuple[int, int, int, int, TableStateDetection]] = []
    for box in results[0].boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        width = max(x2 - x1, 1)
        height = max(y2 - y1, 1)
        if height / width > 1.5:
            continue
        y1 = y1 + int(height * 0.35)
        label = str(table_state_model.names[int(box.cls)]).lower()
        detections.append((x1, y1, x2, y2, TableStateDetection(label=label, confidence=float(box.conf))))
    return detections
