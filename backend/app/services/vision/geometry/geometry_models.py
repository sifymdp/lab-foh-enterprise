"""
Unified Representation-Agnostic Geometry Models
────────────────────────────────────────────────
Normalizes Bounding Boxes, Oriented Bounding Boxes (OBB), and Segmentation Masks
into a standard PolygonGeometry representation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

import cv2
import numpy as np


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def to_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass
class PolygonGeometry:
    """
    Representation-agnostic polygon representation for all vision outputs.
    Points are ordered clockwise or counter-clockwise as [(x1, y1), (x2, y2), ...].
    """
    points: list[tuple[float, float]]
    source_representation: str = "bbox"  # bbox | obb | segmentation | polygon

    def to_dict(self) -> dict[str, Any]:
        return {
            "geometry_type": "polygon",
            "source_representation": self.source_representation,
            "points": [[round(p[0], 2), round(p[1], 2)] for p in self.points],
            "centroid": [round(c, 2) for c in self.centroid()],
            "area": round(self.area(), 2),
            "bbox": [round(b, 2) for b in self.bounding_box()],
        }

    @classmethod
    def from_bbox(cls, x1: float, y1: float, x2: float, y2: float) -> PolygonGeometry:
        """Converts an axis-aligned bounding box [x1, y1, x2, y2] to a 4-point polygon."""
        pts = [
            (float(x1), float(y1)),
            (float(x2), float(y1)),
            (float(x2), float(y2)),
            (float(x1), float(y2)),
        ]
        return cls(points=pts, source_representation="bbox")

    @classmethod
    def from_xywh(cls, x: float, y: float, w: float, h: float) -> PolygonGeometry:
        """Converts [x, y, width, height] to a 4-point polygon."""
        return cls.from_bbox(x, y, x + w, y + h)

    @classmethod
    def from_obb(cls, obb_points: Sequence[Sequence[float]]) -> PolygonGeometry:
        """
        Converts 4-point Oriented Bounding Box [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        to PolygonGeometry.
        """
        pts = [(float(p[0]), float(p[1])) for p in obb_points[:4]]
        return cls(points=pts, source_representation="obb")

    @classmethod
    def from_segmentation(
        cls,
        contour_points: Sequence[Sequence[float]],
        simplify_epsilon: float = 2.0,
    ) -> PolygonGeometry:
        """
        Converts dense segmentation mask contour to a simplified PolygonGeometry.
        """
        if len(contour_points) < 3:
            pts = [(float(p[0]), float(p[1])) for p in contour_points]
            return cls(points=pts, source_representation="segmentation")

        pts_array = np.array(contour_points, dtype=np.float32).reshape((-1, 1, 2))
        peri = cv2.arcLength(pts_array, True)
        eps = max(simplify_epsilon, 0.01 * peri)
        approx = cv2.approxPolyDP(pts_array, eps, True)
        simplified = [(float(pt[0][0]), float(pt[0][1])) for pt in approx]
        return cls(points=simplified, source_representation="segmentation")

    def bounding_box(self) -> tuple[float, float, float, float]:
        """Returns axis-aligned bounding box (x1, y1, x2, y2)."""
        if not self.points:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    def xywh(self) -> tuple[int, int, int, int]:
        """Returns integer (x, y, width, height)."""
        x1, y1, x2, y2 = self.bounding_box()
        return (int(round(x1)), int(round(y1)), int(round(x2 - x1)), int(round(y2 - y1)))

    def centroid(self) -> tuple[float, float]:
        """Calculates polygon centroid (cx, cy)."""
        if not self.points:
            return (0.0, 0.0)
        if len(self.points) < 3:
            xs = [p[0] for p in self.points]
            ys = [p[1] for p in self.points]
            return (sum(xs) / len(xs), sum(ys) / len(ys))

        pts_np = np.array(self.points, dtype=np.float32)
        M = cv2.moments(pts_np)
        if abs(M["m00"]) > 1e-5:
            cx = float(M["m10"] / M["m00"])
            cy = float(M["m01"] / M["m00"])
            return (cx, cy)

        # Fallback to mean coordinates
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    def area(self) -> float:
        """Calculates spatial area of the polygon."""
        if len(self.points) < 3:
            x1, y1, x2, y2 = self.bounding_box()
            return max(0.0, (x2 - x1) * (y2 - y1))
        pts_np = np.array(self.points, dtype=np.float32)
        return float(cv2.contourArea(pts_np))

    def to_cv2_contour(self) -> np.ndarray:
        """Converts to OpenCV contour array shape (N, 1, 2) int32."""
        pts = [[int(round(p[0])), int(round(p[1]))] for p in self.points]
        return np.array(pts, dtype=np.int32).reshape((-1, 1, 2))


@dataclass
class NormalizedDetection:
    """
    Standard normalized detection contract returned by all detector adapters.
    """
    domain_class: str                    # Standard semantic entity (e.g. dining_table, person)
    confidence: float
    geometry: PolygonGeometry
    raw_class_id: int
    raw_class_name: str
    track_id: int | None = None
    model_id: str = "unknown"
    model_version: str = "1.0"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_class": self.domain_class,
            "confidence": round(self.confidence, 4),
            "geometry": self.geometry.to_dict(),
            "raw_class_id": self.raw_class_id,
            "raw_class_name": self.raw_class_name,
            "track_id": self.track_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "timestamp": self.timestamp,
            "attributes": self.attributes,
        }
