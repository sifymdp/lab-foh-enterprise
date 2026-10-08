"""
Representation-Agnostic Geometry Service
──────────────────────────────────────────
Provides polygon intersection, polygon IoU, centroid distances,
containment testing, and perspective homography transformation.
"""

from __future__ import annotations

import math
from typing import Sequence

import cv2
import numpy as np

from app.services.vision.geometry.geometry_models import PolygonGeometry


def polygon_area(points: Sequence[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    pts = np.array(points, dtype=np.float32)
    return float(cv2.contourArea(pts))


def polygon_intersection_area(
    poly1: PolygonGeometry | Sequence[tuple[float, float]],
    poly2: PolygonGeometry | Sequence[tuple[float, float]],
) -> float:
    """Calculates intersection area between two 2D polygons using OpenCV."""
    pts1 = poly1.points if isinstance(poly1, PolygonGeometry) else poly1
    pts2 = poly2.points if isinstance(poly2, PolygonGeometry) else poly2

    if len(pts1) < 3 or len(pts2) < 3:
        return 0.0

    np_pts1 = np.array(pts1, dtype=np.float32).reshape((-1, 1, 2))
    np_pts2 = np.array(pts2, dtype=np.float32).reshape((-1, 1, 2))

    try:
        # cv2.intersectConvexPoly is robust and fast for convex approximations
        # For general polygons, we use bitwise mask rasterization over the local bounding box
        min_x = min(min(p[0] for p in pts1), min(p[0] for p in pts2))
        max_x = max(max(p[0] for p in pts1), max(p[0] for p in pts2))
        min_y = min(min(p[1] for p in pts1), min(p[1] for p in pts2))
        max_y = max(max(p[1] for p in pts1), max(p[1] for p in pts2))

        w = int(math.ceil(max_x - min_x)) + 4
        h = int(math.ceil(max_y - min_y)) + 4
        if w <= 0 or h <= 0 or w > 4000 or h > 4000:
            return 0.0

        mask1 = np.zeros((h, w), dtype=np.uint8)
        mask2 = np.zeros((h, w), dtype=np.uint8)

        shifted1 = np.array([[[int(round(p[0] - min_x + 2)), int(round(p[1] - min_y + 2))]] for p in pts1], dtype=np.int32)
        shifted2 = np.array([[[int(round(p[0] - min_x + 2)), int(round(p[1] - min_y + 2))]] for p in pts2], dtype=np.int32)

        cv2.fillPoly(mask1, [shifted1], 255)
        cv2.fillPoly(mask2, [shifted2], 255)

        inter = cv2.bitwise_and(mask1, mask2)
        return float(np.count_nonzero(inter))
    except Exception:
        return 0.0


def polygon_iou(
    poly1: PolygonGeometry,
    poly2: PolygonGeometry,
) -> float:
    """
    Computes Intersection-over-Union (IoU) between two polygons.
    IoU = Area(poly1 ∩ poly2) / Area(poly1 ∪ poly2)
    """
    area1 = poly1.area()
    area2 = poly2.area()
    if area1 <= 0.0 or area2 <= 0.0:
        return 0.0

    inter_area = polygon_intersection_area(poly1, poly2)
    union_area = area1 + area2 - inter_area
    if union_area <= 0.0:
        return 0.0
    return float(max(0.0, min(1.0, inter_area / union_area)))


def point_in_polygon(point: tuple[float, float], poly: PolygonGeometry) -> bool:
    """Tests if point (x, y) is inside the polygon."""
    if len(poly.points) < 3:
        x1, y1, x2, y2 = poly.bounding_box()
        return x1 <= point[0] <= x2 and y1 <= point[1] <= y2
    pts = np.array(poly.points, dtype=np.float32)
    return cv2.pointPolygonTest(pts, (float(point[0]), float(point[1])), False) >= 0


def distance_between_centroids(poly1: PolygonGeometry, poly2: PolygonGeometry) -> float:
    """Euclidean distance between centroids of two polygons."""
    c1 = poly1.centroid()
    c2 = poly2.centroid()
    return float(math.hypot(c1[0] - c2[0], c1[1] - c2[1]))


def transform_polygon_homography(
    poly: PolygonGeometry,
    H: np.ndarray | Sequence[Sequence[float]],
) -> PolygonGeometry:
    """
    Projects all polygon vertices from camera space to floor space using 3x3 homography matrix H.
    """
    if H is None or len(poly.points) == 0:
        return poly

    H_mat = np.array(H, dtype=np.float32) if not isinstance(H, np.ndarray) else H
    if H_mat.shape != (3, 3):
        return poly

    try:
        pts = np.array([[[float(p[0]), float(p[1])]] for p in poly.points], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pts, H_mat)
        new_pts = [(float(pt[0][0]), float(pt[0][1])) for pt in transformed]
        return PolygonGeometry(points=new_pts, source_representation=poly.source_representation)
    except Exception:
        return poly
