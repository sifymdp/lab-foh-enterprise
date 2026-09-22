from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_reservations_access
from app.database import get_db
from app.models.user import User
from app.schemas.reservation import ReservationCreate, ReservationOut
from app.services import reservation_service

router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.get("", response_model=list[ReservationOut])
def list_reservations(
    db: Session = Depends(get_db),
    user: User = Depends(require_reservations_access),
) -> list[ReservationOut]:
    return reservation_service.list_reservations(db, user.tenant_id, user.branch_id)


@router.post("", response_model=ReservationOut)
def create_reservation(
    body: ReservationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_reservations_access),
) -> ReservationOut:
    return reservation_service.create_reservation(db, body, user.id, user.tenant_id, user.branch_id)


@router.post("/{reservation_id}/release", response_model=ReservationOut)
def release_reservation(
    reservation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_reservations_access),
) -> ReservationOut:
    return reservation_service.release_reservation(db, reservation_id, user.id, user.tenant_id, user.branch_id)


@router.delete("/{reservation_id}", status_code=204)
def delete_reservation(
    reservation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_reservations_access),
) -> None:
    reservation_service.delete_reservation(db, reservation_id, user.id, user.tenant_id, user.branch_id)
