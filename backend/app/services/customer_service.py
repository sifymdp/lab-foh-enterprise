import hashlib
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.ids import new_id
from app.models import CustomerOTP, Reservation, Table
from app.services.floor_service import _table_to_out
from app.services.reservation_service import _to_out
from app.services.table_service import record_history
from app.socket_manager import emit_sync

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_slot(date_value: str, time_value: str) -> datetime:
    try:
        return datetime.fromisoformat(f"{date_value}T{time_value}").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Date must be YYYY-MM-DD and time must be HH:MM") from exc


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _normalize_contact(contact: str) -> str:
    contact = contact.strip().lower()
    if "@" in contact:
        if contact.count("@") != 1 or "." not in contact.rsplit("@", 1)[1]:
            raise HTTPException(status_code=422, detail="Enter a valid email address")
        return contact
    compact = contact.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not compact.startswith("+") or not compact[1:].isdigit() or not 8 <= len(compact[1:]) <= 15:
        raise HTTPException(status_code=422, detail="Enter a valid email or mobile number with country code")
    return compact


def request_otp(db: Session, contact: str) -> dict[str, object]:
    contact = _normalize_contact(contact)
    latest = db.query(CustomerOTP).filter(CustomerOTP.email == contact).order_by(CustomerOTP.created_at.desc()).first()
    now = _now()
    if latest and latest.created_at.replace(tzinfo=timezone.utc) > now - timedelta(seconds=settings.customer_otp_resend_seconds):
        raise HTTPException(status_code=429, detail="Please wait before requesting another code")
    code = f"{secrets.randbelow(1_000_000):06d}"
    row = CustomerOTP(id=new_id(), email=contact, code_hash=_hash_code(code), created_at=now,
                      expires_at=now + timedelta(minutes=settings.customer_otp_expiry_minutes))
    db.add(row)
    db.commit()
    if settings.smtp_host and "@" in contact:
        try:
            sender = settings.smtp_from_email or settings.smtp_username
            if not sender:
                raise RuntimeError("SMTP_FROM_EMAIL or SMTP_USERNAME is required")
            message = f"Subject: Your FOH verification code\n\nYour verification code is {code}. It expires in {settings.customer_otp_expiry_minutes} minutes."
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                smtp.starttls()
                if settings.smtp_username and settings.smtp_password:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.sendmail(sender, contact, message)
        except Exception as exc:
            db.delete(row)
            db.commit()
            raise HTTPException(status_code=503, detail="Verification email could not be delivered") from exc
        return {"message": "Verification code sent"}
    logger.warning("DEVELOPMENT ONLY customer OTP for %s: %s", contact, code)
    channel = "email" if "@" in contact else "mobile"
    return {"message": f"Development OTP generated; no {channel} provider is configured", "development_otp": code}


def verify_otp(db: Session, email: str, code: str) -> tuple[str, str]:
    email = email.strip().lower()
    row = db.query(CustomerOTP).filter(CustomerOTP.email == email, CustomerOTP.used_at.is_(None)).order_by(CustomerOTP.created_at.desc()).first()
    now = _now()
    if not row or row.expires_at.replace(tzinfo=timezone.utc) < now or row.attempts >= settings.customer_otp_max_attempts:
        raise HTTPException(status_code=401, detail="Invalid or expired verification code")
    row.attempts += 1
    if not secrets.compare_digest(row.code_hash, _hash_code(code)):
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid or expired verification code")
    row.used_at = now
    db.commit()
    from app.core.security import create_customer_access_token
    return create_customer_access_token(email)


def availability(db: Session, requested_date: str, requested_time: str, guests: int) -> dict:
    slot = _parse_slot(requested_date, requested_time)
    active = db.query(Reservation).filter(Reservation.status.in_(("PENDING", "CONFIRMED", "SEATED")),
        Reservation.reserved_for <= slot, Reservation.reserved_until > slot).all()
    blocked = {r.table_id for r in active}
    reservations_by_table = {r.table_id: r for r in active}
    tables = db.query(Table).filter(Table.capacity >= guests).all()
    available_tables = [t for t in tables if t.id not in blocked]
    unavailable_tables = [{"id": t.id, "number": t.number,
                           "status": "BOOKED" if reservations_by_table[t.id].status == "CONFIRMED" else "RESERVED"}
                          for t in tables if t.id in reservations_by_table]
    best_table = min(available_tables, key=lambda table: table.capacity - guests, default=None)
    available = bool(available_tables)
    return {
        "requested_date": requested_date,
        "requested_time": requested_time,
        "guests": guests,
        "available": available,
        "best_time": requested_time if available else None,
        "best_table": ({"id": best_table.id, "number": best_table.number, "capacity": best_table.capacity}
                        if best_table else None),
        "availability_score": 100 if available else 0,
        "available_tables": [{"id": t.id, "number": t.number, "capacity": t.capacity, "status": "AVAILABLE"}
                             for t in available_tables],
        "unavailable_tables": unavailable_tables,
        "busy_tables": [t.number for t in tables if t.id in blocked],
        "message": (f"Table {best_table.number} is available at {requested_time}." if best_table
                    else "No table is available at the selected time."),
    }


