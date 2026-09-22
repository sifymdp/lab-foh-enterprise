import shutil
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.config import settings
from app.core import camera_utils
from app.core.yolo_models import detect_table_state_consensus, iter_full_frame_detections
from app.core.deps import get_current_user, require_floor_editor, require_permission
from app.core.ids import new_id
from app.database import get_db
from app.models import TableQRCode
from app.models.user import User
from app.schemas.floor import CreateTableIn, StatusPatchIn, TableOut, TablePatchIn
from app.schemas.roi import (
    CameraRoiSuggestionOut,
    CameraSceneDetectionOut,
    CameraSnapshotAnalysisIn,
    CameraSnapshotAnalysisOut,
)
from app.services.roi_autodetect import suggest_camera_roi
from app.services import table_service

router = APIRouter(prefix="/tables", tags=["tables"])

# Directory where uploaded camera videos are stored
CAMERA_UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "camera_uploads"
CAMERA_UPLOADS_DIR.mkdir(exist_ok=True)


def _roi_to_ints(roi: dict | None) -> dict[str, int] | None:
    if roi is None:
        return None
    return {
        "x": int(round(roi["x"])),
        "y": int(round(roi["y"])),
        "width": int(round(roi["width"])),
        "height": int(round(roi["height"])),
    }


def _intersection_area(a: dict[str, int], b: dict[str, int]) -> int:
    left = max(a["x"], b["x"])
    top = max(a["y"], b["y"])
    right = min(a["x"] + a["width"], b["x"] + b["width"])
    bottom = min(a["y"] + a["height"], b["y"] + b["height"])
    if right <= left or bottom <= top:
        return 0
    return (right - left) * (bottom - top)


def _resolve_roi_label_from_scene(
    roi: dict[str, int] | None,
    scene_detections: list[CameraSceneDetectionOut],
) -> tuple[str | None, float | None]:
    if roi is None:
        return None, None

    roi_area = max(roi["width"] * roi["height"], 1)
    best_label: str | None = None
    best_score = 0.0
    best_confidence: float | None = None

    for detection in scene_detections:
        bounds = {
            "x": int(round(detection.bounds.x)),
            "y": int(round(detection.bounds.y)),
            "width": int(round(detection.bounds.width)),
            "height": int(round(detection.bounds.height)),
        }
        overlap_ratio = _intersection_area(roi, bounds) / roi_area
        if overlap_ratio < 0.18:
            continue
        score = overlap_ratio * float(detection.confidence)
        if score > best_score:
            best_score = score
            best_label = detection.label
            best_confidence = float(detection.confidence)

    return best_label, best_confidence


