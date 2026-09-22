"""
Billing Router — Normal restaurant billing (no AI).
Workflow: Session → Bill (DRAFT/OPEN) → READY_FOR_PAYMENT → PAID
"""
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_current_user_optional, require_permission
from app.core.ids import new_id
from app.core.permissions import (
    PERM_BILLING_CANCEL,
    PERM_BILLING_CREATE,
    PERM_BILLING_UPDATE,
    PERM_BILLING_VIEW,
    PERM_DISCOUNT_APPLY,
    PERM_PAYMENT_CREATE,
    normalize_role,
)
from app.database import get_db
from app.models import Bill, DiningSession, Order, OrderItem, Payment, ServiceCharge, TaxRule, User
from app.models.cashier_shift import CashierShift
from app.schemas.billing import BillingSummary, DiscountIn, DiscountOut, RuleIn
from app.schemas.common import CamelModel
from app.services.billing_service import apply_discount, calculate_bill, list_bills
from app.services.audit_service import log_action
from app.socket_manager import emit_sync

router = APIRouter(prefix="/billing", tags=["billing"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class BillItemOut(CamelModel):
    name: str
    quantity: int
    unit_price: float
    subtotal: float


class BillDetailOut(CamelModel):
    id: str
    bill_number: str | None
    session_id: str | None
    table_number: str | None
    items: list[BillItemOut]
    subtotal: float
    discount_amount: float
    discount_reason: str | None
    service_charge_amount: float
    tax_amount: float
    total: float
    status: str
    created_by: str | None
    created_by_name: str | None
    generated_at: str
    paid_at: str | None
    notes: str | None
    upi_qr_payload: str | None = None
    tax_rate: float | None = 5.0
    service_charge_rate: float | None = 10.0


class ReadySessionItemOut(BaseModel):
    name: str
    quantity: int
    unit_price: float
    subtotal: float


class ReadySessionOut(BaseModel):
    session_id: str
    table_id: str
    table_number: str
    guest_name: str | None
    party_size: int
    started_at: str
    order_count: int
    items: list[ReadySessionItemOut]
    subtotal: float
    estimated_tax: float
    estimated_service_charge: float
    estimated_total: float
    has_bill: bool
    bill_id: str | None = None


class CreateBillIn(BaseModel):
    session_id: str
    notes: str | None = None


class ProcessPaymentIn(BaseModel):
    method: str  # CASH | CARD | UPI | QR | ONLINE
    amount: float
    transaction_id: str | None = None
    shift_id: str | None = None


class PaymentOut(BaseModel):
    payment_id: str
    bill_id: str
    method: str
    amount: float
    payment_status: str
    transaction_id: str | None
    paid_at: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _next_bill_number(db: Session, tenant_id: str) -> str:
    """Generate sequential bill number like B1001, B1002, ..."""
    count = db.query(Bill).filter(Bill.tenant_id == tenant_id).count()
    return f"B{1000 + count + 1}"


def _bill_items_from_session(db: Session, bill: Bill) -> list[BillItemOut]:
    """Collect all order items for a session or bill with clean display names and accurate rates."""
    from app.models import MenuItem
    orders = []
    if bill.session_id:
        orders = db.query(Order).filter(Order.session_id == bill.session_id).all()
    elif bill.order_id:
        single_ord = db.get(Order, bill.order_id)
        if single_ord:
            orders = [single_ord]

    items = []
    for order in orders:
        for oi in order.items:
            item_title = getattr(oi, "item_name", None) or getattr(oi, "menu_item_name", None)
            if not item_title or item_title.strip() == "" or item_title == str(oi.menu_item_id):
                mi = db.get(MenuItem, oi.menu_item_id)
                item_title = mi.name if mi else "Dish Item"
            qty = int(oi.quantity)
            rate = float(oi.unit_price)
            line_sub = round(qty * rate, 2)
            items.append(
                BillItemOut(
                    name=item_title,
                    quantity=qty,
                    unit_price=rate,
                    subtotal=line_sub,
                )
            )

    return items


def _bill_detail_out(bill: Bill, db: Session) -> BillDetailOut:
    from app.models.user import User as U
    creator = db.get(U, bill.created_by) if bill.created_by else None

    # Get table number from session
    table_number = None
    if bill.session_id:
        session = db.get(DiningSession, bill.session_id)
        if session:
            from app.models.table import Table
            table = db.get(Table, session.table_id)
            if table:
                table_number = table.number

    # Collect actual order items
    items = _bill_items_from_session(db, bill)

    # If the bill is not yet paid, keep subtotal and totals 100% aligned with actual order items
    if (bill.status or bill.bill_status or "") != "PAID":
        if items:
            computed_items_subtotal = Decimal(str(round(sum(i.subtotal for i in items), 2)))
            bill.subtotal = computed_items_subtotal
        calculate_bill(db, bill)
        db.commit()
        db.refresh(bill)

    bill_no = bill.bill_number or f"B{bill.id[:6]}"
    total_val = float(bill.total or 0)
    upi_payload = f"upi://pay?pa=foh.dining@icici&pn=FOH+Fine+Dining&am={total_val:.2f}&cu=INR&tn=Bill-{bill_no}"

    return BillDetailOut(
        id=bill.id,
        bill_number=bill.bill_number,
        session_id=bill.session_id,
        table_number=table_number,
        items=items,
        subtotal=float(bill.subtotal or 0),
        discount_amount=float(bill.discount_amount or 0),
        discount_reason=bill.discount_reason,
        service_charge_amount=float(bill.service_charge_amount or 0),
        tax_amount=float(bill.tax_amount or 0),
        total=total_val,
        status=bill.bill_status or bill.status or "OPEN",
        created_by=bill.created_by,
        created_by_name=creator.name if creator else None,
        generated_at=bill.generated_at.isoformat(),
        paid_at=bill.paid_at.isoformat() if bill.paid_at else None,
        notes=bill.notes,
        upi_qr_payload=upi_payload,
        tax_rate=5.0,
        service_charge_rate=10.0,
    )


def _out(b: Bill) -> BillingSummary:
    return BillingSummary(
        id=b.id,
        session_id=b.session_id or "",
        subtotal=float(b.subtotal or 0),
        discount_amount=float(b.discount_amount or 0),
        service_charge_amount=float(b.service_charge_amount or 0),
        tax_amount=float(b.tax_amount or 0),
        total=float(b.total or 0),
        status=b.bill_status or b.status or "OPEN",
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/ready-sessions", response_model=list[ReadySessionOut])
def list_ready_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_BILLING_VIEW)),
):
    """List all active dining sessions with their order items ready for billing."""
    sessions = (
        db.query(DiningSession)
        .filter(
            DiningSession.tenant_id == user.tenant_id,
            DiningSession.closed_at.is_(None),
            DiningSession.status.notin_(["PAID", "CLEANING", "COMPLETED"]),
        )
        .all()
    )
    result = []
    for s in sessions:
        from app.models.table import Table
        tbl = db.get(Table, s.table_id)
        tbl_num = tbl.number if tbl else s.table_id.replace("t-", "")

        orders = db.query(Order).filter(Order.session_id == s.id).all()
        items_list = []
        subtotal = 0.0
        for o in orders:
            for oi in o.items:
                item_title = getattr(oi, "item_name", None) or getattr(oi, "menu_item_name", None) or str(oi.menu_item_id)
                qty = int(oi.quantity)
                unit_price = float(oi.unit_price)
                line_subtotal = round(qty * unit_price, 2)
                subtotal += line_subtotal
                items_list.append(
                    ReadySessionItemOut(
                        name=item_title,
                        quantity=qty,
                        unit_price=unit_price,
                        subtotal=line_subtotal,
                    )
                )

        existing_bill = db.query(Bill).filter(Bill.session_id == s.id).first()

        if existing_bill and subtotal == 0 and float(existing_bill.subtotal or 0) > 0:
            subtotal = float(existing_bill.subtotal)
            est_tax = float(existing_bill.tax_amount or 0)
            est_svc = float(existing_bill.service_charge_amount or 0)
            est_total = float(existing_bill.total or 0)
        else:
            est_tax = round(subtotal * 0.05, 2)
            est_svc = round(subtotal * 0.10, 2)
            est_total = round(subtotal + est_tax + est_svc, 2)

        result.append(
            ReadySessionOut(
                session_id=s.id,
                table_id=s.table_id,
                table_number=str(tbl_num),
                guest_name=s.guest_name,
                party_size=int(s.party_size or 2),
                started_at=s.seated_at.isoformat() if s.seated_at else datetime.now(timezone.utc).isoformat(),
                order_count=len(orders),
                items=items_list,
                subtotal=round(subtotal, 2),
                estimated_tax=est_tax,
                estimated_service_charge=est_svc,
                estimated_total=est_total,
                has_bill=existing_bill is not None,
                bill_id=existing_bill.id if existing_bill else None,
            )
        )
    return result


