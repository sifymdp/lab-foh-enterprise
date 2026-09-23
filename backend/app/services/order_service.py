from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.core.status_machine import is_valid_transition
from app.models import Bill, DiningSession, MenuItem, Order, OrderItem, Table
from app.schemas.order import BillOut, OrderCreate, OrderItemOut, OrderOut
from app.services.floor_service import _table_to_out
from app.services.table_service import (
    _on_status_change,
    active_session_for_table,
    get_table,
    record_history,
)
from app.socket_manager import emit_sync


def _fmt_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat().replace("+00:00", "Z")


def _order_to_out(order: Order, db: Session | None = None) -> OrderOut:
    table_num = None
    if getattr(order, "table", None):
        table_num = order.table.number
    elif db and order.table_id:
        t = db.get(Table, order.table_id)
        if t:
            table_num = t.number

    return OrderOut(
        id=order.id,
        session_id=order.session_id,
        table_id=order.table_id,
        table_number=str(table_num) if table_num is not None else None,
        placed_at=_fmt_dt(order.placed_at),
        status=order.status,
        source=getattr(order, "source", "bot") or "bot",
        approval_status=getattr(order, "approval_status", "PENDING") or "PENDING",
        notes=getattr(order, "notes", None),
        items=[
            OrderItemOut(
                id=i.id,
                item_name=i.item_name,
                unit_price=float(i.unit_price),
                quantity=i.quantity,
                station=getattr(i, "station", None),
                notes=getattr(i, "notes", None),
                allergy_flag=bool(getattr(i, "allergy_flag", False)),
                item_status=getattr(i, "item_status", "RECEIVED") or "RECEIVED",
            )
            for i in order.items
        ],
    )


def _emit_table_updated(table: Table) -> None:
    emit_sync("table_updated", _table_to_out(table).model_dump(by_alias=True), room=table.floor_id)


