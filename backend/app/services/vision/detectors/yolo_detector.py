"""
YOLO Table Detector Adapter (Standard BBox, OBB, and Segmentation)
──────────────────────────────────────────────────────────────────
Concrete detector adapter supporting Ultralytics YOLO models.
Normalizes standard BBox, Oriented Bounding Box (OBB), and Segmentation outputs
into canonical NormalizedDetection instances with PolygonGeometry.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.services.vision.detectors.base_detector import BaseTableDetector
from app.services.vision.geometry.geometry_models import NormalizedDetection, PolygonGeometry
from app.services.vision.ontology.semantic_mapping import SemanticOntology

logger = logging.getLogger(__name__)


def _ensure_ml_cache_dirs() -> None:
    base_dir = Path(tempfile.gettempdir()) / "foh_ml_cache"
    yolo_dir = base_dir / "ultralytics"
    yolo_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(yolo_dir))


class YOLOTableDetector(BaseTableDetector):
    """
    Ultralytics YOLO Table Detector Adapter.
    Supports task: 'detect' (BBox), 'obb' (Oriented Bounding Box), and 'segment' (Instance Segmentation).
    """

    def __init__(
        self,
        model_id: str,
        file_path: str,
        version: str = "1.0",
        task: str = "detect",
        class_map: dict[int, str] | None = None,
        confidence_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        image_size: int = 640,
        device: str = "auto",
    ):
        super().__init__(
            model_id=model_id,
            file_path=file_path,
            version=version,
            task=task,
            class_map=class_map,
            confidence_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
            image_size=image_size,
            device=device,
        )
        self.model: Any | None = None
        self._raw_names: dict[int, str] = {}
        self._resolved_device: str = "cpu"

    def load(self) -> bool:
        """Loads the YOLO model checkpoint."""
        _ensure_ml_cache_dirs()

        try:
            import torch
            from ultralytics import YOLO
        except ImportError:
            logger.error("ultralytics or torch not installed — cannot load YOLO model")
            self._is_loaded = False
            return False

        resolved_path = Path(self.file_path).resolve()
        if not resolved_path.exists():
            logger.error("Model checkpoint not found at: %s", resolved_path)
            self._is_loaded = False
            return False

        try:
            if self.device == "auto":
                self._resolved_device = "cuda:0" if torch.cuda.is_available() else "cpu"
            else:
                self._resolved_device = self.device

            logger.info("Loading YOLO model '%s' on %s", resolved_path.name, self._resolved_device.upper())
            self.model = YOLO(str(resolved_path), task=self.task if self.task != "detect" else None)
            
            # Extract internal class names
            if hasattr(self.model, "names") and isinstance(self.model.names, dict):
                self._raw_names = {int(k): str(v) for k, v in self.model.names.items()}
            
            # If no class map provided, auto-discover via SemanticOntology
            if not self.class_map:
                res = SemanticOntology.validate_ontology(self._raw_names, None)
                self.class_map = res.resolved_class_map

            self._is_loaded = True
            logger.info("YOLO model '%s' loaded successfully (classes: %d)", self.model_id, len(self._raw_names))
            return True
        except Exception:
            logger.exception("Failed to load YOLO model checkpoint '%s'", self.file_path)
            self.model = None
            self._is_loaded = False
            return False

    def validate(self) -> bool:
        """Runs a zero-frame smoke test to verify inference capabilities."""
        if not self.is_loaded or self.model is None:
            if not self.load():
                return False
        try:
            dummy_frame = np.zeros((self.image_size, self.image_size, 3), dtype=np.uint8)
            t0 = time.perf_counter()
            _ = self.model(
                dummy_frame,
                conf=self.confidence_threshold,
                iou=self.iou_threshold,
                imgsz=self.image_size,
                device=self._resolved_device,
                verbose=False,
            )
            self._last_inference_ms = (time.perf_counter() - t0) * 1000.0
            return True
        except Exception:
            logger.exception("Validation smoke test failed for model '%s'", self.model_id)
            return False

    def detect(self, frame: np.ndarray) -> list[NormalizedDetection]:
        """Runs inference on frame and returns NormalizedDetection list."""
        if not self.is_loaded or self.model is None or frame is None or frame.size == 0:
            return []

        t0 = time.perf_counter()
        detections: list[NormalizedDetection] = []

        try:
            results = self.model(
                frame,
                conf=self.confidence_threshold,
                iou=self.iou_threshold,
                imgsz=self.image_size,
                device=self._resolved_device,
                verbose=False,
            )
        except Exception:
            logger.exception("Inference error in YOLOTableDetector '%s'", self.model_id)
            return []

        self._last_inference_ms = (time.perf_counter() - t0) * 1000.0

        if not results or len(results) == 0:
            return []

        res = results[0]

        # ── Task 1: OBB (Oriented Bounding Box) ──────────────────────────────
        if hasattr(res, "obb") and res.obb is not None and len(res.obb) > 0:
            for box in res.obb:
                raw_cls = int(box.cls[0])
                raw_name = self._raw_names.get(raw_cls, f"cls_{raw_cls}")
                domain_cls = self.class_map.get(raw_cls)
                if not domain_cls:
                    continue  # Ignore non-mapped classes

                conf = float(box.conf[0])
                # xyxyxyxy shape (4, 2)
                pts = box.xyxyxyxy[0].cpu().numpy().tolist()
                poly_geom = PolygonGeometry.from_obb(pts)

                detections.append(
                    NormalizedDetection(
                        domain_class=domain_cls,
                        confidence=conf,
                        geometry=poly_geom,
                        raw_class_id=raw_cls,
                        raw_class_name=raw_name,
                        model_id=self.model_id,
                        model_version=self.version,
                    )
                )

        # ── Task 2: Instance Segmentation (Masks) ────────────────────────────
        elif hasattr(res, "masks") and res.masks is not None and len(res.masks) > 0:
            for mask, box in zip(res.masks, res.boxes):
                raw_cls = int(box.cls[0])
                raw_name = self._raw_names.get(raw_cls, f"cls_{raw_cls}")
                domain_cls = self.class_map.get(raw_cls)
                if not domain_cls:
                    continue

                conf = float(box.conf[0])
                # mask.xy contains list of contour segments
                if mask.xy and len(mask.xy) > 0 and len(mask.xy[0]) >= 3:
                    contour = mask.xy[0].tolist()
                    poly_geom = PolygonGeometry.from_segmentation(contour)
                else:
                    x1, y1, x2, y2 = map(float, box.xyxy[0])
                    poly_geom = PolygonGeometry.from_bbox(x1, y1, x2, y2)

                detections.append(
                    NormalizedDetection(
                        domain_class=domain_cls,
                        confidence=conf,
                        geometry=poly_geom,
                        raw_class_id=raw_cls,
                        raw_class_name=raw_name,
                        model_id=self.model_id,
                        model_version=self.version,
                    )
                )

        # ── Task 3: Standard Axis-Aligned Bounding Box (BBox) ────────────────
        elif hasattr(res, "boxes") and res.boxes is not None and len(res.boxes) > 0:
            for box in res.boxes:
                raw_cls = int(box.cls[0])
                raw_name = self._raw_names.get(raw_cls, f"cls_{raw_cls}")
                domain_cls = self.class_map.get(raw_cls)
                if not domain_cls:
                    continue  # Ignore non-mapped classes

                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(float, box.xyxy[0])
                poly_geom = PolygonGeometry.from_bbox(x1, y1, x2, y2)

                detections.append(
                    NormalizedDetection(
                        domain_class=domain_cls,
                        confidence=conf,
                        geometry=poly_geom,
                        raw_class_id=raw_cls,
                        raw_class_name=raw_name,
                        model_id=self.model_id,
                        model_version=self.version,
                    )
                )

        return detections

    def unload(self) -> None:
        """Releases the model and flushes cache."""
        self.model = None
        self._is_loaded = False
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        logger.info("YOLO model '%s' unloaded", self.model_id)