@router.get("/bills", response_model=list[BillingSummary])
def bills(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_BILLING_VIEW)),
):
    """List bills scoped by tenant/branch."""
    all_bills = list_bills(db, user)
    return [_out(b) for b in all_bills]


@router.post("/bills", response_model=BillDetailOut, status_code=201)
def create_bill(
    body: CreateBillIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_BILLING_CREATE)),
):
    """Create a bill for a dining session. Calculates totals from order items."""
    # Validate session
    session = (
        db.query(DiningSession)
        .filter(
            DiningSession.id == body.session_id,
            DiningSession.tenant_id == user.tenant_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Prevent duplicate bills - if existing, calculate and return refreshed bill
    existing = db.query(Bill).filter(Bill.session_id == body.session_id).first()
    if existing:
        calculate_bill(db, existing)
        db.commit()
        db.refresh(existing)
        return _bill_detail_out(existing, db)

    # Calculate subtotal from order items
    orders = db.query(Order).filter(Order.session_id == body.session_id).all()
    subtotal = Decimal("0")
    for order in orders:
        for oi in order.items:
            subtotal += Decimal(str(oi.quantity)) * Decimal(str(oi.unit_price))

    now = datetime.now(timezone.utc)
    bill = Bill(
        id=new_id(),
        bill_number=_next_bill_number(db, user.tenant_id),
        session_id=body.session_id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
        created_by=user.id,
        subtotal=subtotal,
        discount_amount=Decimal("0"),
        service_charge_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        total=subtotal,
        status="OPEN",
        bill_status="OPEN",
        generated_at=now,
        notes=body.notes,
    )
    db.add(bill)
    db.flush()
    # Apply tax/service charge rules
    calculate_bill(db, bill)
    db.commit()
    db.refresh(bill)

    log_action(db, user.id, user.tenant_id, user.branch_id, "BILL_CREATED", "bill", bill.id,
               new_value={"bill_number": bill.bill_number, "total": float(bill.total)})
    emit_sync("bill.created", {"billId": bill.id, "billNumber": bill.bill_number,
                               "total": float(bill.total), "sessionId": body.session_id},
              room=user.tenant_id)
    return _bill_detail_out(bill, db)


@router.get("/bills/{bill_id}", response_model=BillDetailOut)
def get_bill(
    bill_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Get full bill details including itemized breakdown. Supports staff POS and guest table-pay."""
    query = db.query(Bill).filter(Bill.id == bill_id)
    if user and user.tenant_id:
        query = query.filter(Bill.tenant_id == user.tenant_id)
    bill = query.first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if user and user.branch_id and bill.branch_id and bill.branch_id != user.branch_id:
        raise HTTPException(status_code=404, detail="Bill not found")
    return _bill_detail_out(bill, db)


@router.post("/bills/{bill_id}/pay", response_model=PaymentOut)
def process_payment(
    bill_id: str,
    body: ProcessPaymentIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Process payment for a bill. Prevents duplicate payments via unique constraint."""
    valid_methods = {"CASH", "CARD", "UPI", "QR", "ONLINE"}
    method_upper = body.method.upper()
    if method_upper not in valid_methods:
        raise HTTPException(status_code=422, detail=f"Invalid payment method. Use one of: {', '.join(valid_methods)}")

    query = db.query(Bill).filter(Bill.id == bill_id)
    if user and user.tenant_id:
        query = query.filter(Bill.tenant_id == user.tenant_id)
    bill = query.with_for_update().first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if (bill.status or bill.bill_status or "") in ("PAID",):
        raise HTTPException(status_code=409, detail="Bill is already paid")
    if (bill.status or bill.bill_status or "") in ("CANCELLED", "REFUNDED"):
        raise HTTPException(status_code=409, detail=f"Cannot pay a {bill.status} bill")

    tenant_id = user.tenant_id if user else bill.tenant_id
    branch_id = user.branch_id if user else bill.branch_id
    user_id = user.id if user else (bill.created_by or "system-guest")

    # Verify method is enabled in dynamic settings
    from app.services.configuration_service import get_config
    payment_cfg = get_config(db, tenant_id, "payment_methods", branch_id)
    if not payment_cfg.get(method_upper, True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment method {method_upper} is currently disabled."
        )

    # Validate payment amount (must match bill total within 1 rupee tolerance)
    expected = float(bill.total or 0)
    pay_amount = expected if (body.amount is None or body.amount <= 0) else body.amount
    if abs(pay_amount - expected) > 1.0:
        raise HTTPException(
            status_code=422,
            detail=f"Payment amount ₹{pay_amount:.2f} does not match bill total ₹{expected:.2f}",
        )

    # Prevent duplicate payment
    existing_payment = db.query(Payment).filter(Payment.bill_id == bill_id).first()
    if existing_payment and existing_payment.payment_status == "SUCCESS":
        raise HTTPException(status_code=409, detail="Duplicate payment: this bill is already paid")

    now = datetime.now(timezone.utc)
    payment = Payment(
        id=new_id(),
        bill_id=bill_id,
        tenant_id=tenant_id,
        branch_id=branch_id,
        method=method_upper,
        amount=Decimal(str(round(pay_amount, 2))),
        transaction_id=body.transaction_id,
        payment_status="SUCCESS",
        created_by=user_id,
        paid_at=now,
        completed_at=now,
        shift_id=body.shift_id,
    )
    db.add(payment)

    # Mark bill paid
    bill.status = "PAID"
    bill.bill_status = "PAID"
    bill.paid_at = now

    # Find active cashier shift to credit this payment
    shift = None
    if body.shift_id:
        shift = db.get(CashierShift, body.shift_id)
    if not shift:
        shift = (
            db.query(CashierShift)
            .filter(CashierShift.tenant_id == tenant_id, CashierShift.status == "OPEN")
            .order_by(CashierShift.opened_at.desc())
            .first()
        )
    if shift and shift.status == "OPEN":
        payment.shift_id = shift.id
        method_map = {
            "CASH":   "cash_sales",
            "CARD":   "card_sales",
            "UPI":    "upi_sales",
            "QR":     "qr_sales",
            "ONLINE": "online_sales",
        }
        col = method_map.get(method_upper)
        if col:
            current_val = Decimal(str(getattr(shift, col) or 0))
            setattr(shift, col, current_val + payment.amount)
        if bill.discount_amount and Decimal(str(bill.discount_amount)) > 0:
            current_disc = Decimal(str(shift.discount_total or 0))
            shift.discount_total = current_disc + Decimal(str(bill.discount_amount))

    # Close the dining session and set table to CLEANING
    if bill.session_id:
        from app.models import DiningSession, Table
        from app.services.table_service import record_history, _table_to_out
        session = db.get(DiningSession, bill.session_id)
        if session:
            session.status = "COMPLETED"
            session.closed_at = now
            table = db.get(Table, session.table_id)
            if table:
                old_status = table.status
                table.status = "CLEANING"
                record_history(db, table.id, old_status, "CLEANING", user_id, session.id)
                tbl_payload = _table_to_out(table).model_dump(by_alias=True)
                emit_sync("table_updated", tbl_payload, room=str(table.floor_id))
                emit_sync("table:updated", tbl_payload, room=str(table.floor_id))
                if tenant_id and tenant_id != str(table.floor_id):
                    emit_sync("table_updated", tbl_payload, room=tenant_id)

    db.commit()
    db.refresh(payment)

    log_action(db, user_id, tenant_id, branch_id, "PAYMENT_COMPLETED", "payment", payment.id,
               new_value={"method": method_upper, "amount": float(payment.amount), "bill_id": bill_id})
    emit_sync("payment.updated", {
        "billId": bill_id,
        "paymentId": payment.id,
        "status": "SUCCESS",
        "method": method_upper,
        "amount": float(payment.amount),
    }, room=tenant_id)

    return PaymentOut(
        payment_id=payment.id,
        bill_id=bill_id,
        method=payment.method,
        amount=float(payment.amount),
        payment_status=payment.payment_status,
        transaction_id=payment.transaction_id,
        paid_at=payment.paid_at.isoformat(),
    )


@router.post("/bills/{bill_id}/cancel")
def cancel_bill(
    bill_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_BILLING_CANCEL)),
):
    """Cancel a bill. Only allowed for OPEN/DRAFT bills."""
    bill = db.query(Bill).filter(Bill.id == bill_id, Bill.tenant_id == user.tenant_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if (bill.status or "") in ("PAID",):
        raise HTTPException(status_code=409, detail="Paid bills cannot be cancelled directly. Submit a refund request.")
    if (bill.status or "") in ("CANCELLED",):
        raise HTTPException(status_code=409, detail="Bill is already cancelled")

    old_status = bill.status
    bill.status = "CANCELLED"
    bill.bill_status = "CANCELLED"
    db.commit()

    log_action(db, user.id, user.tenant_id, user.branch_id, "BILL_CANCELLED", "bill", bill.id,
               old_value={"status": old_status}, new_value={"status": "CANCELLED"})
    return {"ok": True, "bill_id": bill_id, "status": "CANCELLED"}


@router.post("/bills/{bill_id}/discount", response_model=DiscountOut)
def discount(
    bill_id: str,
    payload: DiscountIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_DISCOUNT_APPLY)),
):
    return apply_discount(db, bill_id, payload, user)


@router.post("/tax-rules")
def tax_rule(
    payload: RuleIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_BILLING_UPDATE)),
):
    row = TaxRule(
        id=new_id(), tenant_id=user.tenant_id, branch_id=user.branch_id,
        name=payload.name, rate=payload.rate, created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    return row


@router.post("/service-charges")
def service_charge(
    payload: RuleIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_BILLING_UPDATE)),
):
    row = ServiceCharge(
        id=new_id(), tenant_id=user.tenant_id, branch_id=user.branch_id,
        name=payload.name, rate=payload.rate, created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    return row
