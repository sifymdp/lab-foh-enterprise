import json
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.core.status_machine import ACTIVE_SESSION_STATUSES, is_valid_transition
from app.models import DiningSession, StatusHistory, Table
from app.schemas.floor import CreateTableIn, TableOut, TablePatchIn
from app.services.floor_service import get_current_floor, _table_to_out
from app.socket_manager import emit_sync, sio


def _emit_table_updated(table: Table) -> None:
    sio.emit_sync(
        "table_updated",
        {
            "id": table.id,
            "status": table.status,
            "floor_id": table.floor_id,
            "number": table.number,
        },
        room=str(table.floor_id),
    )


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _on_status_change(table: Table, old_status: str, new_status: str) -> None:
    """Reset camera scan counters and edge-triggered alert flags; stamp cleaning start time."""
    if old_status != new_status:
        table.consecutive_person_scans = 0
        table.consecutive_empty_scans = 0
        # Re-arm one-shot alerts: each occurrence of BILLING/CLEANING gets its
        # own alert cycle, so leaving the status resets the flags.
        table.dirty_alert_sent = False
        table.dirty_escalated = False
        table.departure_alert_sent = False
    if new_status == "CLEANING":
        table.cleaning_started_at = _iso_now()
    elif old_status == "CLEANING" and new_status != "CLEANING":
        table.cleaning_started_at = None


