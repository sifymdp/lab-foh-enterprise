"""
Revenue & Financial Reporting Router
Provides daily summaries, payment-method breakdowns, cashier-wise totals,
and branch performance. No AI — pure aggregation.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.permissions import (
    PERM_REVENUE_VIEW_ALL,
    PERM_REVENUE_VIEW_BRANCH,
    PERM_REVENUE_VIEW_OWN,
    normalize_role,
)
from app.database import get_db
from app.models import Bill, Payment, User
from app.models.cashier_shift import CashierShift

router = APIRouter(prefix="/revenue", tags=["revenue"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class PaymentMethodSummary(BaseModel):
    cash: float
    card: float
    upi: float
    qr: float
    online: float
    total: float


class DailyRevenueSummary(BaseModel):
    date: str
    total_bills: int
    paid_bills: int
    pending_bills: int
    cancelled_bills: int
    refunded_bills: int
    gross_revenue: float
    discount_total: float
    tax_total: float
    service_charge_total: float
    net_revenue: float
    payment_methods: PaymentMethodSummary


class CashierSummary(BaseModel):
    cashier_id: str
    cashier_name: str
    bills_count: int
    total_amount: float


# ── Helpers ───────────────────────────────────────────────────────────────────

def _payment_method_totals(db: Session, tenant_id: str, branch_id: str | None,
                            cashier_id: str | None, date_filter: date | None) -> PaymentMethodSummary:
    q = db.query(Payment).filter(
        Payment.tenant_id == tenant_id,
        Payment.payment_status == "SUCCESS",
    )
    if branch_id:
        q = q.filter(Payment.branch_id == branch_id)
    if cashier_id:
        q = q.filter(Payment.created_by == cashier_id)
    if date_filter:
        start = datetime(date_filter.year, date_filter.month, date_filter.day, tzinfo=timezone.utc)
        from datetime import timedelta
        end = start + timedelta(days=1)
        q = q.filter(Payment.paid_at >= start, Payment.paid_at < end)

    payments = q.all()
    totals = {"CASH": 0.0, "CARD": 0.0, "UPI": 0.0, "QR": 0.0, "ONLINE": 0.0}
    for p in payments:
        method = (p.method or "").upper()
        if method in totals:
            totals[method] += float(p.amount or 0)
        # Legacy STRIPE → CARD
        elif method == "STRIPE":
            totals["CARD"] += float(p.amount or 0)

    total = sum(totals.values())
    return PaymentMethodSummary(
        cash=round(totals["CASH"], 2),
        card=round(totals["CARD"], 2),
        upi=round(totals["UPI"], 2),
        qr=round(totals["QR"], 2),
        online=round(totals["ONLINE"], 2),
        total=round(total, 2),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/daily", response_model=DailyRevenueSummary)
def daily_revenue(
    target_date: date | None = Query(None, alias="date"),
    branch_id: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_REVENUE_VIEW_BRANCH)),
):
    """Daily revenue summary for owner/manager."""
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    # Branch isolation: managers can only see their own branch
    effective_branch = user.branch_id
    if normalize_role(user.role) == "OWNER" and branch_id:
        effective_branch = branch_id

    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    from datetime import timedelta
    end = start + timedelta(days=1)

    bills_q = (
        db.query(Bill)
        .filter(
            Bill.tenant_id == user.tenant_id,
            Bill.generated_at >= start,
            Bill.generated_at < end,
        )
    )
    if effective_branch:
        bills_q = bills_q.filter(Bill.branch_id == effective_branch)
    bills = bills_q.all()

    total_bills = len(bills)
    paid_bills      = sum(1 for b in bills if (b.status or b.bill_status or "") in ("PAID",))
    pending_bills   = sum(1 for b in bills if (b.status or b.bill_status or "") in ("OPEN", "READY_FOR_PAYMENT", "DRAFT"))
    cancelled_bills = sum(1 for b in bills if (b.status or b.bill_status or "") in ("CANCELLED",))
    refunded_bills  = sum(1 for b in bills if (b.status or b.bill_status or "") in ("REFUNDED",))

    gross_revenue        = sum(float(b.subtotal or 0) for b in bills if (b.status or "") in ("PAID",))
    discount_total       = sum(float(b.discount_amount or 0) for b in bills)
    tax_total            = sum(float(b.tax_amount or 0) for b in bills)
    service_charge_total = sum(float(b.service_charge_amount or 0) for b in bills)
    net_revenue          = sum(float(b.total or 0) for b in bills if (b.status or "") in ("PAID",))

    methods = _payment_method_totals(db, user.tenant_id, effective_branch, None, target_date)

    return DailyRevenueSummary(
        date=target_date.isoformat(),
        total_bills=total_bills,
        paid_bills=paid_bills,
        pending_bills=pending_bills,
        cancelled_bills=cancelled_bills,
        refunded_bills=refunded_bills,
        gross_revenue=round(gross_revenue, 2),
        discount_total=round(discount_total, 2),
        tax_total=round(tax_total, 2),
        service_charge_total=round(service_charge_total, 2),
        net_revenue=round(net_revenue, 2),
        payment_methods=methods,
    )


@router.get("/payment-methods", response_model=PaymentMethodSummary)
def payment_method_summary(
    target_date: date | None = Query(None, alias="date"),
    branch_id: str | None = Query(None),
    cashier_id: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_REVENUE_VIEW_BRANCH)),
):
    """Payment method breakdown with filters."""
    effective_branch = user.branch_id
    if normalize_role(user.role) == "OWNER" and branch_id:
        effective_branch = branch_id

    # Cashier can only see own data
    effective_cashier = cashier_id
    if normalize_role(user.role) in ("CASHIER",):
        effective_cashier = user.id

    return _payment_method_totals(db, user.tenant_id, effective_branch, effective_cashier, target_date)


@router.get("/own", response_model=PaymentMethodSummary)
def my_revenue(
    target_date: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_REVENUE_VIEW_OWN)),
):
    """Cashier's own payment method summary."""
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()
    return _payment_method_totals(db, user.tenant_id, user.branch_id, user.id, target_date)


