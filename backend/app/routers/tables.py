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
from app.models import Table, TableQRCode
from app.models.session import DiningSession
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


def resolve_table_and_qr(db: Session, identifier: str) -> tuple[Table, TableQRCode]:
    """
    Finds a table by ID or Number (e.g. 'tbl-90ee5c90', '1', 'T1', 'tbl-1') and
    guarantees an active TableQRCode exists.
    If the requested table was deleted due to a floor-plan layout change, gracefully
    resolves to the matching table number or first available active table so QR links never fail.
    """
    table = db.query(Table).filter(Table.id == identifier).first()
    if not table:
        table = db.query(Table).filter(Table.number == identifier).first()
    if not table:
        clean = identifier.replace("tbl-", "").replace("table-", "").lstrip("Tt ")
        table = db.query(Table).filter(
            (Table.number == clean)
            | (Table.number == f"T{clean}")
            | (Table.number == f"Table {clean}")
        ).first()
    if not table:
        # Fallback to first table on active floor
        table = db.query(Table).order_by(Table.number.asc()).first()
    if not table:
        # Create default Table 1 if floor is completely empty
        table = Table(
            id=new_id(),
            floor_id="floor-1",
            number="1",
            capacity=4,
            status="AVAILABLE",
            x=100.0,
            y=100.0,
            width=85.0,
            height=85.0,
            shape="SQUARE",
        )
        db.add(table)
        db.commit()
        db.refresh(table)

    qr = (
        db.query(TableQRCode)
        .filter(TableQRCode.table_id == table.id, TableQRCode.is_active.is_(True))
        .first()
    )
    if not qr:
        token = f"t{table.number}".lower().replace(" ", "").replace("-", "")
        existing = db.query(TableQRCode).filter(TableQRCode.token == token).first()
        if existing:
            existing.table_id = table.id
            existing.is_active = True
            qr = existing
        else:
            qr = TableQRCode(
                id=new_id(),
                table_id=table.id,
                token=token,
                is_active=True,
            )
            db.add(qr)
        db.commit()
        db.refresh(qr)

    return table, qr


@router.get("/by-number/{table_number}/qr")
def table_qr_by_number_page(table_number: str, db: Session = Depends(get_db)) -> HTMLResponse:
    return table_qr_page(table_number, db)


@router.get("/{table_id}/qr")
def table_qr_page(table_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    table, qr = resolve_table_and_qr(db, table_id)

    # Permanent URL identified by table number so layout changes never break the physical QR
    guest_url = f"{settings.guest_menu_base_url}/guest/menu?table={table.number}&token={qr.token}"
    qr_img = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={quote(guest_url)}"

    # Get other floor tables for quick switching / printing
    all_tables = (
        db.query(Table)
        .filter(Table.floor_id == table.floor_id)
        .order_by(Table.number.asc())
        .all()
    )
    options_html = "".join(
        f'<option value="{t.id}" {"selected" if t.id == table.id else ""}>Table {t.number}</option>'
        for t in all_tables
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Table {table.number} QR Code — FOH Restaurant</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --primary: #0f172a;
      --accent: #2563eb;
      --gold: #d97706;
      --border: #e2e8f0;
      --text: #1e293b;
      --muted: #64748b;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}
    .no-print-toolbar {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
      background: #ffffff;
      padding: 10px 16px;
      border-radius: 12px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.06);
      border: 1px solid var(--border);
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.15s ease;
      border: 1px solid transparent;
    }}
    .btn-primary {{
      background: #0f172a;
      color: #ffffff;
    }}
    .btn-primary:hover {{
      background: #1e293b;
    }}
    .btn-outline {{
      background: #ffffff;
      color: #334155;
      border-color: var(--border);
    }}
    .btn-outline:hover {{
      background: #f1f5f9;
    }}
    select {{
      padding: 8px 12px;
      border-radius: 8px;
      border: 1px solid var(--border);
      font-family: inherit;
      font-size: 13px;
      color: #334155;
      outline: none;
    }}
    .stand-card {{
      background: var(--card-bg);
      width: 100%;
      max-width: 420px;
      border-radius: 20px;
      border: 2px solid #0f172a;
      box-shadow: 0 20px 40px -15px rgba(15,23,42,0.12);
      text-align: center;
      padding: 36px 32px;
      position: relative;
    }}
    .restaurant-brand {{
      font-size: 11px;
      letter-spacing: 2px;
      text-transform: uppercase;
      font-weight: 700;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .table-badge {{
      display: inline-block;
      background: #0f172a;
      color: #ffffff;
      font-family: 'Fraunces', serif;
      font-size: 28px;
      font-weight: 700;
      padding: 6px 24px;
      border-radius: 100px;
      margin-bottom: 20px;
      letter-spacing: -0.02em;
    }}
    .qr-frame {{
      display: inline-block;
      padding: 16px;
      background: #ffffff;
      border: 2px solid #0f172a;
      border-radius: 16px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.06);
      margin-bottom: 20px;
    }}
    .qr-frame img {{
      display: block;
      width: 240px;
      height: 240px;
      border-radius: 6px;
    }}
    .instructions {{
      font-size: 15px;
      font-weight: 600;
      color: #0f172a;
      margin-bottom: 6px;
    }}
    .sub-instructions {{
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 16px;
    }}
    .url-box {{
      font-family: monospace;
      font-size: 11px;
      color: #64748b;
      word-break: break-all;
      background: #f8fafc;
      padding: 8px 12px;
      border-radius: 8px;
      border: 1px solid var(--border);
    }}
    .footer-pill {{
      margin-top: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      font-size: 11px;
      font-weight: 600;
      color: #0f172a;
    }}
    .footer-pill span {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }}
    @media print {{
      body {{
        background: #ffffff;
        padding: 0;
        margin: 0;
      }}
      .no-print-toolbar {{
        display: none !important;
      }}
      .stand-card {{
        border: 2px solid #000000;
        box-shadow: none;
        max-width: 100%;
        margin: auto;
        page-break-inside: avoid;
      }}
    }}
  </style>
</head>
<body>
  <div class="no-print-toolbar">
    <button class="btn btn-primary" onclick="window.print()">🖨️ Print Stand</button>
    <a href="{guest_url}" target="_blank" class="btn btn-outline">🍽️ Test Menu</a>
    <select onchange="window.location.href='/tables/' + this.value + '/qr'">
      {options_html}
    </select>
  </div>

  <div class="stand-card">
    <div class="restaurant-brand">FOH Enterprise Dining</div>
    <div class="table-badge">TABLE {table.number}</div>

    <div class="qr-frame">
      <img src="{qr_img}" alt="Table {table.number} QR Code" width="240" height="240" />
    </div>

    <div class="instructions">📱 Scan with Phone Camera</div>
    <div class="sub-instructions">Browse live menu · Place orders · Pay from table</div>

    <div class="url-box">{guest_url}</div>

    <div class="footer-pill">
      <span>⚡ Instant Kitchen Sync</span>
      <span>•</span>
      <span>💳 UPI / Card / Cash</span>
    </div>
  </div>
</body>
</html>"""
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

