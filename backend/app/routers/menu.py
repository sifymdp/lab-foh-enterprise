from io import BytesIO
import json
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_menu_manager
from app.database import get_db
from app.models import MenuItem, User
from app.models.menu_bulk import MenuImport, MenuImportItem, MenuVersion
from app.schemas.menu import MenuItemCreate, MenuItemOut, MenuItemUpdate
from app.schemas.menu_bulk import (
    MenuApproveIn,
    MenuChangeLogOut,
    MenuImportDetailOut,
    MenuImportItemOut,
    MenuImportSummaryOut,
    MenuVersionOut,
)
from app.services import menu_excel_service, menu_service

router = APIRouter(prefix="/menu", tags=["menu"])


@router.get("", response_model=list[MenuItemOut])
def list_public_menu(
    branch_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[MenuItemOut]:
    return menu_service.list_available(db, branch_id=branch_id)


@router.get("/all", response_model=list[MenuItemOut])
def list_all_menu(
    branch_id: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MenuItemOut]:
    effective_branch = branch_id or user.branch_id
    return menu_service.list_all(db, branch_id=effective_branch)


@router.post("/items", response_model=MenuItemOut)
def create_menu_item(
    body: MenuItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_menu_manager),
) -> MenuItemOut:
    return menu_service.create_item(db, body, tenant_id=user.tenant_id, branch_id=user.branch_id)


@router.patch("/items/{item_id}", response_model=MenuItemOut)
def update_menu_item(
    item_id: str,
    body: MenuItemUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_menu_manager),
) -> MenuItemOut:
    return menu_service.update_item(db, item_id, body)


@router.delete("/items/{item_id}", status_code=204)
def delete_menu_item(
    item_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_menu_manager),
) -> None:
    menu_service.delete_item(db, item_id)


@router.patch("/items/{item_id}/toggle", response_model=MenuItemOut)
def toggle_menu_item(
    item_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_menu_manager),
) -> MenuItemOut:
    return menu_service.toggle_item(db, item_id)


# ─── Bulk Excel Operations ───────────────────────────────────────────────────


