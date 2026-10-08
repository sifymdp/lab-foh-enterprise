from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.order import BillOut
from app.schemas.session import DiningSessionOut, SeatGuestIn
from app.services import order_service, session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[DiningSessionOut])
def get_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DiningSessionOut]:
    return session_service.list_sessions(db, user.tenant_id, user.branch_id)


@router.post("/seat", response_model=DiningSessionOut)
def seat(
    body: SeatGuestIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DiningSessionOut:
    return session_service.seat_guest(db, body, user.id, user.tenant_id, user.branch_id)


@router.post("/{session_id}/close", response_model=DiningSessionOut)
def close(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DiningSessionOut:
    return session_service.close_session(db, session_id, user.id, user.tenant_id, user.branch_id)


@router.post("/{session_id}/request-bill", response_model=BillOut)
def request_bill(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BillOut:
    return order_service.request_bill(db, session_id, user.id, user.tenant_id, user.branch_id)


@router.post("/{session_id}/mark-paid", response_model=BillOut)
def mark_paid(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BillOut:
    return order_service.mark_paid(db, session_id, user.id, user.tenant_id, user.branch_id)


@router.get("/{session_id}/bill", response_model=BillOut)
def get_bill(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BillOut:
    return order_service.get_bill(db, session_id, user.tenant_id, user.branch_id)
