"""
Camera Calibration & Perspective Homography Transformation Service
───────────────────────────────────────────────────────────────────
Calculates 3x3 homography matrix from camera reference points (P1..Pn)
to digital floor plan coordinates (F1..Fn).
Provides bi-directional spatial projection:
  - Camera Pixels (x_cam, y_cam)  →  Floor Coordinates (x_floor, y_floor)
  - Floor Coordinates (x_floor, y_floor)  →  Camera Pixels (x_cam, y_cam)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Sequence

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.core.ids import generate_id
from app.models.vision import Camera, CameraCalibration

logger = logging.getLogger(__name__)


def compute_homography(
    camera_points: Sequence[dict[str, float]],
    floor_points: Sequence[dict[str, float]],
) -> tuple[np.ndarray | None, float]:
    """
    Computes 3x3 perspective homography matrix mapping camera points to floor points.
    Returns (H, reprojection_error).
    """
    if len(camera_points) < 4 or len(floor_points) < 4:
        raise ValueError("At least 4 matching reference points are required for perspective calibration")

    src = np.array([[p["x"], p["y"]] for p in camera_points], dtype=np.float32)
    dst = np.array([[p["x"], p["y"]] for p in floor_points], dtype=np.float32)

    if len(camera_points) == 4:
        H = cv2.getPerspectiveTransform(src, dst)
    else:
        H, status = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)

    if H is None:
        raise ValueError("Could not calculate valid perspective transformation matrix")

    # Calculate average reprojection error
    transformed = cv2.perspectiveTransform(src.reshape(-1, 1, 2), H).reshape(-1, 2)
    errors = np.linalg.norm(transformed - dst, axis=1)
    mean_error = float(np.mean(errors))

    return H, mean_error


def camera_to_floor(*args, **kwargs) -> tuple[float, float]:
    """
    Projects camera coordinate (x, y) into digital floor space.
    Accepts either:
      camera_to_floor(x, y, H)
    or:
      camera_to_floor(db, camera_id, x, y)
    """
    if len(args) == 4 and hasattr(args[0], "query"):
        db, camera_id, x, y = args
        calib = db.query(CameraCalibration).filter(CameraCalibration.camera_id == camera_id).first()
        if not calib or not calib.transformation_matrix:
            return float(x), float(y)
        matrix = _to_numpy_matrix(calib.transformation_matrix)
    elif len(args) == 3:
        x, y, H = args
        matrix = _to_numpy_matrix(H)
    else:
        x = kwargs.get("x", 0.0)
        y = kwargs.get("y", 0.0)
        matrix = _to_numpy_matrix(kwargs.get("H"))

    if matrix is None:
        return float(x), float(y)

    pt = np.array([[[float(x), float(y)]]], dtype=np.float32)
    mapped = cv2.perspectiveTransform(pt, matrix)
    fx, fy = mapped[0][0]
    return float(fx), float(fy)


def floor_to_camera(
    floor_x: float,
    floor_y: float,
    H: np.ndarray | list[list[float]] | str,
) -> tuple[float, float]:
    """Projects digital floor coordinate (floor_x, floor_y) back into camera pixels."""
    matrix = _to_numpy_matrix(H)
    if matrix is None:
        return floor_x, floor_y

    try:
        H_inv = np.linalg.inv(matrix)
        pt = np.array([[[float(floor_x), float(floor_y)]]], dtype=np.float32)
        mapped = cv2.perspectiveTransform(pt, H_inv)
        cx, cy = mapped[0][0]
        return float(cx), float(cy)
    except Exception:
        return floor_x, floor_y


def _to_numpy_matrix(matrix_data: Any) -> np.ndarray | None:
    if matrix_data is None:
        return None
    if isinstance(matrix_data, np.ndarray):
        return matrix_data
    if isinstance(matrix_data, str):
        try:
            parsed = json.loads(matrix_data)
            return np.array(parsed, dtype=np.float64)
        except Exception:
            return None
    if isinstance(matrix_data, list):
        return np.array(matrix_data, dtype=np.float64)
    return None


def compute_and_save_homography(
    db: Session,
    camera_id: str,
    point_pairs: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Computes 3x3 homography and saves to CameraCalibration record.
    Supports both nested format {'camera': {'x':..}, 'floor': {'x':..}}
    and flat format {'camera_x': .., 'floor_x': ..}.
    """
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        return {"success": False, "error": f"Camera {camera_id} not found"}

    cam_pts = []
    floor_pts = []
    for p in point_pairs:
        if "camera" in p and "floor" in p:
            cam_pts.append({"x": float(p["camera"]["x"]), "y": float(p["camera"]["y"])})
            floor_pts.append({"x": float(p["floor"]["x"]), "y": float(p["floor"]["y"])})
        elif "camera_x" in p and "floor_x" in p:
            cam_pts.append({"x": float(p["camera_x"]), "y": float(p["camera_y"])})
            floor_pts.append({"x": float(p["floor_x"]), "y": float(p["floor_y"])})

    try:
        H, mean_err = compute_homography(cam_pts, floor_pts)
        matrix_list = H.tolist() if H is not None else None

        existing = db.query(CameraCalibration).filter(CameraCalibration.camera_id == camera_id).first()
        if existing:
            existing.reference_points = json.dumps(point_pairs)
            existing.transformation_matrix = json.dumps(matrix_list)
            existing.status = "CALIBRATED"
            calib = existing
        else:
            calib = CameraCalibration(
                id=generate_id("cal"),
                camera_id=camera_id,
                reference_points=json.dumps(point_pairs),
                transformation_matrix=json.dumps(matrix_list),
                status="CALIBRATED",
            )
            db.add(calib)

        camera.calibration_status = "READY"
        db.commit()
        db.refresh(calib)
        return {
            "success": True,
            "status": "CALIBRATED",
            "reprojection_error": round(mean_err, 2),
            "transformation_matrix": matrix_list,
        }
    except Exception as e:
        logger.error("Failed to calibrate camera %s: %s", camera_id, e)
        return {"success": False, "error": str(e)}