def get_table(
    db: Session,
    table_id: str,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> Table:
    q = db.query(Table).filter(Table.id == table_id)
    if tenant_id:
        q = q.filter(Table.tenant_id == tenant_id)
    if branch_id:
        q = q.filter(Table.branch_id == branch_id)
    table = q.first()
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    return table


def active_session_for_table(db: Session, table_id: str) -> DiningSession | None:
    return (
        db.query(DiningSession)
        .filter(
            DiningSession.table_id == table_id,
            DiningSession.closed_at.is_(None),
            DiningSession.status.in_(ACTIVE_SESSION_STATUSES),
        )
        .order_by(DiningSession.seated_at.desc())
        .first()
    )


def record_history(
    db: Session,
    table_id: str,
    from_status: str | None,
    to_status: str,
    user_id: str | None,
    session_id: str | None = None,
) -> None:
    db.add(
        StatusHistory(
            id=new_id(),  # uuid4 — no millisecond collision risk
            table_id=table_id,
            session_id=session_id,
            from_status=from_status,
            to_status=to_status,
            changed_by=user_id,
            changed_at=datetime.now(timezone.utc),
        )
    )


def update_table(
    db: Session,
    table_id: str,
    patch: TablePatchIn,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> TableOut:
    table = get_table(db, table_id, tenant_id, branch_id)
    data = patch.model_dump(exclude_unset=True, by_alias=False)
    old_status = table.status
    if "roi_coords" in data:
        # roi_coords arrives as a dict (or None) from the RectBounds schema field,
        # but the DB column stores it as a JSON string — convert before saving.
        roi = data["roi_coords"]
        if hasattr(roi, "model_dump"):
            roi = roi.model_dump()
        data["roi_coords"] = json.dumps(roi) if roi is not None else None
    for key, val in data.items():
        setattr(table, key, val)
    if "status" in data and data["status"] != old_status:
        _on_status_change(table, old_status, data["status"])
    db.commit()
    db.refresh(table)
    if "status" in data and data["status"] != old_status:
        _emit_table_updated(table)
    return _table_to_out(table)


def patch_table_status(
    db: Session,
    table_id: str,
    new_status: str,
    user_id: str | None,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> TableOut:
    table = get_table(db, table_id, tenant_id, branch_id)
    if not is_valid_transition(table.status, new_status):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid transition from {table.status} to {new_status}",
        )
    session = active_session_for_table(db, table_id)
    if new_status in ("SEATED", "ACTIVE") and not session:
        now = datetime.now(timezone.utc)
        session = DiningSession(
            id=new_id(),
            table_id=table.id,
            tenant_id=table.tenant_id,
            branch_id=table.branch_id,
            host_id=user_id,
            guest_name=f"Guest Table {table.number}",
            party_size=table.capacity or 2,
            status=new_status,
            seated_at=now,
        )
        db.add(session)
        db.flush()

    old = table.status
    table.status = new_status
    _on_status_change(table, old, new_status)
    if session:
        session.status = new_status
        if new_status == "BILLING":
            # Automatically link/create a real Bill record in the billing module
            from app.models.bill import Bill
            from app.models.order import Order
            from app.services.billing_service import calculate_bill
            from decimal import Decimal
            
            now = datetime.now(timezone.utc)
            orders = db.query(Order).filter(Order.session_id == session.id).all()
            subtotal = Decimal("0")
            for order in orders:
                for oi in order.items:
                    subtotal += Decimal(str(oi.quantity)) * Decimal(str(oi.unit_price))
            
            existing_bill = db.query(Bill).filter(Bill.session_id == session.id).first()
            if not existing_bill:
                count = db.query(Bill).filter(Bill.tenant_id == table.tenant_id).count()
                bill_no = f"B{1000 + count + 1}"
                
                existing_bill = Bill(
                    id=new_id(),
                    bill_number=bill_no,
                    session_id=session.id,
                    tenant_id=table.tenant_id,
                    branch_id=table.branch_id,
                    created_by=user_id,
                    subtotal=subtotal,
                    discount_amount=Decimal("0"),
                    service_charge_amount=Decimal("0"),
                    tax_amount=Decimal("0"),
                    total=subtotal,
                    status="OPEN",
                    bill_status="OPEN",
                    generated_at=now,
                )
                db.add(existing_bill)
                db.flush()
            else:
                existing_bill.subtotal = subtotal
                if existing_bill.status != "PAID":
                    existing_bill.status = "OPEN"
                    existing_bill.bill_status = "OPEN"
            
            calculate_bill(db, existing_bill)
            
            emit_sync("bill.created", {
                "billId": existing_bill.id,
                "billNumber": existing_bill.bill_number,
                "total": float(existing_bill.total),
                "sessionId": session.id,
                "tableId": table.id,
                "tableNumber": table.number,
            }, room=table.tenant_id)
        elif new_status == "PAID":
            from app.models.bill import Bill
            existing_bill = db.query(Bill).filter(Bill.session_id == session.id).first()
            if existing_bill and existing_bill.status != "PAID":
                now = datetime.now(timezone.utc)
                existing_bill.status = "PAID"
                existing_bill.bill_status = "PAID"
                existing_bill.paid_at = now

        if new_status not in ACTIVE_SESSION_STATUSES and session.closed_at is None:
            # e.g. staff sends a SEATED table straight back to AVAILABLE —
            # stamp closure so the session doesn't linger open in reports
            session.closed_at = datetime.now(timezone.utc)
    record_history(db, table_id, old, new_status, user_id, session.id if session else None)
    db.commit()
    db.refresh(table)
    _emit_table_updated(table)
    return _table_to_out(table)


def add_table(
    db: Session,
    payload: CreateTableIn,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> TableOut:
    floor = get_current_floor(db, tenant_id, branch_id)
    w = payload.width if payload.width is not None else (64 if payload.shape == "CIRCLE" else 88)
    h = payload.height if payload.height is not None else (64 if payload.shape == "CIRCLE" else 72)
    table = Table(
        id=new_id(),  # uuid4
        floor_id=floor.id,
        tenant_id=floor.tenant_id,
        branch_id=floor.branch_id,
        section_id=payload.section_id,
        number=payload.number,
        capacity=payload.capacity,
        type=payload.type,
        shape=payload.shape,
        status="AVAILABLE",
        x=payload.x if payload.x is not None else 200,
        y=payload.y if payload.y is not None else 200,
        width=w,
        height=h,
        rotation=0,
    )
    db.add(table)
    db.commit()
    db.refresh(table)
    return _table_to_out(table)


def delete_table(
    db: Session,
    table_id: str,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> None:
    if active_session_for_table(db, table_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot remove table with an active session. Release the table first.",
        )
    table = get_table(db, table_id, tenant_id, branch_id)
    db.query(DiningSession).filter(DiningSession.table_id == table_id).delete()
    db.delete(table)
    db.commit()


def change_table_status(
    db: Session,
    table_id: str,
    new_status: str,
    user_id: str | None = None,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> TableOut:
    return patch_table_status(db, table_id, new_status, user_id, tenant_id, branch_id)