@router.get("/export/template")
def download_menu_template(
    _user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Download blank Excel template for bulk menu editing and addition."""
    buf = menu_excel_service.generate_menu_template()
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="restaurant_menu_template.xlsx"'},
    )


@router.get("/export/current")
def download_current_menu(
    branch_id: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_menu_manager),
) -> StreamingResponse:
    """Download the current active menu as an Excel file, scoped to authorized branch."""
    effective_branch = branch_id or user.branch_id
    buf = menu_excel_service.export_current_menu(
        db, tenant_id=user.tenant_id, branch_id=effective_branch
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="current_menu_{timestamp}.xlsx"'},
    )


@router.post("/import/upload", response_model=MenuImportSummaryOut)
async def upload_menu_excel(
    file: UploadFile = File(...),
    branch_id: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_menu_manager),
) -> MenuImportSummaryOut:
    """Upload and analyze a menu Excel file without touching live items."""
    fname = file.filename or "menu.xlsx"
    if not (fname.lower().endswith(".xlsx") or fname.lower().endswith(".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only Excel spreadsheets (.xlsx, .xls) are allowed.",
        )

    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum allowed limit (15MB).",
        )

    effective_branch = branch_id or user.branch_id
    try:
        import_rec = menu_excel_service.parse_and_analyze_excel(
            db=db,
            file_bytes=content,
            file_name=fname,
            user=user,
            tenant_id=user.tenant_id,
            branch_id=effective_branch,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err)) from val_err

    return _to_import_summary(import_rec)


@router.get("/import/history", response_model=list[MenuImportSummaryOut])
def list_import_history(
    db: Session = Depends(get_db),
    user: User = Depends(require_menu_manager),
) -> list[MenuImportSummaryOut]:
    """Retrieve history of all menu Excel imports."""
    q = db.query(MenuImport)
    if user.tenant_id:
        q = q.filter((MenuImport.tenant_id == user.tenant_id) | (MenuImport.tenant_id.is_(None)))
    if user.branch_id:
        q = q.filter((MenuImport.branch_id == user.branch_id) | (MenuImport.branch_id.is_(None)))
    rows = q.order_by(MenuImport.created_at.desc()).limit(50).all()
    return [_to_import_summary(r) for r in rows]


@router.get("/import/{import_id}/analysis", response_model=MenuImportSummaryOut)
def get_import_analysis(
    import_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_menu_manager),
) -> MenuImportSummaryOut:
    """Get high-level summary counters for an uploaded import."""
    rec = db.get(MenuImport, import_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu import not found")
    return _to_import_summary(rec)


@router.get("/import/{import_id}/preview", response_model=MenuImportDetailOut)
def get_import_preview(
    import_id: str,
    filter_action: str | None = Query(None, alias="filter"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_menu_manager),
) -> MenuImportDetailOut:
    """Get categorized row-by-row preview with diffs and missing items."""
    rec = db.get(MenuImport, import_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu import not found")

    q = db.query(MenuImportItem).filter(MenuImportItem.import_id == import_id)
    if filter_action and filter_action.upper() != "ALL":
        filt = filter_action.upper()
        if filt == "WARNINGS":
            q = q.filter(MenuImportItem.status == "WARNING")
        elif filt == "ERRORS":
            q = q.filter(MenuImportItem.status == "ERROR")
        else:
            q = q.filter(MenuImportItem.action == filt)

    items = q.order_by(MenuImportItem.row_number).all()

    # Load missing items if present
    missing_items: list[MenuItemOut] = []
    if rec.raw_data_json:
        try:
            m_ids = json.loads(rec.raw_data_json)
            if m_ids:
                m_rows = db.query(MenuItem).filter(MenuItem.id.in_(m_ids)).all()
                missing_items = [menu_service._to_out(m) for m in m_rows]
        except Exception:
            missing_items = []

    item_outs = [
        MenuImportItemOut(
            id=i.id,
            rowNumber=i.row_number,
            itemCode=i.item_code,
            itemName=i.item_name,
            category=i.category,
            action=i.action,
            status=i.status,
            errorMessage=i.error_message,
            warningMessage=i.warning_message,
            similarityMatch=i.similarity_match,
            similarityScore=i.similarity_score,
            oldValues=json.loads(i.old_values) if i.old_values else None,
            newValues=json.loads(i.new_values) if i.new_values else None,
        )
        for i in items
    ]

    return MenuImportDetailOut(
        summary=_to_import_summary(rec),
        items=item_outs,
        missingItems=missing_items,
    )


@router.post("/import/{import_id}/approve", response_model=MenuVersionOut)
def approve_import(
    import_id: str,
    body: MenuApproveIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_menu_manager),
) -> MenuVersionOut:
    """Approve and atomically apply the menu import to live floor & POS."""
    try:
        version_rec = menu_excel_service.approve_menu_import(
            db=db,
            import_id=import_id,
            deactivate_missing=bool(getattr(body, "deactivate_missing", getattr(body, "deactivateMissing", False))),
            user=user,
            notes=body.notes,
        )
    except PermissionError as p_err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(p_err)) from p_err
    except ValueError as v_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(v_err)) from v_err

    return _to_version_out(version_rec)


@router.post("/import/{import_id}/reject", status_code=204)
def reject_import(
    import_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_menu_manager),
) -> None:
    """Reject an import without modifying live menu items."""
    try:
        menu_excel_service.reject_menu_import(db, import_id, user)
    except ValueError as v_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(v_err)) from v_err


@router.get("/import/{import_id}/error-report")
def download_error_report(
    import_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_menu_manager),
) -> StreamingResponse:
    """Download an Excel report containing all invalid rows and suggested fixes."""
    rec = db.get(MenuImport, import_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu import not found")

    buf = menu_excel_service.generate_error_report(rec)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="import_errors_{rec.id[:8]}.xlsx"'},
    )


@router.get("/import/{import_id}/report")
def download_import_report(
    import_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_menu_manager),
) -> StreamingResponse:
    """Download a multi-sheet audit Excel report for this import."""
    rec = db.get(MenuImport, import_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu import not found")

    buf = menu_excel_service.generate_import_report(rec)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="menu_import_report_{rec.id[:8]}.xlsx"'},
    )


# ─── Menu Versioning ─────────────────────────────────────────────────────────


@router.get("/versions", response_model=list[MenuVersionOut])
def list_menu_versions(
    db: Session = Depends(get_db),
    user: User = Depends(require_menu_manager),
) -> list[MenuVersionOut]:
    """List historical immutable versions of the restaurant menu."""
    q = db.query(MenuVersion)
    if user.tenant_id:
        q = q.filter((MenuVersion.tenant_id == user.tenant_id) | (MenuVersion.tenant_id.is_(None)))
    if user.branch_id:
        q = q.filter((MenuVersion.branch_id == user.branch_id) | (MenuVersion.branch_id.is_(None)))
    rows = q.order_by(MenuVersion.version_number.desc()).limit(30).all()
    return [_to_version_out(r) for r in rows]


@router.get("/versions/{version_id}", response_model=MenuVersionOut)
def get_menu_version_detail(
    version_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_menu_manager),
) -> MenuVersionOut:
    rec = db.get(MenuVersion, version_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu version not found")
    return _to_version_out(rec)


# ─── Private Helpers ─────────────────────────────────────────────────────────


def _to_import_summary(rec: MenuImport) -> MenuImportSummaryOut:
    uploader_name = rec.uploader.name if rec.uploader else None
    approver_name = rec.approver.name if rec.approver else None
    return MenuImportSummaryOut(
        id=rec.id,
        fileName=rec.file_name,
        status=rec.status,
        totalRows=rec.total_rows,
        newCount=rec.new_count,
        updatedCount=rec.updated_count,
        unchangedCount=rec.unchanged_count,
        errorCount=rec.error_count,
        warningCount=rec.warning_count,
        deactivatedCount=rec.deactivated_count,
        createdAt=rec.created_at.isoformat() if rec.created_at else "",
        approvedAt=rec.approved_at.isoformat() if rec.approved_at else None,
        uploadedBy=uploader_name,
        approvedBy=approver_name,
    )


def _to_version_out(rec: MenuVersion) -> MenuVersionOut:
    creator_name = rec.creator.name if rec.creator else None
    return MenuVersionOut(
        id=rec.id,
        versionNumber=rec.version_number,
        versionTag=rec.version_tag,
        createdAt=rec.created_at.isoformat() if rec.created_at else "",
        createdBy=rec.created_by,
        creatorName=creator_name,
        totalItems=rec.total_items,
        newItemsCount=rec.new_items_count,
        updatedItemsCount=rec.updated_items_count,
        deactivatedItemsCount=rec.deactivated_items_count,
        notes=rec.notes,
    )

