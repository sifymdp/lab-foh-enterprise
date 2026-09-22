"""
Vision & CCTV Management API Router
────────────────────────────────────
Handles camera registration, calibration, polygon table ROIs,
mismatch alerts, human verification actions, and real-time vision telemetry.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.ids import generate_id
from app.core.permissions import require_permission
from app.core.temporal_occupancy import temporal_tracker
from app.core.vision_engine import vision_engine
from app.models import Floor, Table, User
from app.models.vision import Camera, CameraCalibration, TableROI, VisionMismatch, VisionObservation
from app.services.mismatch_service import mismatch_service

router = APIRouter(prefix="/vision", tags=["vision"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class CameraCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    stream_url: str = Field(..., min_length=1)
    section: str | None = None
    floor_id: str | None = None
    resolution: str | None = "1280x720"


class CameraCalibratePayload(BaseModel):
    reference_points: list[dict[str, Any]]
    transformation_matrix: list[list[float]] | None = None


class TableROIPayload(BaseModel):
    table_id: str
    polygon_points: list[dict[str, float]] | None = None
    bounds: dict[str, float] | None = None
    active: bool = True


class MismatchResolvePayload(BaseModel):
    action: str = Field(..., description="CONFIRM_OCCUPIED | CONFIRM_AVAILABLE | CONFIRM_DEPARTURE | DISMISS")
    notes: str | None = None


# ── Cameras ──────────────────────────────────────────────────────────────────

@router.get("/cameras")
def list_cameras(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission("camera.view", current_user, db)
    tenant_id = getattr(current_user, "tenant_id", None) or "org-demo"

    cameras = db.execute(
        select(Camera).where(Camera.tenant_id == tenant_id).order_by(Camera.name)
    ).scalars().all()

    results = []
    for c in cameras:
        rois = db.execute(
            select(TableROI).where(TableROI.camera_id == c.id, TableROI.active == True)
        ).scalars().all()

        results.append({
            "id": c.id,
            "name": c.name,
            "section": c.section,
            "floor_id": c.floor_id,
            "stream_url": c.stream_url,
            "resolution": c.resolution,
            "fps": c.fps,
            "enabled": c.enabled,
            "calibration_status": c.calibration_status,
            "configured_rois_count": len(rois),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return results


@router.post("/cameras")
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission("camera.configuration", current_user, db)
    tenant_id = getattr(current_user, "tenant_id", None) or "org-demo"
    branch_id = getattr(current_user, "branch_id", None) or "branch-demo"

    cam_id = generate_id("cam")
    camera = Camera(
        id=cam_id,
        tenant_id=tenant_id,
        branch_id=branch_id,
        floor_id=payload.floor_id,
        name=payload.name,
        section=payload.section,
        stream_url=payload.stream_url,
        resolution=payload.resolution or "1280x720",
        enabled=True,
        calibration_status="UNCONFIGURED",
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return {"id": camera.id, "name": camera.name, "stream_url": camera.stream_url}


@router.post("/cameras/{camera_id}/calibrate")
def calibrate_camera(
    camera_id: str,
    payload: CameraCalibratePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission("camera.calibration", current_user, db)
    camera = db.execute(select(Camera).where(Camera.id == camera_id)).scalar_one_or_none()
    if not camera:
        raise HTTPException(404, "Camera not found")

    calib = CameraCalibration(
        id=generate_id("cal"),
        camera_id=camera.id,
        reference_points=json.dumps(payload.reference_points),
        transformation_matrix=json.dumps(payload.transformation_matrix) if payload.transformation_matrix else None,
        status="CALIBRATED",
    )
    camera.calibration_status = "READY"
    db.add(calib)
    db.commit()
    return {"success": True, "calibration_status": "READY"}


# ── ROIs ─────────────────────────────────────────────────────────────────────

@router.get("/cameras/{camera_id}/rois")
def get_camera_rois(
    camera_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission("camera.view", current_user, db)
    rois = db.execute(
        select(TableROI).where(TableROI.camera_id == camera_id)
    ).scalars().all()

    out = []
    for r in rois:
        table = db.execute(select(Table).where(Table.id == r.table_id)).scalar_one_or_none()
        out.append({
            "id": r.id,
            "camera_id": r.camera_id,
            "table_id": r.table_id,
            "table_number": table.number if table else "?",
            "polygon_points": json.loads(r.polygon_points) if r.polygon_points else [],
            "bounds": json.loads(r.bounds) if r.bounds else None,
            "active": r.active,
        })
    return out


@router.post("/cameras/{camera_id}/rois")
def save_table_roi(
    camera_id: str,
    payload: TableROIPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission("camera.configuration", current_user, db)
    camera = db.execute(select(Camera).where(Camera.id == camera_id)).scalar_one_or_none()
    if not camera:
        raise HTTPException(404, "Camera not found")

    table = db.execute(select(Table).where(Table.id == payload.table_id)).scalar_one_or_none()
    if not table:
        raise HTTPException(404, "Table not found")

    existing = db.execute(
        select(TableROI).where(
            TableROI.camera_id == camera_id,
            TableROI.table_id == payload.table_id,
        )
    ).scalar_one_or_none()

    poly_json = json.dumps(payload.polygon_points) if payload.polygon_points else None
    bounds_json = json.dumps(payload.bounds) if payload.bounds else None

    if existing:
        existing.polygon_points = poly_json
        existing.bounds = bounds_json
        existing.active = payload.active
        roi_record = existing
    else:
        roi_record = TableROI(
            id=generate_id("roi"),
            camera_id=camera_id,
            table_id=payload.table_id,
            polygon_points=poly_json,
            bounds=bounds_json,
            active=payload.active,
        )
        db.add(roi_record)

    # Also update table.roi_coords and table.camera_url for backward compatibility
    if bounds_json:
        table.roi_coords = bounds_json
    table.camera_url = camera.stream_url

    db.commit()
    db.refresh(roi_record)
    return {"id": roi_record.id, "table_id": roi_record.table_id, "saved": True}


# ── Mismatches ───────────────────────────────────────────────────────────────

@router.get("/mismatches")
def list_mismatches(
    status_filter: str = Query("PENDING"),
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission("camera.view", current_user, db)
    tenant_id = getattr(current_user, "tenant_id", None) or "org-demo"

    query = select(VisionMismatch).where(VisionMismatch.tenant_id == tenant_id)
    if status_filter != "ALL":
        query = query.where(VisionMismatch.status == status_filter)
    query = query.order_by(desc(VisionMismatch.created_at)).limit(limit)

    rows = db.execute(query).scalars().all()
    return [
        {
            "id": r.id,
            "camera_id": r.camera_id,
            "table_id": r.table_id,
            "table_number": r.table_number,
            "digital_status": r.digital_status,
            "observed_state": r.observed_state,
            "detected_people": r.detected_people,
            "confidence": r.confidence,
            "mismatch_type": r.mismatch_type,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        }
        for r in rows
    ]


@router.post("/mismatches/{mismatch_id}/resolve")
def resolve_mismatch(
    mismatch_id: str,
    payload: MismatchResolvePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission("camera.override", current_user, db)
    try:
        res = mismatch_service.resolve_mismatch(
            db=db,
            mismatch_id=mismatch_id,
            action=payload.action,
            user_id=current_user.id,
            notes=payload.notes,
        )
        return res
    except ValueError as e:
        raise HTTPException(404, str(e))


# ── Live Telemetry ───────────────────────────────────────────────────────────

@router.get("/telemetry")
def get_vision_telemetry(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission("camera.view", current_user, db)
    tenant_id = getattr(current_user, "tenant_id", None) or "org-demo"

    pending_mismatches_count = db.execute(
        select(VisionMismatch).where(
            VisionMismatch.tenant_id == tenant_id,
            VisionMismatch.status == "PENDING",
        )
    ).scalars().all()

    active_cameras_count = db.execute(
        select(Camera).where(Camera.tenant_id == tenant_id, Camera.enabled == True)
    ).scalars().all()

    return {
        "model_name": vision_engine.model_name,
        "is_ready": vision_engine.is_ready,
        "device": vision_engine.device.upper(),
        "ai_fps": vision_engine.current_fps,
        "active_cameras": len(active_cameras_count),
        "pending_mismatches": len(pending_mismatches_count),
        "tracker": "ByteTrack",
    }