@router.get("/{table_id}/qr")
def table_qr_page(table_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    qr = (
        db.query(TableQRCode)
        .filter(TableQRCode.table_id == table_id, TableQRCode.is_active.is_(True))
        .first()
    )
    if not qr:
        raise HTTPException(404, "QR code not found for table")
    guest_url = f"{settings.guest_menu_base_url}/guest/menu?token={qr.token}"
    qr_img = f"https://api.qrserver.com/v1/create-qr-code/?size=240x240&data={quote(guest_url)}"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Table QR</title>
<style>
  body {{ font-family: system-ui, sans-serif; text-align: center; padding: 40px; }}
  img {{ border: 8px solid #111; border-radius: 8px; }}
  p {{ color: #555; margin-top: 16px; word-break: break-all; }}
</style></head>
<body>
  <h1>Scan to order</h1>
  <img src="{qr_img}" alt="QR code" width="240" height="240" />
  <p>{guest_url}</p>
</body></html>"""
    return HTMLResponse(html)


@router.get("/{table_id}/camera/snapshot")
def camera_snapshot(
    table_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_floor_editor),
) -> Response:
    """Grab one still frame from this table's camera so the ROI tool has something to draw on."""
    table = table_service.get_table(db, table_id, user.tenant_id, user.branch_id)
    if not table.camera_url:
        raise HTTPException(404, "This table has no camera_url configured yet")

    frame = camera_utils.capture_frame(table.camera_url)
    if frame is None:
        raise HTTPException(502, "Could not read a frame from that camera_url")

    jpeg_bytes = camera_utils.encode_jpeg(frame)
    return Response(content=jpeg_bytes, media_type="image/jpeg")


@router.post("/{table_id}/camera/auto-roi", response_model=CameraRoiSuggestionOut)
def auto_roi_suggestion(
    table_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_floor_editor),
) -> CameraRoiSuggestionOut:
    """Sample a pre-recorded camera source and suggest a stable ROI."""
    table = table_service.get_table(db, table_id, user.tenant_id, user.branch_id)
    if not table.camera_url:
        raise HTTPException(404, "This table has no camera_url configured yet")

    try:
        suggestion = suggest_camera_roi(table.camera_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CameraRoiSuggestionOut(**suggestion)


@router.post("/{table_id}/camera/analyze-snapshot", response_model=CameraSnapshotAnalysisOut)
def analyze_camera_snapshot(
    table_id: str,
    body: CameraSnapshotAnalysisIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_floor_editor),
) -> CameraSnapshotAnalysisOut:
    """Run table-state analysis on one captured snapshot.

    Uses the caller-provided ROI when present so the setup page can preview
    draft lassos before saving, while still returning a whole-scene summary.
    """
    table = table_service.get_table(db, table_id, user.tenant_id, user.branch_id)
    if not table.camera_url:
        raise HTTPException(404, "This table has no camera_url configured yet")

    frames = camera_utils.capture_frame_sequence(
        table.camera_url,
        sample_frames=settings.table_state_sample_frames,
        frame_stride=settings.table_state_sample_stride,
    )
    if not frames:
        raise HTTPException(502, "Could not read a frame from that camera_url")

    frame = frames[-1]
    frame_height, frame_width = frame.shape[:2]
    roi_used = _roi_to_ints(
        body.roi_coords.model_dump() if body.roi_coords is not None else camera_utils.parse_roi(table.roi_coords)
    )

    scene_detections = []
    scene_summary = {"clean": 0, "dirty": 0, "occupied": 0}
    for x1, y1, x2, y2, detection in iter_full_frame_detections(frame):
        scene_summary[detection.label] = scene_summary.get(detection.label, 0) + 1
        scene_detections.append(
            CameraSceneDetectionOut(
                label=detection.label,
                confidence=detection.confidence,
                bounds={
                    "x": x1,
                    "y": y1,
                    "width": max(x2 - x1, 1),
                    "height": max(y2 - y1, 1),
                },
            )
        )

    roi_label: str | None = None
    roi_confidence: float | None = None
    if roi_used is not None:
        cropped_frames = [
            cropped
            for cropped in (camera_utils.crop_roi(sampled_frame, roi_used) for sampled_frame in frames)
            if cropped is not None
        ]
        if cropped_frames:
            roi_detection = detect_table_state_consensus(cropped_frames)
            if roi_detection is None:
                roi_label = "clean"
                roi_confidence = 0.0
            else:
                roi_label = roi_detection.label
                roi_confidence = roi_detection.confidence

        scene_label, scene_confidence = _resolve_roi_label_from_scene(roi_used, scene_detections)
        if scene_label is not None:
            if roi_label is None or roi_label == "clean" or (
                scene_label == "occupied" and (roi_confidence or 0.0) < scene_confidence
            ):
                roi_label = scene_label
                roi_confidence = scene_confidence

    return CameraSnapshotAnalysisOut(
        frame_width=frame_width,
        frame_height=frame_height,
        roi_used=roi_used,
        roi_label=roi_label,
        roi_confidence=roi_confidence,
        scene_summary=scene_summary,
        scene_detections=scene_detections,
    )


@router.post("/{table_id}/camera/upload")
def upload_camera_video(
    table_id: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(require_floor_editor),
) -> dict:
    """Upload a video file to use as the camera source for this table."""
    table = table_service.get_table(db, table_id, user.tenant_id, user.branch_id)

    # Save the file to disk
    suffix = Path(file.filename or "video.mp4").suffix or ".mp4"
    dest = CAMERA_UPLOADS_DIR / f"table_{table_id}{suffix}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Update the table's camera_url to point to the saved file
    file_path = str(dest.resolve())
    table.camera_url = file_path
    db.commit()

    return {"cameraUrl": file_path, "filename": file.filename}


@router.post("/{table_id}/qr/rotate")
def rotate_table_qr(
    table_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_floor_editor),
) -> dict:
    table_service.get_table(db, table_id, user.tenant_id, user.branch_id)

    active_codes = (
        db.query(TableQRCode)
        .filter(TableQRCode.table_id == table_id, TableQRCode.is_active.is_(True))
        .all()
    )
    for qr in active_codes:
        qr.is_active = False

    new_token = new_id()
    db.add(TableQRCode(id=new_id(), table_id=table_id, token=new_token, is_active=True))
    db.commit()

    return {"token": new_token, "message": "QR token rotated"}


@router.post("", response_model=TableOut)
def create_table(
    body: CreateTableIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_floor_editor),
) -> TableOut:
    return table_service.add_table(db, body, user.tenant_id, user.branch_id)


@router.put("/{table_id}", response_model=TableOut)
def update_table(
    table_id: str,
    body: TablePatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TableOut:
    return table_service.update_table(db, table_id, body, user.tenant_id, user.branch_id)


@router.patch("/{table_id}/status", response_model=TableOut)
def patch_status(
    table_id: str,
    body: StatusPatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TableOut:
    return table_service.patch_table_status(db, table_id, body.status, user.id, user.tenant_id, user.branch_id)


@router.delete("/{table_id}", status_code=204)
def remove_table(
    table_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_floor_editor),
) -> None:
    table_service.delete_table(db, table_id, user.tenant_id, user.branch_id)


class TableAssignmentIn(BaseModel):
    staff_id: str


@router.post("/{table_id}/assign")
def assign_table_staff(
    table_id: str,
    body: TableAssignmentIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tables.assign"))
):
    from app.models.staff_table_assignment import StaffTableAssignment
    from app.core.ids import new_id
    from datetime import datetime, timezone
    
    # Check if table exists
    from app.models.table import Table
    tbl = db.query(Table).filter(Table.id == table_id, Table.tenant_id == user.tenant_id).first()
    if not tbl:
        raise HTTPException(status_code=404, detail="Table not found")
        
    # Remove existing assignment if any
    db.query(StaffTableAssignment).filter(
        StaffTableAssignment.table_id == table_id,
        StaffTableAssignment.tenant_id == user.tenant_id
    ).delete()
    
    now = datetime.now(timezone.utc)
    assignment = StaffTableAssignment(
        id=new_id(),
        staff_id=body.staff_id,
        table_id=table_id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
        assigned_by=user.id,
        assigned_at=now
    )
    db.add(assignment)
    db.commit()
    return {"ok": True}


@router.get("/assignments")
def get_table_assignments(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tables.view"))
):
    from app.models.staff_table_assignment import StaffTableAssignment
    from app.core.deps import get_user_branches
    q = db.query(StaffTableAssignment).filter(StaffTableAssignment.tenant_id == user.tenant_id)
    allowed_branches = get_user_branches(db, user)
    if allowed_branches is not None:
        q = q.filter(StaffTableAssignment.branch_id.in_(allowed_branches))
        
    assignments = q.all()
    res = []
    for a in assignments:
        u = db.query(User).filter(User.id == a.staff_id).first()
        res.append({
            "id": a.id,
            "tableId": a.table_id,
            "staffId": a.staff_id,
            "staffName": u.name if u else "Unknown",
            "assignedBy": a.assigned_by,
            "assignedAt": a.assigned_at.isoformat()
        })
    return res

