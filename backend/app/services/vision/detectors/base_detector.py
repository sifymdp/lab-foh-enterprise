"""
Model-Agnostic Base Table Detector Abstraction
────────────────────────────────────────────────
Common abstract interface for all table detection models.
The rest of the FOH application interfaces ONLY with this contract,
ensuring model architecture independence.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from app.services.vision.geometry.geometry_models import NormalizedDetection

logger = logging.getLogger(__name__)


class BaseTableDetector(ABC):
    """Abstract base class for all table detection model adapters."""

    def __init__(
        self,
        model_id: str,
        file_path: str,
        version: str = "1.0",
        task: str = "detect",  # detect | obb | segment
        class_map: dict[int, str] | None = None,
        confidence_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        image_size: int = 640,
        device: str = "auto",
    ):
        self.model_id = model_id
        self.file_path = file_path
        self.version = version
        self.task = task
        self.class_map = class_map or {}
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.image_size = image_size
        self.device = device
        self._is_loaded = False
        self._last_inference_ms = 0.0

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def last_inference_ms(self) -> float:
        return self._last_inference_ms

    @abstractmethod
    def load(self) -> bool:
        """Loads model weights into memory/device. Returns True if successful."""
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Runs a validation smoke test on the model."""
        pass

    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[NormalizedDetection]:
        """
        Runs table inference on a raw BGR frame and returns normalized detections.
        Raw model outputs must be converted to NormalizedDetection with PolygonGeometry.
        """
        pass

    @abstractmethod
    def unload(self) -> None:
        """Releases model weights and frees GPU/CPU memory."""
        pass

    def get_metadata(self) -> dict[str, Any]:
        """Returns standard metadata dictionary for the detector."""
        return {
            "model_id": self.model_id,
            "version": self.version,
            "task": self.task,
            "file_path": self.file_path,
            "is_loaded": self.is_loaded,
            "confidence_threshold": self.confidence_threshold,
            "iou_threshold": self.iou_threshold,
            "image_size": self.image_size,
            "device": self.device,
            "class_map": self.class_map,
            "last_inference_ms": round(self._last_inference_ms, 2),
        }
