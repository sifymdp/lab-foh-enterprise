"""
Cashier Shift Management Router
Endpoints for starting, ending, and viewing cashier shifts.
"""
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.schemas.common import CamelModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.core.ids import new_id
from app.core.permissions import (
    PERM_SHIFT_END,
    PERM_SHIFT_START,
    PERM_SHIFT_VIEW,
    normalize_role,
)
from app.database import get_db
from app.models import CashierShift, Payment, User
from app.models.user import User as UserModel
from app.services.audit_service import log_action

router = APIRouter(prefix="/cashier-shifts", tags=["cashier-shifts"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class ShiftStartIn(CamelModel):
    opening_cash: float = 0.0
    notes: str | None = None


class ShiftEndIn(CamelModel):
    closing_cash: float
    actual_cash: float
    notes: str | None = None


class ShiftOut(CamelModel):

    id: str
    cashier_id: str
    cashier_name: str
    branch_id: str | None
    opening_cash: float
    closing_cash: float | None
    cash_sales: float
    card_sales: float
    upi_sales: float
    qr_sales: float
    online_sales: float
    refund_total: float
    discount_total: float
    expected_cash: float | None
    actual_cash: float | None
    difference: float | None
    opened_at: str
    closed_at: str | None
    status: str
    notes: str | None


def _shift_out(shift: CashierShift, db: Session) -> ShiftOut:
    cashier = db.get(UserModel, shift.cashier_id)
    return ShiftOut(
        id=shift.id,
        cashier_id=shift.cashier_id,
        cashier_name=cashier.name if cashier else "Unknown",
        branch_id=shift.branch_id,
        opening_cash=float(shift.opening_cash or 0),
        closing_cash=float(shift.closing_cash) if shift.closing_cash is not None else None,
        cash_sales=float(shift.cash_sales or 0),
        card_sales=float(shift.card_sales or 0),
        upi_sales=float(shift.upi_sales or 0),
        qr_sales=float(shift.qr_sales or 0),
        online_sales=float(shift.online_sales or 0),
        refund_total=float(shift.refund_total or 0),
        discount_total=float(shift.discount_total or 0),
        expected_cash=float(shift.expected_cash) if shift.expected_cash is not None else None,
        actual_cash=float(shift.actual_cash) if shift.actual_cash is not None else None,
        difference=float(shift.difference) if shift.difference is not None else None,
        opened_at=shift.opened_at.isoformat(),
        closed_at=shift.closed_at.isoformat() if shift.closed_at else None,
        status=shift.status,
        notes=shift.notes,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start", response_model=ShiftOut)
def start_shift(
    body: ShiftStartIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_SHIFT_START)),
):
    """Cashier starts their shift and declares opening cash."""
    # Only one OPEN shift per cashier at a time
    existing = (
        db.query(CashierShift)
        .filter(
            CashierShift.cashier_id == user.id,
            CashierShift.status == "OPEN",
        )
        .first()
    )
    if existing:
        return _shift_out(existing, db)

    shift = CashierShift(
        id=new_id(),
        cashier_id=user.id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
        opening_cash=Decimal(str(body.opening_cash)),
        opened_at=datetime.now(timezone.utc),
        status="OPEN",
        notes=body.notes,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)

    log_action(db, user.id, user.tenant_id, user.branch_id, "SHIFT_STARTED", "cashier_shift", shift.id)
    return _shift_out(shift, db)


@router.patch("/{shift_id}/end", response_model=ShiftOut)
def end_shift(
    shift_id: str,
    body: ShiftEndIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_SHIFT_END)),
):
    """Cashier closes their shift with actual cash count and reconciliation."""
    shift = db.get(CashierShift, shift_id)
    if not shift or shift.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Shift not found")
    if shift.cashier_id != user.id and normalize_role(user.role) not in ("OWNER", "MANAGER"):
        raise HTTPException(status_code=403, detail="Cannot close another cashier's shift")
    if shift.status == "CLOSED":
        raise HTTPException(status_code=409, detail="Shift is already closed")

    # Compute expected cash: opening + cash sales - cash refunds
    expected = float(shift.opening_cash or 0) + float(shift.cash_sales or 0) - float(shift.refund_total or 0)

    shift.closing_cash = Decimal(str(body.closing_cash))
    shift.actual_cash = Decimal(str(body.actual_cash))
    shift.expected_cash = Decimal(str(round(expected, 2)))
    shift.difference = Decimal(str(round(body.actual_cash - expected, 2)))
    shift.closed_at = datetime.now(timezone.utc)
    shift.status = "CLOSED"
    if body.notes:
        shift.notes = body.notes

    db.commit()
    db.refresh(shift)

    log_action(db, user.id, user.tenant_id, user.branch_id, "SHIFT_CLOSED", "cashier_shift", shift.id)
    return _shift_out(shift, db)


@router.get("/my", response_model=list[ShiftOut])
def my_shifts(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_SHIFT_VIEW)),
):
    """Cashier views their own shifts."""
    shifts = (
        db.query(CashierShift)
        .filter(CashierShift.cashier_id == user.id, CashierShift.tenant_id == user.tenant_id)
        .order_by(CashierShift.opened_at.desc())
        .limit(30)
        .all()
    )
    return [_shift_out(s, db) for s in shifts]


@router.get("/current", response_model=ShiftOut | None)
def current_shift(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_SHIFT_VIEW)),
):
    """Get the currently open shift for the authenticated cashier/terminal."""
    # 1. Check user's own open shift
    shift = (
        db.query(CashierShift)
        .filter(
            CashierShift.cashier_id == user.id,
            CashierShift.tenant_id == user.tenant_id,
            CashierShift.status == "OPEN",
        )
        .first()
    )
    # 2. Check any open shift in the branch
    if not shift and user.branch_id:
        shift = (
            db.query(CashierShift)
            .filter(
                CashierShift.tenant_id == user.tenant_id,
                CashierShift.branch_id == user.branch_id,
                CashierShift.status == "OPEN",
            )
            .order_by(CashierShift.opened_at.desc())
            .first()
        )
    # 3. Check any open shift in tenant
    if not shift:
        shift = (
            db.query(CashierShift)
            .filter(
                CashierShift.tenant_id == user.tenant_id,
                CashierShift.status == "OPEN",
            )
            .order_by(CashierShift.opened_at.desc())
            .first()
        )
    # 4. If none and cashier/manager/owner, auto-open active shift
    if not shift and normalize_role(user.role) in ("CASHIER", "OWNER", "MANAGER"):
        shift = CashierShift(
            id=new_id(),
            cashier_id=user.id,
            tenant_id=user.tenant_id,
            branch_id=user.branch_id,
            opening_cash=Decimal("2000.00"),
            opened_at=datetime.now(timezone.utc),
            status="OPEN",
            notes="Auto-started active shift",
        )
        db.add(shift)
        db.commit()
        db.refresh(shift)
    return _shift_out(shift, db) if shift else None



@router.get("", response_model=list[ShiftOut])
def list_shifts(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_SHIFT_VIEW)),
):
    """Manager/Owner: list all shifts for the branch."""
    q = db.query(CashierShift).filter(CashierShift.tenant_id == user.tenant_id)
    if user.branch_id and normalize_role(user.role) not in ("OWNER",):
        q = q.filter(CashierShift.branch_id == user.branch_id)
    shifts = q.order_by(CashierShift.opened_at.desc()).limit(100).all()
    return [_shift_out(s, db) for s in shifts]
