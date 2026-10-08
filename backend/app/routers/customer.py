from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_customer_email
from app.schemas.customer import CustomerAvailability, CustomerEmail, CustomerHold, CustomerVerify, CustomerWaitlist
from app.services import customer_service
from app.services.floor_service import floor_to_out, get_current_floor
from app.services.reservation_service import _to_out
from app.models import Reservation
from app.models import CustomerWaitlistEntry
from app.core.ids import new_id
from datetime import datetime, timezone

router = APIRouter(prefix="/customer", tags=["customer booking"])


@router.get("/layout")
def layout(db: Session = Depends(get_db), _email: str = Depends(get_customer_email)):
    return floor_to_out(get_current_floor(db))


@router.post("/auth/request-otp")
def request_otp(body: CustomerEmail, db: Session = Depends(get_db)):
    return customer_service.request_otp(db, body.identity)


@router.post("/auth/verify-otp")
def verify_otp(body: CustomerVerify, db: Session = Depends(get_db)):
    identity = body.contact.strip().lower()
    token, expires = customer_service.verify_otp(db, identity, body.code)
    return {"access_token": token, "token_type": "bearer", "expires_at": expires, "contact": identity}


@router.post("/availability")
def availability(body: CustomerAvailability, db: Session = Depends(get_db), _email: str = Depends(get_customer_email)):
    return customer_service.availability(db, body.requested_date, body.requested_time, body.guests)


@router.post("/holds", response_model=None, status_code=201)
def create_hold(body: CustomerHold, db: Session = Depends(get_db), email: str = Depends(get_customer_email)):
    return _to_out(customer_service.hold(db, email, body.table_id, body.guest_name, body.requested_date, body.requested_time, body.guests))


@router.get("/bookings", response_model=None)
def bookings(db: Session = Depends(get_db), email: str = Depends(get_customer_email)):
    return [_to_out(row) for row in db.query(Reservation).filter(Reservation.customer_email == email).order_by(Reservation.reserved_for.desc()).all()]


@router.post("/bookings/{reservation_id}/confirm", response_model=None)
def confirm(reservation_id: str, db: Session = Depends(get_db), email: str = Depends(get_customer_email)):
    return _to_out(customer_service.confirm(db, email, reservation_id))


@router.post("/bookings/{reservation_id}/cancel", response_model=None)
def cancel(reservation_id: str, db: Session = Depends(get_db), email: str = Depends(get_customer_email)):
    return _to_out(customer_service.cancel(db, email, reservation_id))


@router.post("/waitlist", status_code=201)
def join_waitlist(body: CustomerWaitlist, db: Session = Depends(get_db), email: str = Depends(get_customer_email)):
    requested_for = customer_service._parse_slot(body.requested_date, body.requested_time)
    entry = CustomerWaitlistEntry(id=new_id(), email=email, guest_name=body.guest_name,
        requested_for=requested_for, guests=body.guests, status="WAITING", created_at=datetime.now(timezone.utc))
    db.add(entry)
    db.commit()
    return {"id": entry.id, "status": entry.status, "requested_for": requested_for.isoformat(), "predicted_wait_minutes": 20}
