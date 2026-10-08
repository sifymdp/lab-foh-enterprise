from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.config import settings
from app.core.camera_utils import resolve_camera_source
from app.schemas.floor import RectBounds

logger = logging.getLogger(__name__)

_table_model: Any | None = None


def _load_table_model() -> Any | None:
    global _table_model
    if _table_model is not None:
        return _table_model

    model_path = getattr(settings, "yolo_table_model_path", "").strip()
    if not model_path:
        return None

    path = Path(model_path)
    if not path.exists():
        logger.warning("Table model path does not exist: %s", path)
        return None

    try:
        from ultralytics import YOLO as YOLOClass
    except ImportError:
        logger.warning("ultralytics not installed — table auto-detect will use contour fallback")
        return None

    try:
        logger.info("Loading table detection model: %s", path)
        _table_model = YOLOClass(str(path))
    except Exception:
        logger.exception("Failed to load table detection model: %s", path)
        _table_model = None
    return _table_model


def _clamp_rect(rect: dict[str, float], width: int, height: int) -> RectBounds | None:
    x = max(0, min(int(round(rect["x"])), width - 1))
    y = max(0, min(int(round(rect["y"])), height - 1))
    w = max(1, min(int(round(rect["width"])), width - x))
    h = max(1, min(int(round(rect["height"])), height - y))
    if w < 24 or h < 24:
        return None
    return RectBounds(x=x, y=y, width=w, height=h)


def _expand_rect(
    rect: RectBounds,
    frame_width: int,
    frame_height: int,
    x_ratio: float = 0.9,
    y_ratio: float = 1.05,
) -> RectBounds | None:
    pad_x = max(72, int(round(rect.width * x_ratio)))
    pad_y = max(64, int(round(rect.height * y_ratio)))
    return _clamp_rect(
        {
            "x": rect.x - pad_x,
            "y": rect.y - pad_y,
            "width": rect.width + pad_x * 2,
            "height": rect.height + pad_y * 2,
        },
        frame_width,
        frame_height,
    )


def _is_reasonable_table_rect(rect: RectBounds, frame_width: int, frame_height: int) -> bool:
    frame_area = frame_width * frame_height
    area = rect.width * rect.height
    if area <= 0:
        return False
    if area > frame_area * 0.38:
        return False
    if rect.width > frame_width * 0.82 or rect.height > frame_height * 0.82:
        return False
    if rect.y < frame_height * 0.06:
        return False
    if rect.x <= 4 and rect.y <= 4:
        return False
    if rect.x + rect.width >= frame_width - 4 and rect.y + rect.height >= frame_height - 4:
        return False
    return True


def _dedupe_rects(rects: list[tuple[float, RectBounds]], iou_threshold: float = 0.35) -> list[RectBounds]:
    def iou(a: RectBounds, b: RectBounds) -> float:
        ax2 = a.x + a.width
        ay2 = a.y + a.height
        bx2 = b.x + b.width
        by2 = b.y + b.height
        inter_x1 = max(a.x, b.x)
        inter_y1 = max(a.y, b.y)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0
        inter = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        union = a.width * a.height + b.width * b.height - inter
        return inter / union if union else 0.0

    selected: list[RectBounds] = []
    for _, rect in sorted(rects, key=lambda item: item[0], reverse=True):
        if all(iou(rect, existing) < iou_threshold for existing in selected):
            selected.append(rect)
    return selected