def get_camera_calibration(db: Session, camera_id: str) -> dict[str, Any] | None:
    """Returns parsed calibration record for a camera."""
    calib = db.query(CameraCalibration).filter(CameraCalibration.camera_id == camera_id).first()
    if not calib:
        return None

    try:
        ref_pts = json.loads(calib.reference_points) if calib.reference_points else []
    except Exception:
        ref_pts = []

    try:
        matrix = json.loads(calib.transformation_matrix) if calib.transformation_matrix else None
    except Exception:
        matrix = None

    return {
        "id": calib.id,
        "camera_id": calib.camera_id,
        "status": calib.status,
        "reference_points": ref_pts,
        "transformation_matrix": matrix,
    }


def get_perspective_zone(y_cam: float, frame_height: float = 720.0) -> str:
    """
    Categorizes camera coordinate into perspective depth zone (Section 17):
      FAR: top 35% of frame (distant, smaller expected tables)
      MID: middle 35% of frame (normal dining distance)
      NEAR: bottom 30% of frame (foreground, larger expected tables)
    """
    rel_y = y_cam / max(frame_height, 1.0)
    if rel_y < 0.35:
        return "FAR"
    elif rel_y < 0.70:
        return "MID"
    return "NEAR"


def get_zone_expected_table_size(zone: str, frame_w: float = 1280.0, frame_h: float = 720.0) -> dict[str, Any]:
    """
    Returns valid bounds (min/max width, height, area, scale) for tables in this perspective depth zone.
    """
    if zone == "FAR":
        return {
            "zone": "FAR",
            "min_w": int(frame_w * 0.035),
            "max_w": int(frame_w * 0.22),
            "min_h": int(frame_h * 0.035),
            "max_h": int(frame_h * 0.22),
            "min_area": int(frame_w * frame_h * 0.003),
            "max_area": int(frame_w * frame_h * 0.06),
            "scale_factor": 0.65,
        }
    elif zone == "MID":
        return {
            "zone": "MID",
            "min_w": int(frame_w * 0.05),
            "max_w": int(frame_w * 0.35),
            "min_h": int(frame_h * 0.05),
            "max_h": int(frame_h * 0.35),
            "min_area": int(frame_w * frame_h * 0.008),
            "max_area": int(frame_w * frame_h * 0.14),
            "scale_factor": 1.0,
        }
    else:  # NEAR
        return {
            "zone": "NEAR",
            "min_w": int(frame_w * 0.08),
            "max_w": int(frame_w * 0.48),
            "min_h": int(frame_h * 0.08),
            "max_h": int(frame_h * 0.45),
            "min_area": int(frame_w * frame_h * 0.015),
            "max_area": int(frame_w * frame_h * 0.24),
            "scale_factor": 1.45,
        }


def validate_perspective_geometry(
    bbox: tuple[int, int, int, int],
    frame_w: float = 1280.0,
    frame_h: float = 720.0,
) -> tuple[bool, str, float]:
    """
    Validates candidate table bounding box against perspective depth zone (Sections 17 & 18).
    Returns (is_valid, zone_name, geometry_validity_score 0.0-1.0).
    """
    x, y, w, h = bbox
    center_y = y + h / 2.0
    zone = get_perspective_zone(center_y, frame_h)
    bounds = get_zone_expected_table_size(zone, frame_w, frame_h)

    area = w * h
    if area < bounds["min_area"] or area > bounds["max_area"]:
        return False, zone, 0.40
    if w < bounds["min_w"] or h < bounds["min_h"]:
        return False, zone, 0.45
    if w > bounds["max_w"] or h > bounds["max_h"]:
        return False, zone, 0.45

    aspect = w / max(float(h), 1.0)
    if aspect < 0.35 or aspect > 2.8:
        return False, zone, 0.50

    return True, zone, 0.95