def list_orders(
    db: Session,
    table_id: str | None = None,
    session_id: str | None = None,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> list[OrderOut]:
    q = db.query(Order)
    if tenant_id:
        q = q.filter(Order.tenant_id == tenant_id)
    if branch_id:
        q = q.filter(Order.branch_id == branch_id)
    if table_id:
        q = q.filter(Order.table_id == table_id)
    if session_id:
        q = q.filter(Order.session_id == session_id)
    rows = q.order_by(Order.placed_at.desc()).all()
    return [_order_to_out(o) for o in rows]


def create_order(
    db: Session,
    payload: OrderCreate,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> OrderOut:
    table_q = db.query(Table).filter(Table.id == payload.table_id)
    if tenant_id:
        table_q = table_q.filter(Table.tenant_id == tenant_id)
    if branch_id:
        table_q = table_q.filter(Table.branch_id == branch_id)
    table = table_q.first()
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    now = datetime.now(timezone.utc)
    session = None
    if payload.session_id:
        session_q = db.query(DiningSession).filter(DiningSession.id == payload.session_id)
        if tenant_id:
            session_q = session_q.filter(DiningSession.tenant_id == tenant_id)
        if branch_id:
            session_q = session_q.filter(DiningSession.branch_id == branch_id)
        session = session_q.first()
    if not session:
        session = active_session_for_table(db, payload.table_id)
    if not session:
        # Auto-initialize active dining session for the table so orders succeed immediately
        session = DiningSession(
            id=new_id(),
            table_id=table.id,
            tenant_id=table.tenant_id,
            branch_id=table.branch_id,
            guest_name=payload.notes or f"Guest Table {table.number}",
            party_size=table.capacity or 2,
            status="ACTIVE",
            seated_at=now,
        )
        db.add(session)
        table.status = "ACTIVE"
        db.flush()
        record_history(db, table.id, table.status, "ACTIVE", None, session.id)

    if not payload.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order must include items")
    is_guest = getattr(payload, "source", None) in ("bot", "guest", "qr") or payload.source is None
    approval = payload.approval_status or ("PENDING" if is_guest else "APPROVED")
    order = Order(
        id=new_id(),
        session_id=session.id,
        table_id=payload.table_id,
        tenant_id=table.tenant_id,
        branch_id=table.branch_id,
        placed_at=now,
        status="RECEIVED",
        source=payload.source or ("guest" if is_guest else "waiter"),
        approval_status=approval,
        notes=payload.notes,
    )
    db.add(order)
    db.flush()

    for line in payload.items:
        menu_item = db.get(MenuItem, str(line.menu_item_id))
        if not menu_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Menu item not found: {line.menu_item_id}")
        db.add(
            OrderItem(
                id=new_id(),
                order_id=order.id,
                menu_item_id=menu_item.id,
                item_name=menu_item.name,
                unit_price=float(menu_item.price),
                quantity=line.quantity,
            )
        )

    if table.status == "SEATED" and is_valid_transition("SEATED", "ACTIVE"):
        old = table.status
        table.status = "ACTIVE"
        session.status = "ACTIVE"
        record_history(db, table.id, old, "ACTIVE", None, session.id)

    db.commit()
    db.refresh(order)
    db.refresh(table)

    item_count = sum(line.quantity for line in payload.items)
    total_amount = round(
        sum(float(i.unit_price) * i.quantity for i in order.items),
        2,
    )
    emit_sync(
        "order_placed",
        {
            "tableId": table.id,
            "tableNumber": table.number,
            "floorId": table.floor_id,
            "itemCount": item_count,
            "totalAmount": total_amount,
            "approvalStatus": order.approval_status,
        },
        room=str(table.floor_id),
    )
    if order.approval_status == "PENDING":
        emit_sync(
            "order.pending_approval",
            {
                "orderId": order.id,
                "tableId": table.id,
                "tableNumber": table.number,
                "itemCount": item_count,
                "totalAmount": total_amount,
                "notes": order.notes,
            },
            room=str(table.floor_id),
        )
    _emit_table_updated(table)
    return _order_to_out(order, db=db)


def approve_order(db: Session, order_id: str, user_id: str | None = None) -> OrderOut:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.approval_status = "APPROVED"
    db.commit()
    db.refresh(order)

    table = db.get(Table, order.table_id)
    floor_id = str(table.floor_id) if table else "floor-1"

    emit_sync(
        "order.approved",
        {
            "orderId": order.id,
            "tableId": order.table_id,
            "tableNumber": table.number if table else None,
            "approvalStatus": "APPROVED",
        },
        room=floor_id,
    )
    emit_sync("order.status.changed", {"orderId": order.id, "newStatus": order.status}, room=floor_id)
    emit_sync("kitchen_order_new", {"orderId": order.id, "tableNumber": table.number if table else None}, room=floor_id)
    return _order_to_out(order, db=db)


def reject_order(db: Session, order_id: str, reason: str | None = None, user_id: str | None = None) -> OrderOut:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.approval_status = "REJECTED"
    order.status = "REJECTED"
    if reason:
        order.notes = reason
    db.commit()
    db.refresh(order)

    table = db.get(Table, order.table_id)
    floor_id = str(table.floor_id) if table else "floor-1"

    emit_sync(
        "order.rejected",
        {
            "orderId": order.id,
            "tableId": order.table_id,
            "tableNumber": table.number if table else None,
            "approvalStatus": "REJECTED",
            "reason": order.notes,
        },
        room=floor_id,
    )
    emit_sync("order.status.changed", {"orderId": order.id, "newStatus": "REJECTED"}, room=floor_id)
    return _order_to_out(order, db=db)


def request_bill(
    db: Session,
    session_id: str,
    user_id: str | None,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> BillOut:
    session_q = db.query(DiningSession).filter(DiningSession.id == session_id)
    if tenant_id:
        session_q = session_q.filter(DiningSession.tenant_id == tenant_id)
    if branch_id:
        session_q = session_q.filter(DiningSession.branch_id == branch_id)
    session = session_q.first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    table = get_table(db, session.table_id, tenant_id, branch_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    existing_q = db.query(Bill).filter(Bill.session_id == session_id)
    if tenant_id:
        existing_q = existing_q.filter(Bill.tenant_id == tenant_id)
    if branch_id:
        existing_q = existing_q.filter(Bill.branch_id == branch_id)
    existing = existing_q.first()
    if existing:
        return get_bill(db, session_id, tenant_id, branch_id)

    items: list[OrderItem] = []
    for order in session.orders:
        items.extend(order.items)

    from decimal import Decimal
    from app.services.billing_service import calculate_bill

    subtotal = Decimal(str(sum(float(i.unit_price) * i.quantity for i in items))) if items else Decimal("0")
    now = datetime.now(timezone.utc)
    count = db.query(Bill).filter(Bill.tenant_id == table.tenant_id).count()
    bill_no = f"B{1000 + count + 1}"

    bill = Bill(
        id=new_id(),
        bill_number=bill_no,
        session_id=session_id,
        tenant_id=table.tenant_id,
        branch_id=table.branch_id,
        created_by=user_id,
        subtotal=subtotal,
        discount_amount=Decimal("0"),
        service_charge_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        total=subtotal,
        generated_at=now,
        status="OPEN",
        bill_status="OPEN",
    )
    db.add(bill)
    db.flush()
    calculate_bill(db, bill)
    session.requested_bill_at = now

    if is_valid_transition(table.status, "BILLING"):
        old = table.status
        table.status = "BILLING"
        session.status = "BILLING"
        record_history(db, table.id, old, "BILLING", user_id, session.id)

    db.commit()
    db.refresh(bill)
    db.refresh(table)
    _emit_table_updated(table)
    return get_bill(db, session_id, tenant_id, branch_id)


def get_bill(
    db: Session,
    session_id: str,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> BillOut:
    q = db.query(Bill).filter(Bill.session_id == session_id)
    if tenant_id:
        q = q.filter(Bill.tenant_id == tenant_id)
    if branch_id:
        q = q.filter(Bill.branch_id == branch_id)
    bill = q.first()
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")

    session_q = db.query(DiningSession).filter(DiningSession.id == session_id)
    if tenant_id:
        session_q = session_q.filter(DiningSession.tenant_id == tenant_id)
    if branch_id:
        session_q = session_q.filter(DiningSession.branch_id == branch_id)
    session = session_q.first()
    line_items = []
    for order in session.orders if session else []:
        for item in order.items:
            line_items.append(
                {
                    "item_name": item.item_name,
                    "unit_price": float(item.unit_price),
                    "quantity": item.quantity,
                    "line_total": round(float(item.unit_price) * item.quantity, 2),
                }
            )

    from app.schemas.order import BillItemOut

    return BillOut(
        id=bill.id,
        session_id=bill.session_id,
        subtotal=float(bill.subtotal),
        total=float(bill.total),
        status=bill.status,
        generated_at=_fmt_dt(bill.generated_at),
        paid_at=_fmt_dt(bill.paid_at) if bill.paid_at else None,
        items=[BillItemOut(**li) for li in line_items],
    )


def mark_paid(
    db: Session,
    session_id: str,
    user_id: str | None,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> BillOut:
    session_q = db.query(DiningSession).filter(DiningSession.id == session_id)
    if tenant_id:
        session_q = session_q.filter(DiningSession.tenant_id == tenant_id)
    if branch_id:
        session_q = session_q.filter(DiningSession.branch_id == branch_id)
    session = session_q.first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    bill_q = db.query(Bill).filter(Bill.session_id == session_id)
    if tenant_id:
        bill_q = bill_q.filter(Bill.tenant_id == tenant_id)
    if branch_id:
        bill_q = bill_q.filter(Bill.branch_id == branch_id)
    bill = bill_q.first()
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    table = get_table(db, session.table_id, tenant_id, branch_id)
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    now = datetime.now(timezone.utc)
    bill.status = "PAID"
    bill.paid_at = now

    if is_valid_transition(table.status, "PAID"):
        old = table.status
        table.status = "PAID"
        session.status = "PAID"
        _on_status_change(table, old, "PAID")
        record_history(db, table.id, old, "PAID", user_id, session.id)

    if is_valid_transition(table.status, "CLEANING"):
        old = table.status
        table.status = "CLEANING"
        session.status = "CLEANING"
        # resets counters/alert flags and stamps cleaning_started_at, which
        # starts the 10/20-minute dirty-alert clock for this cleaning cycle
        _on_status_change(table, old, "CLEANING")
        record_history(db, table.id, old, "CLEANING", user_id, session.id)

    db.commit()
    db.refresh(bill)
    db.refresh(table)

    bill_out = get_bill(db, session_id, tenant_id, branch_id)
    emit_sync("payment_confirmed", bill_out.model_dump(by_alias=True), room=table.floor_id)
    _emit_table_updated(table)
    return bill_out