def hold(db: Session, email: str, table_id: str, guest_name: str, date_value: str, time_value: str, guests: int) -> Reservation:
    slot = _parse_slot(date_value, time_value)
    now = _now()
    table = db.query(Table).filter(Table.id == table_id).with_for_update().first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    db.query(Reservation).filter(Reservation.status == "PENDING", Reservation.expires_at.is_not(None), Reservation.expires_at < now).update({Reservation.status: "EXPIRED"}, synchronize_session=False)
    conflict = db.query(Reservation).filter(
    Reservation.table_id == table_id,
    Reservation.status.in_((
        "PENDING",
        "CONFIRMED",
        "SEATED",
    )),
    Reservation.reserved_for <= slot,
    Reservation.reserved_until > slot
    ).first()
    if conflict:
        db.rollback()
        raise HTTPException(status_code=409, detail="Sorry, this table was just booked. Please select another table.")
    if guests > table.capacity:
        raise HTTPException(status_code=400, detail="Party size exceeds table capacity")
    expires = now + timedelta(minutes=settings.customer_hold_minutes)
    t_id = getattr(table, "tenant_id", None) or "org-demo"
    b_id = getattr(table, "branch_id", None)
    reservation = Reservation(
        id=new_id(),
        table_id=table_id,
        tenant_id=t_id,
        branch_id=b_id,
        guest_name=guest_name,
        party_size=guests,
        reserved_for=slot,
        reserved_until=slot + timedelta(minutes=settings.customer_booking_duration_minutes),
        status="PENDING",
        notes="Customer booking hold",
        customer_email=email,
        payment_status="UNPAID",
        expires_at=expires,
    )
    old = table.status
    table.status = "RESERVED"
    table.reserved_until = expires.isoformat()
    db.add(reservation)
    record_history(db, table.id, old, "RESERVED", None)
    db.commit()
    db.refresh(reservation)
    emit_sync("reservation.created", {"reservationId": reservation.id, "tableId": table.id}, room=table.floor_id)
    emit_sync("table_updated", _table_to_out(table).model_dump(by_alias=True), room=table.floor_id)
    return reservation


def _owned(db: Session, email: str, reservation_id: str) -> Reservation:
    row = db.query(Reservation).filter(Reservation.id == reservation_id, Reservation.customer_email == email).first()
    if not row:
        raise HTTPException(status_code=404, detail="Booking not found")
    return row


def confirm(
    db: Session,
    email: str,
    reservation_id: str,
) -> Reservation:

    row = _owned(
        db,
        email,
        reservation_id,
    )

    if row.status != "PENDING":
        raise HTTPException(
            status_code=409,
            detail="Booking is no longer pending",
        )

    if (
        row.expires_at
        and row.expires_at.replace(
            tzinfo=timezone.utc
        ) < _now()
    ):
        expire(
            db,
            row,
        )

        raise HTTPException(
            status_code=410,
            detail="Temporary booking has expired",
        )

    # -----------------------------------------
    # CONFIRM THE BOOKING
    # -----------------------------------------

    row.status = "CONFIRMED"

    # Development payment simulation.
    row.payment_status = "PAID"

    row.expires_at = None

    db.commit()

    db.refresh(row)

    table = db.get(
        Table,
        row.table_id,
    )

    # -----------------------------------------
    # SEND REAL-TIME UPDATE TO STAFF DASHBOARD
    # -----------------------------------------

    if table:
        table.status = "RESERVED"
        db.commit()
        db.refresh(table)

        emit_sync(
            "reservation.confirmed",
            {
                "reservationId": row.id,
                "tableId": table.id,
                "status": row.status,
                "paymentStatus": row.payment_status,
            },
            room=table.floor_id,
        )

        emit_sync(
            "table_updated",
            _table_to_out(table).model_dump(
                by_alias=True
            ),
            room=table.floor_id,
        )

    return row

def cancel(db: Session, email: str, reservation_id: str) -> Reservation:
    row = _owned(db, email, reservation_id)
    if row.status in ("SEATED", "BILLING", "COMPLETED", "CANCELLED", "RELEASED", "EXPIRED"):
        raise HTTPException(status_code=409, detail="Booking cannot be cancelled in its current state")
    table = db.get(Table, row.table_id)
    row.status = "CANCELLED"
    if table and table.status == "RESERVED":
        old = table.status
        table.status = "AVAILABLE"
        table.reserved_until = None
        record_history(db, table.id, old, "AVAILABLE", None)
    db.commit()
    if table:
        emit_sync("reservation.cancelled", {"reservationId": row.id, "tableId": table.id}, room=table.floor_id)
        emit_sync("table_updated", _table_to_out(table).model_dump(by_alias=True), room=table.floor_id)
    return row


def expire(db: Session, row: Reservation) -> None:
    table = db.get(Table, row.table_id)
    row.status = "EXPIRED"
    if table and table.status == "RESERVED":
        table.status = "AVAILABLE"
        table.reserved_until = None
        record_history(db, table.id, "RESERVED", "AVAILABLE", None)
    db.commit()
    if table:
        emit_sync("reservation.expired", {"reservationId": row.id, "tableId": table.id}, room=table.floor_id)
        emit_sync("table_updated", _table_to_out(table).model_dump(by_alias=True), room=table.floor_id)


def expire_pending(db: Session) -> None:
    rows = db.query(Reservation).filter(Reservation.status == "PENDING", Reservation.expires_at.is_not(None), Reservation.expires_at < _now()).all()
    for row in rows:
        expire(db, row)