@router.get("/cashier", response_model=list[CashierSummary])
def cashier_summary(
    target_date: date | None = Query(None, alias="date"),
    branch_id: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_REVENUE_VIEW_BRANCH)),
):
    """Cashier-wise billing totals for the day."""
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    effective_branch = user.branch_id
    if normalize_role(user.role) == "OWNER" and branch_id:
        effective_branch = branch_id

    from datetime import timedelta
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    q = db.query(Bill).filter(
        Bill.tenant_id == user.tenant_id,
        Bill.generated_at >= start,
        Bill.generated_at < end,
        Bill.created_by.isnot(None),
    )
    if effective_branch:
        q = q.filter(Bill.branch_id == effective_branch)

    bills = q.all()

    by_cashier: dict[str, dict] = {}
    for bill in bills:
        cid = bill.created_by
        if cid not in by_cashier:
            cashier = db.get(User, cid)
            by_cashier[cid] = {
                "cashier_id": cid,
                "cashier_name": cashier.name if cashier else "Unknown",
                "bills_count": 0,
                "total_amount": 0.0,
            }
        by_cashier[cid]["bills_count"] += 1
        if (bill.status or "") in ("PAID",):
            by_cashier[cid]["total_amount"] += float(bill.total or 0)

    return [
        CashierSummary(**v) for v in sorted(
            by_cashier.values(), key=lambda x: x["total_amount"], reverse=True
        )
    ]


@router.get("/shifts", response_model=list[dict])
def shift_summary(
    target_date: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_REVENUE_VIEW_BRANCH)),
):
    """Manager/Owner: list cashier shift summaries."""
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()
    from datetime import timedelta
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    q = db.query(CashierShift).filter(
        CashierShift.tenant_id == user.tenant_id,
        CashierShift.opened_at >= start,
        CashierShift.opened_at < end,
    )
    if user.branch_id and normalize_role(user.role) != "OWNER":
        q = q.filter(CashierShift.branch_id == user.branch_id)

    result = []
    for s in q.all():
        cashier = db.get(User, s.cashier_id)
        result.append({
            "shift_id": s.id,
            "cashier_name": cashier.name if cashier else "Unknown",
            "status": s.status,
            "opening_cash": float(s.opening_cash or 0),
            "cash_sales": float(s.cash_sales or 0),
            "expected_cash": float(s.expected_cash or 0) if s.expected_cash else None,
            "actual_cash": float(s.actual_cash or 0) if s.actual_cash else None,
            "difference": float(s.difference or 0) if s.difference else None,
            "opened_at": s.opened_at.isoformat(),
            "closed_at": s.closed_at.isoformat() if s.closed_at else None,
        })
    return result