def _sample_frames(camera_url: str, max_frames: int = 30) -> tuple[list[np.ndarray], tuple[int, int]]:
    cap = cv2.VideoCapture(resolve_camera_source(camera_url))
    if not cap.isOpened():
        raise ValueError(f"Could not open camera/video source: {camera_url}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    frames: list[np.ndarray] = []
    try:
        if total_frames > 0:
            indices = np.linspace(0, max(total_frames - 1, 0), num=min(max_frames, total_frames), dtype=int)
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                ok, frame = cap.read()
                if ok and frame is not None:
                    frames.append(frame)
        else:
            for _ in range(max_frames):
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                frames.append(frame)
    finally:
        cap.release()

    if not frames:
        raise ValueError("No frames could be sampled from the camera source")

    if width <= 0 or height <= 0:
        height, width = frames[0].shape[:2]

    return frames, (width, height)


def _median_frame(frames: list[np.ndarray], size: tuple[int, int]) -> np.ndarray:
    width, height = size
    normalized = [cv2.resize(frame, (width, height)) for frame in frames]
    stack = np.stack(normalized, axis=0)
    return np.median(stack, axis=0).astype(np.uint8)


def _detect_with_yolo(frame: np.ndarray) -> list[tuple[float, RectBounds]]:
    model = _load_table_model()
    if model is None:
        return []

    try:
        results = model(frame, verbose=False)
    except Exception:
        logger.exception("YOLO table detection failed")
        return []

    if not results or not results[0].boxes:
        return []

    rects: list[tuple[float, RectBounds]] = []
    names = getattr(model, "names", {}) or {}
    frame_h, frame_w = frame.shape[:2]
    for box in results[0].boxes:
        class_name = str(names.get(int(box.cls), "")).lower()
        if class_name and "table" not in class_name and "desk" not in class_name and "bench" not in class_name:
            continue
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        rect = _clamp_rect(
            {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
            frame_w,
            frame_h,
        )
        if rect is None:
            continue
        expanded = _expand_rect(rect, frame_w, frame_h, x_ratio=0.18, y_ratio=0.18)
        rects.append((float(box.conf), expanded or rect))
    return rects


def _detect_with_table_tops(frame: np.ndarray) -> list[tuple[float, RectBounds]]:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frame_h, frame_w = frame.shape[:2]
    frame_area = float(frame_h * frame_w)
    border_margin = max(8, int(min(frame_w, frame_h) * 0.015))

    # Table tops in this CCTV footage are mostly low-saturation, darker
    # rectangles. This mask avoids the green camera tint and moving people.
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    sat_limit = int(np.percentile(saturation, 58))
    val_limit = int(np.percentile(value, 62))
    mask = cv2.inRange(saturation, 0, max(45, sat_limit))
    mask = cv2.bitwise_and(mask, cv2.inRange(value, 25, max(85, val_limit)))
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[float, RectBounds]] = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < frame_area * 0.003 or area > frame_area * 0.18:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if (
            x <= border_margin
            or y <= border_margin
            or x + w >= frame_w - border_margin
            or y + h >= frame_h - border_margin
        ):
            continue
        aspect = w / float(h)
        if not (0.75 <= aspect <= 4.2):
            continue

        rect_area = float(w * h)
        fill_ratio = area / rect_area
        if fill_ratio < 0.38:
            continue

        approx = cv2.approxPolyDP(contour, 0.035 * cv2.arcLength(contour, True), True)
        if len(approx) > 8:
            continue

        rect = _clamp_rect({"x": x, "y": y, "width": w, "height": h}, frame_w, frame_h)
        expanded = _expand_rect(rect, frame_w, frame_h) if rect is not None else None
        if expanded is None or not _is_reasonable_table_rect(expanded, frame_w, frame_h):
            continue

        mean_inside = cv2.mean(gray, mask=cv2.drawContours(np.zeros_like(gray), [contour], -1, 255, -1))[0]
        score = float(area * fill_ratio * (1.0 + max(0.0, (float(np.mean(gray)) - mean_inside) / 255.0)))
        candidates.append((score, expanded))

    return candidates


def _detect_with_contours(frame: np.ndarray) -> list[tuple[float, RectBounds]]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 45, 135)
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    frame_h, frame_w = frame.shape[:2]
    frame_area = float(frame_h * frame_w)
    border_margin = max(8, int(min(frame_w, frame_h) * 0.02))
    candidates: list[tuple[float, RectBounds]] = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < frame_area * 0.008 or area > frame_area * 0.35:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w < 32 or h < 32:
            continue
        if (
            x <= border_margin
            or y <= border_margin
            or x + w >= frame_w - border_margin
            or y + h >= frame_h - border_margin
        ):
            continue
        fill_ratio = area / float(w * h)
        aspect = w / float(h)
        if fill_ratio < 0.35 or not (0.45 <= aspect <= 4.5):
            continue
        rect = cv2.minAreaRect(contour)
        rect_area = float(rect[1][0] * rect[1][1]) or 1.0
        rect_fill = area / rect_area
        if rect_fill < 0.45:
            continue
        approx = cv2.approxPolyDP(contour, 0.03 * cv2.arcLength(contour, True), True)
        polygon_bonus = 1.25 if len(approx) in (4, 5) else 1.0
        if len(approx) > 8:
            continue
        mean_inside = cv2.mean(gray, mask=cv2.drawContours(np.zeros_like(gray), [contour], -1, 255, -1))[0]
        mean_frame = float(np.mean(gray))
        dark_bonus = 1.0 + max(0.0, (mean_frame - mean_inside) / 255.0)
        score = float(area * fill_ratio * rect_fill * polygon_bonus * dark_bonus)
        rect = _clamp_rect({"x": x, "y": y, "width": w, "height": h}, frame_w, frame_h)
        expanded = _expand_rect(rect, frame_w, frame_h, x_ratio=0.2, y_ratio=0.25) if rect is not None else None
        if expanded is not None and _is_reasonable_table_rect(expanded, frame_w, frame_h):
            candidates.append((score, expanded))

    if not candidates:
        # As a last resort, try the most interior dark blob. If nothing useful
        # appears, return no candidates so the UI can keep the ROI manual.
        mask = cv2.inRange(gray, 0, int(np.median(gray) * 0.85))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        fallback_contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in fallback_contours:
            area = cv2.contourArea(contour)
            if area < frame_area * 0.01 or area > frame_area * 0.25:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if x <= border_margin or y <= border_margin or x + w >= frame_w - border_margin or y + h >= frame_h - border_margin:
                continue
            rect = _clamp_rect({"x": x, "y": y, "width": w, "height": h}, frame_w, frame_h)
            expanded = _expand_rect(rect, frame_w, frame_h, x_ratio=0.2, y_ratio=0.25) if rect is not None else None
            if expanded is not None and _is_reasonable_table_rect(expanded, frame_w, frame_h):
                candidates.append((float(area), expanded))
                break

    return candidates


def suggest_camera_roi(camera_url: str, max_frames: int = 30) -> dict[str, Any]:
    frames, (frame_width, frame_height) = _sample_frames(camera_url, max_frames=max_frames)
    median = _median_frame(frames, (frame_width, frame_height))

    candidates = _detect_with_yolo(median)
    method = "yolo"
    if not candidates:
        candidates = _detect_with_table_tops(median)
        method = "table-top-mask"
    if not candidates:
        candidates = _detect_with_contours(median)
        method = "contours"

    deduped = [
        rect
        for rect in _dedupe_rects(candidates)
        if _is_reasonable_table_rect(rect, frame_width, frame_height)
    ]
    if not deduped:
        raise ValueError("Could not identify a stable table ROI from the sampled frames")

    primary = deduped[0]
    confidence = min(0.99, 0.55 + (0.1 * min(len(deduped), 4)))
    return {
        "frame_width": frame_width,
        "frame_height": frame_height,
        "sampled_frames": len(frames),
        "method": method,
        "confidence": confidence,
        "roi_coords": primary,
        "candidates": deduped,
    }
