"""Match full-frame YOLO detections to per-table ROI rectangles.

Detections and saved roi_coords both live in raw-camera-resolution space, so
the overlap comparison needs no coordinate conversion.
"""

from __future__ import annotations

from app.config import settings
from app.core.yolo_models import TableStateDetection


def iou_over_roi(box: tuple[int, int, int, int], roi: dict[str, int]) -> float:
    """Fraction of the ROI rectangle covered by the detection box.

    Detection boxes are often much larger than a table's ROI (e.g. spanning
    seated guests), so plain IoU would punish valid matches — coverage of the
    table zone is what matters.
    """
    x1, y1, x2, y2 = box
    rx, ry, rw, rh = roi["x"], roi["y"], roi["width"], roi["height"]
    ix1, iy1 = max(x1, rx), max(y1, ry)
    ix2, iy2 = min(x2, rx + rw), min(y2, ry + rh)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    intersection = iw * ih
    roi_area = max(rw * rh, 1)
    return intersection / roi_area


def match_detection_for_roi(
    detections: list[tuple[int, int, int, int, TableStateDetection]],
    roi: dict[str, int],
    min_overlap: float | None = None,
) -> TableStateDetection | None:
    """Return the detection that best covers the ROI, or None if none covers
    at least ``min_overlap`` of it."""
    threshold = min_overlap if min_overlap is not None else settings.stream_roi_match_min_overlap
    best_score = 0.0
    best_detection: TableStateDetection | None = None
    for x1, y1, x2, y2, detection in detections:
        score = iou_over_roi((x1, y1, x2, y2), roi)
        if score > best_score:
            best_score = score
            best_detection = detection
    if best_score < threshold:
        return None
    return best_detection
