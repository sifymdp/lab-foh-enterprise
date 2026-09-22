"""
Refund / Approval Request Router
Handles refund requests, discount approvals, and bill-cancellation requests.
Cashier cannot approve their own request (enforced server-side).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.core.ids import new_id
from app.core.permissions import (
    PERM_BILLING_VIEW,
    PERM_PAYMENT_APPROVE,
    PERM_PAYMENT_REFUND,
    normalize_role,
)
from app.database import get_db
from app.models import Bill, Payment, RefundRequest, User
from app.services.audit_service import log_action

router = APIRouter(prefix="/refunds", tags=["refunds"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class RefundRequestIn(BaseModel):
    bill_id: str
    payment_id: str | None = None
    request_type: str = "REFUND"  # REFUND | DISCOUNT | CANCELLATION
    amount: float | None = None
    reason: str


class ApprovalIn(BaseModel):
    resolution_notes: str | None = None


class RefundRequestOut(BaseModel):
    id: str
    bill_id: str
    payment_id: str | None
    request_type: str
    amount: float | None
    reason: str
    status: str
    requested_by: str
    requester_name: str
    approved_by: str | None
    created_at: str
    resolved_at: str | None
    resolution_notes: str | None


def _out(r: RefundRequest, db: Session) -> RefundRequestOut:
    from app.models.user import User as U
    req = db.get(U, r.requested_by)
    return RefundRequestOut(
        id=r.id,
        bill_id=r.bill_id,
        payment_id=r.payment_id,
        request_type=r.request_type,
        amount=float(r.amount) if r.amount is not None else None,
        reason=r.reason,
        status=r.status,
        requested_by=r.requested_by,
        requester_name=req.name if req else "Unknown",
        approved_by=r.approved_by,
        created_at=r.created_at.isoformat(),
        resolved_at=r.resolved_at.isoformat() if r.resolved_at else None,
        resolution_notes=r.resolution_notes,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=RefundRequestOut, status_code=201)
def create_refund_request(
    body: RefundRequestIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_PAYMENT_REFUND)),
):
    """Cashier/staff creates a refund/approval request."""
    # Validate bill exists and belongs to the same tenant
    bill = (
        db.query(Bill)
        .filter(Bill.id == body.bill_id, Bill.tenant_id == user.tenant_id)
        .first()
    )
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    # Prevent duplicate pending requests for the same bill
    existing = (
        db.query(RefundRequest)
        .filter(
            RefundRequest.bill_id == body.bill_id,
            RefundRequest.status == "PENDING",
            RefundRequest.request_type == body.request_type,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="A pending request already exists for this bill")

    req = RefundRequest(
        id=new_id(),
        bill_id=body.bill_id,
        payment_id=body.payment_id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
        requested_by=user.id,
        request_type=body.request_type,
        amount=body.amount,
        reason=body.reason,
        status="PENDING",
        created_at=datetime.now(timezone.utc),
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    log_action(
        db, user.id, user.tenant_id, user.branch_id,
        "REFUND_REQUESTED", "refund_request", req.id,
        new_value={"bill_id": body.bill_id, "type": body.request_type, "amount": body.amount},
    )
    return _out(req, db)


@router.patch("/{request_id}/approve", response_model=RefundRequestOut)
def approve_refund(
    request_id: str,
    body: ApprovalIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_PAYMENT_APPROVE)),
):
    """Manager/Owner approves a refund/approval request.
    Cashier cannot approve their own request.
    """
    req = db.get(RefundRequest, request_id)
    if not req or req.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Request is already {req.status}")

    # Cashier cannot approve their own request
    if req.requested_by == user.id:
        raise HTTPException(
            status_code=403,
            detail="You cannot approve your own request",
        )

    now = datetime.now(timezone.utc)
    req.status = "APPROVED"
    req.approved_by = user.id
    req.resolved_at = now
    req.resolution_notes = body.resolution_notes

    # Apply the refund effect to the bill/payment
    if req.request_type == "REFUND":
        bill = db.get(Bill, req.bill_id)
        if bill:
            bill.status = "REFUNDED"
            bill.bill_status = "REFUNDED"
        if req.payment_id:
            payment = db.get(Payment, req.payment_id)
            if payment:
                payment.payment_status = "REFUNDED"

    elif req.request_type == "CANCELLATION":
        bill = db.get(Bill, req.bill_id)
        if bill:
            bill.status = "CANCELLED"
            bill.bill_status = "CANCELLED"

    elif req.request_type == "DISCOUNT":
        bill = db.get(Bill, req.bill_id)
        if bill:
            from app.models.discount import Discount
            from app.services.billing_service import calculate_bill
            discount = (
                db.query(Discount)
                .filter(Discount.bill_id == bill.id, Discount.status == "PENDING")
                .first()
            )
            if discount:
                discount.status = "APPROVED"
                discount.approved_by = user.id
                bill.discount_amount = round(float(bill.subtotal) * float(discount.percent) / 100, 2)
                bill.discount_reason = discount.reason
                calculate_bill(db, bill)


    db.commit()
    db.refresh(req)

    log_action(
        db, user.id, user.tenant_id, user.branch_id,
        "REFUND_APPROVED", "refund_request", req.id,
    )
    return _out(req, db)


@router.patch("/{request_id}/reject", response_model=RefundRequestOut)
def reject_refund(
    request_id: str,
    body: ApprovalIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_PAYMENT_APPROVE)),
):
    """Manager/Owner rejects a refund/approval request."""
    req = db.get(RefundRequest, request_id)
    if not req or req.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Request is already {req.status}")
    if req.requested_by == user.id:
        raise HTTPException(status_code=403, detail="You cannot reject your own request")

    req.status = "REJECTED"
    req.approved_by = user.id
    req.resolved_at = datetime.now(timezone.utc)
    req.resolution_notes = body.resolution_notes

    if req.request_type == "DISCOUNT":
        from app.models.discount import Discount
        discount = (
            db.query(Discount)
            .filter(Discount.bill_id == req.bill_id, Discount.status == "PENDING")
            .first()
        )
        if discount:
            discount.status = "REJECTED"
            discount.approved_by = user.id


    db.commit()
    db.refresh(req)

    log_action(
        db, user.id, user.tenant_id, user.branch_id,
        "REFUND_REJECTED", "refund_request", req.id,
    )
    return _out(req, db)


@router.get("", response_model=list[RefundRequestOut])
def list_refund_requests(
    req_status: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_BILLING_VIEW)),
):
    """List refund requests. Cashier sees only their own; Manager/Owner sees all."""
    q = db.query(RefundRequest).filter(RefundRequest.tenant_id == user.tenant_id)

    if normalize_role(user.role) in ("CASHIER", "WAITER"):
        q = q.filter(RefundRequest.requested_by == user.id)
    elif user.branch_id and normalize_role(user.role) not in ("OWNER",):
        q = q.filter(RefundRequest.branch_id == user.branch_id)

    if req_status:
        q = q.filter(RefundRequest.status == req_status.upper())

    return [_out(r, db) for r in q.order_by(RefundRequest.created_at.desc()).limit(200).all()]
