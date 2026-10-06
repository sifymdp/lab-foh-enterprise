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
from app.models.vision import (
    Camera,
    CameraCalibration,
    FloorPlanSuggestion,
    FloorPlanVersion,
    TableROI,
    VisionMismatch,
    VisionObservation,
)
from app.services import calibration_service, floor_plan_ai_service
from app.services.mismatch_service import mismatch_service
from app.services.video_sources import video_source_manager
from app.services.vision_benchmark_service import run_vision_benchmark

router = APIRouter(prefix="/vision", tags=["vision"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class CameraCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    stream_url: str = Field(..., min_length=1)
    source_type: str = "RTSP"
    section: str | None = None
    floor_id: str | None = None
    resolution: str | None = "1280x720"


class CameraUpdate(BaseModel):
    name: str | None = None
    stream_url: str | None = None
    source_type: str | None = None
    section: str | None = None
    floor_id: str | None = None
    resolution: str | None = None
    is_online: bool | None = None
    health_status: str | None = None
    enabled: bool | None = None


class VideoSourceTestPayload(BaseModel):
    source_type: str
    stream_url: str


class FloorPlanDetectPayload(BaseModel):
    camera_id: str
    floor_id: str | None = None
    override_stream_url: str | None = None
    source_type: str | None = None
    min_confidence: float = 0.25
    reconstruct_mode: bool = False


class SuggestionActionPayload(BaseModel):
    action: str = Field(..., description="APPROVE | REJECT | IGNORE | EDIT")
    review_notes: str | None = None
    edited_data: dict[str, Any] | None = None


class ApplySuggestionsPayload(BaseModel):
    floor_id: str
    suggestion_ids: list[str]
    replace_existing: bool = False


class FloorPlanClearPayload(BaseModel):
    floor_id: str


class FloorPlanReconstructPayload(BaseModel):
    camera_id: str
    floor_id: str
    override_stream_url: str | None = None
    source_type: str | None = None
    min_confidence: float = 0.20
    replace_existing: bool = True


class BenchmarkRunPayload(BaseModel):
    sample_frames: int = 15
    video_source: str | None = None


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
            "source_type": getattr(c, "source_type", "RTSP") or "RTSP",
            "is_online": getattr(c, "is_online", True),
            "health_status": getattr(c, "health_status", "ONLINE") or "ONLINE",
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
        source_type=payload.source_type or "RTSP",
        is_online=True,
        health_status="ONLINE",
        resolution=payload.resolution or "1280x720",
        enabled=True,
        calibration_status="UNCONFIGURED",
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return {
        "id": camera.id,
        "name": camera.name,
        "stream_url": camera.stream_url,
        "source_type": camera.source_type,
        "health_status": camera.health_status,
    }


@router.patch("/cameras/{camera_id}")
@router.put("/cameras/{camera_id}")
def update_camera(
    camera_id: str,
    payload: CameraUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission("camera.configuration", current_user, db)
    tenant_id = getattr(current_user, "tenant_id", None) or "org-demo"

    camera = db.execute(
        select(Camera).where(Camera.id == camera_id, Camera.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if not camera:
        camera = db.execute(
            select(Camera).where(Camera.id == camera_id)
        ).scalar_one_or_none()
    if not camera:
        raise HTTPException(404, f"Camera {camera_id} not found")

    if payload.name is not None:
        camera.name = payload.name
    if payload.stream_url is not None:
        camera.stream_url = payload.stream_url
    if payload.source_type is not None:
        camera.source_type = payload.source_type
    if payload.section is not None:
        camera.section = payload.section
    if payload.floor_id is not None:
        camera.floor_id = payload.floor_id
    if payload.resolution is not None:
        camera.resolution = payload.resolution
    if payload.is_online is not None:
        camera.is_online = payload.is_online
    if payload.health_status is not None:
        camera.health_status = payload.health_status
    if payload.enabled is not None:
        camera.enabled = payload.enabled

    db.commit()
    db.refresh(camera)

    try:
        from app.services.video_sources import video_source_manager
        with video_source_manager._lock:
            if camera_id in video_source_manager._sources:
                existing = video_source_manager._sources[camera_id]
                existing.disconnect()
                del video_source_manager._sources[camera_id]
            # Also clear any floor stream worker associated with this camera
            floor_stream_id = f"stream_{camera.floor_id}"
            if floor_stream_id in video_source_manager._sources:
                existing = video_source_manager._sources[floor_stream_id]
                existing.disconnect()
                del video_source_manager._sources[floor_stream_id]
    except Exception as e:
        logger.warning("Failed to refresh video source manager for camera %s: %s", camera_id, e)

    return {
        "id": camera.id,
        "name": camera.name,
        "stream_url": camera.stream_url,
        "source_type": camera.source_type,
        "health_status": camera.health_status,
        "resolution": camera.resolution,
        "section": camera.section,
        "floor_id": camera.floor_id,
        "enabled": camera.enabled,
    }


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

    result = calibration_service.compute_and_save_homography(
        db=db,
        camera_id=camera_id,
        point_pairs=payload.reference_points,
    )
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Calibration failed"))

    return result


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
        t = db.execute(select(Table).where(Table.id == r.table_id)).scalar_one_or_none()
        out.append({
            "id": r.id,
            "table_id": r.table_id,
            "table_number": t.number if t else "Unknown",
            "polygon_points": json.loads(r.polygon_points) if r.polygon_points else None,
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

    existing_roi = db.execute(
        select(TableROI).where(TableROI.camera_id == camera_id, TableROI.table_id == payload.table_id)
    ).scalar_one_or_none()

    poly_str = json.dumps(payload.polygon_points) if payload.polygon_points else None
    bounds_str = json.dumps(payload.bounds) if payload.bounds else None

    if existing_roi:
        existing_roi.polygon_points = poly_str
        existing_roi.bounds = bounds_str
        existing_roi.active = payload.active
        existing_roi.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {"id": existing_roi.id, "status": "updated"}
    else:
        new_roi = TableROI(
            id=generate_id("roi"),
            camera_id=camera_id,
            table_id=payload.table_id,
            polygon_points=poly_str,
            bounds=bounds_str,
            active=payload.active,
        )
        db.add(new_roi)
        db.commit()
        return {"id": new_roi.id, "status": "created"}


# ── Mismatches ───────────────────────────────────────────────────────────────

@router.get("/mismatches")
def list_mismatches(
    status_filter: str | None = Query(None, alias="status_filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission("camera.view", current_user, db)
    tenant_id = getattr(current_user, "tenant_id", None) or "org-demo"

    query = select(VisionMismatch).where(VisionMismatch.tenant_id == tenant_id)
    if status_filter and status_filter.upper() != "ALL":
        query = query.where(VisionMismatch.status == status_filter.upper())
    query = query.order_by(desc(VisionMismatch.created_at)).limit(50)

    items = db.execute(query).scalars().all()
    return [
        {
            "id": m.id,
            "table_id": m.table_id,
            "table_number": m.table_number,
            "digital_status": m.digital_status,
            "observed_state": m.observed_state,
            "detected_people": m.detected_people,
            "confidence": m.confidence,
            "mismatch_type": m.mismatch_type,
            "status": m.status,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in items
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

    cams = active_cameras_count
    health_summary = {
        "ONLINE": sum(1 for c in cams if c.health_status == "ONLINE" and c.is_online),
        "OFFLINE": sum(1 for c in cams if not c.is_online or c.health_status == "OFFLINE"),
        "WARNING": sum(1 for c in cams if c.health_status in ("LOW_FPS", "LOW_QUALITY", "CONNECTING")),
    }

    return {
        "model_name": vision_engine.model_name,
        "is_ready": vision_engine.is_ready,
        "device": vision_engine.device.upper(),
        "ai_fps": vision_engine.current_fps,
        "active_cameras": len(active_cameras_count),
        "pending_mismatches": len(pending_mismatches_count),
        "tracker": vision_engine.get_tracker().replace(".yaml", "").upper(),
        "supported_trackers": ["bytetrack", "botsort"],
        "camera_health": health_summary,
    }


# ── Video Sources ─────────────────────────────────────────────────────────────

@router.get("/sources")
def get_supported_sources(
    current_user: User = Depends(get_current_user),
):
    """
    List supported video source modes (Mode 1 to Mode 6) and available uploaded clips.
    """
    files = video_source_manager.list_uploaded_videos()
    return {
        "supported_modes": [
            {
                "id": "RTSP",
                "mode_number": 1,
                "label": "Mode 1: Real CCTV / RTSP",
                "is_demo": False,
                "description": "Production IP Cameras & Network Video Recorders",
                "example": "rtsp://admin:pass@192.168.1.100:554/h264Preview_01_main",
                "default_url": "rtsp://camera-address/stream",
            },
            {
                "id": "ONVIF",
                "mode_number": 2,
                "label": "Mode 2: ONVIF Camera",
                "is_demo": False,
                "description": "ONVIF Profile S/T Auto-Discovery & Configuration",
                "example": "http://192.168.1.120:80/onvif/device_service",
                "default_url": "http://192.168.1.120:80/onvif/device_service",
            },
            {
                "id": "WEBCAM",
                "mode_number": 3,
                "label": "Mode 3: Local Webcam (Camera 0, 1)",
                "is_demo": True,
                "description": "Local host device camera index (0, 1, 2...)",
                "example": "0",
                "default_url": "0",
            },
            {
                "id": "VIDEO_FILE",
                "mode_number": 4,
                "label": "Mode 4: Uploaded Restaurant Video (MP4, AVI, MOV)",
                "is_demo": True,
                "description": "Real restaurant footage loops from backend/camera_uploads/",
                "example": "table_t-1.mp4",
                "default_url": files[0] if files else "table_t-1.mp4",
            },
            {
                "id": "DEMO_STREAM",
                "mode_number": 5,
                "label": "Mode 5: Demo / External Live Stream with DemoStreamAdapter",
                "is_demo": True,
                "description": "Permitted external live stream or fallback demo",
                "example": "https://example.com/demo-stream.m3u8",
                "default_url": "https://example.com/demo-stream.m3u8",
            },
            {
                "id": "SYNTHETIC",
                "mode_number": 6,
                "label": "Mode 6: Synthetic Restaurant Simulation (offline testing fallback)",
                "is_demo": True,
                "description": "Procedural simulated dining room with tables and dynamic patrons",
                "example": "synthetic",
                "default_url": "synthetic",
            },
        ],
        "available_video_files": files,
    }


@router.post("/sources/test")
def test_video_source(
    payload: VideoSourceTestPayload,
    current_user: User = Depends(get_current_user),
):
    """
    Test connection to a video source and capture a sample frame without saving.
    """
    result = video_source_manager.test_connection(
        source_type=payload.source_type,
        stream_url=payload.stream_url,
    )
    return result


# ── Camera Calibration Details ────────────────────────────────────────────────

@router.get("/cameras/{camera_id}/calibration")
def get_camera_calibration(
    camera_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission("camera.view", current_user, db)
    camera = db.execute(select(Camera).where(Camera.id == camera_id)).scalar_one_or_none()
    if not camera:
        raise HTTPException(404, "Camera not found")

    calib = calibration_service.get_camera_calibration(db, camera_id)
    return {
        "camera_id": camera_id,
        "camera_name": camera.name,
        "is_calibrated": calib is not None and calib.get("status") == "CALIBRATED",
        "calibration": calib,
    }


# ── AI Floor Plan Detection & Suggestions ────────────────────────────────────

@router.post("/floor-plan/detect")
def detect_floor_layout(
    payload: FloorPlanDetectPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Triggers AI Computer Vision layout analysis:
    - Captures frames from camera/video source
    - Detects table candidates and shapes using YOLO11 + OpenCV Tabletop contours
    - Projects candidate coordinates through homography calibration to floor space
    - Matches candidate tables against existing digital floor plan
    - Surfaces positional drift, size changes, new tables, and removed tables
    """
    require_permission("camera.configuration", current_user, db)
    tenant_id = getattr(current_user, "tenant_id", None) or "org-demo"

    camera = db.execute(select(Camera).where(Camera.id == payload.camera_id)).scalar_one_or_none()
    if not camera:
        # Fallback to demo camera
        camera = db.execute(select(Camera)).scalars().first()
        if not camera:
            camera = Camera(
                id=payload.camera_id,
                tenant_id=tenant_id,
                branch_id="branch-demo",
                name="AI Detection Camera",
                stream_url=payload.override_stream_url or "table_t-1.mp4",
                source_type="VIDEO_FILE",
                enabled=True,
            )
            db.add(camera)
            db.commit()
            db.refresh(camera)

    floor_id = payload.floor_id or camera.floor_id
    if not floor_id:
        f = db.execute(select(Floor)).scalars().first()
        floor_id = f.id if f else None
    if not floor_id:
        raise HTTPException(400, "floor_id is required or must be configured on the camera")

    try:
        report = floor_plan_ai_service.analyze_floor_layout(
            db=db,
            camera_id=camera.id,
            floor_id=floor_id,
            tenant_id=tenant_id,
            created_by_user_id=current_user.id,
            stream_url=payload.override_stream_url or camera.stream_url,
            source_type=payload.source_type or camera.source_type or "RTSP",
            min_confidence=payload.min_confidence,
            reconstruct_mode=payload.reconstruct_mode,
        )
        return report
    except Exception as e:
        raise HTTPException(500, f"AI Floor Plan Detection failed: {str(e)}")


@router.get("/floor-plan/suggestions")
def get_floor_plan_suggestions(
    floor_id: str,
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List AI Floor Plan suggestions for review by Owner/Manager.
    """
    require_permission("camera.view", current_user, db)
    tenant_id = getattr(current_user, "tenant_id", None) or "org-demo"

    query = select(FloorPlanSuggestion).where(
        FloorPlanSuggestion.floor_id == floor_id,
        FloorPlanSuggestion.tenant_id == tenant_id,
    )
    if status_filter:
        query = query.where(FloorPlanSuggestion.status == status_filter.upper())
    else:
        query = query.where(FloorPlanSuggestion.status.in_(["PENDING", "APPROVED"]))
    query = query.order_by(desc(FloorPlanSuggestion.created_at)).limit(30)

    suggestions = db.execute(query).scalars().all()

    out = []
    for s in suggestions:
        existing_table = None
        if s.existing_table_id:
            t = db.execute(select(Table).where(Table.id == s.existing_table_id)).scalar_one_or_none()
            if t:
                existing_table = {
                    "id": t.id,
                    "label": t.number,
                    "x": t.x,
                    "y": t.y,
                    "width": t.width,
                    "height": t.height,
                    "shape": t.shape,
                    "section": t.section_id,
                }

        pos = json.loads(s.detected_position) if s.detected_position else {}
        if not pos or pos.get("x") is None or pos.get("width") is None:
            if existing_table:
                pos = {
                    "x": existing_table["x"],
                    "y": existing_table["y"],
                    "width": existing_table["width"],
                    "height": existing_table["height"],
                    "shape": existing_table.get("shape", "RECTANGLE"),
                    "capacity": 4,
                }
            else:
                pos = {"x": 100, "y": 100, "width": 110, "height": 75, "shape": "RECTANGLE", "capacity": 4}
        cbbox = json.loads(s.camera_bbox) if s.camera_bbox else None

        out.append({
            "id": s.id,
            "camera_id": s.camera_id,
            "floor_id": s.floor_id,
            "suggestion_type": s.suggestion_type,
            "existing_table_id": s.existing_table_id,
            "existing_table": existing_table,
            "suggested_label": s.suggested_label,
            "detected_position": pos,
            "camera_bbox": cbbox,
            "confidence": s.confidence,
            "drift_distance": s.drift_distance,
            "status": s.status,
            "review_notes": s.review_notes,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
        })
    return out


@router.post("/floor-plan/suggestions/{suggestion_id}/action")
def update_suggestion_action(
    suggestion_id: str,
    payload: SuggestionActionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Owner/Manager review action on an AI suggestion:
    APPROVE | REJECT | IGNORE | EDIT
    """
    require_permission("camera.configuration", current_user, db)
    s = db.execute(select(FloorPlanSuggestion).where(FloorPlanSuggestion.id == suggestion_id)).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Suggestion not found")

    action = payload.action.upper()
    if action not in ("APPROVE", "REJECT", "IGNORE", "EDIT"):
        raise HTTPException(400, "Action must be APPROVE, REJECT, IGNORE, or EDIT")

    if action == "APPROVE":
        s.status = "APPROVED"
    elif action == "REJECT":
        s.status = "REJECTED"
    elif action == "IGNORE":
        s.status = "IGNORED"
    elif action == "EDIT":
        s.status = "APPROVED"
        if payload.edited_data:
            current_pos = json.loads(s.detected_position) if s.detected_position else {}
            s.detected_position = json.dumps({**current_pos, **payload.edited_data})

    s.reviewed_by = current_user.id
    s.reviewed_at = datetime.now(timezone.utc)
    if payload.review_notes:
        s.review_notes = payload.review_notes

    db.commit()
    db.refresh(s)
    return {"id": s.id, "status": s.status, "message": f"Suggestion {action} successfully"}


@router.post("/floor-plan/apply")
def apply_approved_floor_plan(
    payload: ApplySuggestionsPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    One-click transactional application of all approved AI suggestions to the official FOH floor plan.
    Creates an atomic version snapshot and audit logs.
    Rolls back completely if any table update fails.
    """
    require_permission("camera.configuration", current_user, db)
    tenant_id = getattr(current_user, "tenant_id", None) or "org-demo"

    result = floor_plan_ai_service.apply_approved_suggestions(
        db=db,
        floor_id=payload.floor_id,
        suggestion_ids=payload.suggestion_ids,
        user_id=current_user.id,
        tenant_id=tenant_id,
        replace_existing_layout=payload.replace_existing,
    )
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Failed to apply floor plan updates"))

    return result


@router.post("/floor-plan/clear")
def clear_floor_plan(
    payload: FloorPlanClearPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Clears all tables from a floor plan so a clean digital layout can be reconstructed from scratch.
    """
    require_permission("camera.configuration", current_user, db)
    try:
        res = floor_plan_ai_service.clear_floor_tables(
            db=db,
            floor_id=payload.floor_id,
            user_id=current_user.id,
        )
        return res
    except Exception as e:
        raise HTTPException(500, f"Failed to clear floor plan: {str(e)}")


@router.post("/floor-plan/reconstruct")
def reconstruct_floor_plan(
    payload: FloorPlanReconstructPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    1-Click direct reconstruction pipeline:
    Analyzes the video, removes old tables, and creates real tables matching the video layout.
    """
    require_permission("camera.configuration", current_user, db)
    try:
        res = floor_plan_ai_service.reconstruct_floor_plan_from_video(
            db=db,
            camera_id=payload.camera_id,
            floor_id=payload.floor_id,
            stream_url=payload.override_stream_url,
            source_type=payload.source_type or "RTSP",
            min_confidence=payload.min_confidence,
            replace_old=payload.replace_existing,
            user_id=current_user.id,
        )
        return res
    except Exception as e:
        raise HTTPException(500, f"Floor plan reconstruction failed: {str(e)}")


@router.get("/floor-plan/drift")
def get_floor_plan_drift(
    floor_id: str,
    camera_id: str,
    drift_threshold: float = 40.0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Evaluates systematic physical-to-digital floor plan drift (Section 29).
    """
    require_permission("camera.view", current_user, db)
    return floor_plan_ai_service.detect_floor_plan_drift(
        db=db,
        floor_id=floor_id,
        camera_id=camera_id,
        drift_threshold=drift_threshold,
    )


@router.get("/floor-plan/versions")
def list_floor_plan_versions(
    floor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    View floor plan version history snapshots.
    """
    require_permission("camera.view", current_user, db)
    versions = db.execute(
        select(FloorPlanVersion)
        .where(FloorPlanVersion.floor_id == floor_id)
        .order_by(desc(FloorPlanVersion.version_number))
    ).scalars().all()

    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "created_by": v.created_by,
            "change_summary": v.change_summary,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "table_count": len(json.loads(v.layout_snapshot)) if v.layout_snapshot else 0,
        }
        for v in versions
    ]


# ── Vision Model Benchmarking ────────────────────────────────────────────────

@router.post("/benchmark")
def run_model_benchmark(
    payload: BenchmarkRunPayload,
    current_user: User = Depends(get_current_user),
):
    """
    Benchmark YOLO11 against custom table-state model on real restaurant footage.
    Measures Precision, Recall, mAP, FPS, inference latency, false positive/negative rates.
    """
    require_permission("camera.configuration", current_user)
    report = run_vision_benchmark(
        sample_frames=payload.sample_frames,
        video_filename=payload.video_source or "table_t-1.mp4",
    )
    return report
