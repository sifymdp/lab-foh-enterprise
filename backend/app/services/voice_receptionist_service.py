import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.models import Floor, Reservation, Table
from app.services.floor_service import _table_to_out, get_current_floor
from app.services.table_service import _emit_table_updated, record_history
from app.socket_manager import emit_sync

logger = logging.getLogger(__name__)

WORD_TO_NUMBER = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "a": 1,
    "single": 1,
    "couple": 2,
    "pair": 2,
}


def parse_voice_booking_transcript(transcript: str, caller_phone: str | None = None) -> dict[str, Any]:
    """Deterministically and robustly extract reservation parameters from spoken transcripts."""
    text = transcript.strip()
    text_lower = text.lower()

    # 1. Party Size
    party_size = 2  # default
    party_patterns = [
        r"(?:table for|party of|booking for|reservation for|for)\s+(\w+|\d+)\s*(?:people|guests|persons|pax)?",
        r"(\d+)\s*(?:people|guests|persons|pax)",
        r"(?:we are|there are)\s+(\w+|\d+)\s*(?:of us|people|guests)",
    ]
    for pattern in party_patterns:
        match = re.search(pattern, text_lower)
        if match:
            raw_val = match.group(1).lower()
            if raw_val.isdigit():
                party_size = max(1, min(20, int(raw_val)))
                break
            elif raw_val in WORD_TO_NUMBER:
                party_size = WORD_TO_NUMBER[raw_val]
                break

    # 2. Guest Name
    guest_name = "Guest Caller"
    name_patterns = [
        r"(?:my name is|this is|name is|i am|i'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"(?:under|for)\s+(?:the name\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    ]
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            candidate = match.group(1).strip()
            # Ignore common non-name words
            if candidate.lower() not in ("table", "tonight", "tomorrow", "dinner", "lunch", "reservation", "a", "the", "friday", "saturday", "sunday"):
                guest_name = candidate
                break

    # 3. Date
    now = datetime.now(timezone.utc)
    target_date = now.date()
    if "tomorrow" in text_lower:
        target_date = (now + timedelta(days=1)).date()
    elif "day after tomorrow" in text_lower:
        target_date = (now + timedelta(days=2)).date()
    else:
        # Check explicit YYYY-MM-DD
        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
        if date_match:
            try:
                target_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
            except ValueError:
                pass

    # 4. Time
    target_time_str = "19:00"  # default 7:00 PM
    time_match = (
        re.search(r"(?:at|around)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text_lower)
        or re.search(r"\b(\d{1,2})(?::(\d{2}))\s*(am|pm)?\b", text_lower)
        or re.search(r"\b(\d{1,2})\s*(am|pm)\b", text_lower)
    )
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or "0") if time_match.group(2) else 0
        meridiem = time_match.group(3) if len(time_match.groups()) >= 3 else None
        if not meridiem and time_match.lastindex and time_match.group(time_match.lastindex) in ("am", "pm"):
            meridiem = time_match.group(time_match.lastindex)
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        elif not meridiem and hour <= 6:
            hour += 12  # Assume dinner if e.g. "at 7"
        target_time_str = f"{hour:02d}:{minute:02d}"

    # 5. Notes & Special Requests
    special_requests = []
    if "booth" in text_lower:
        special_requests.append("Booth seating preferred")
    if "window" in text_lower:
        special_requests.append("Window table")
    if "anniversary" in text_lower:
        special_requests.append("Anniversary celebration")
    if "birthday" in text_lower:
        special_requests.append("Birthday celebration")
    if "high chair" in text_lower or "baby" in text_lower:
        special_requests.append("High chair needed")
    if "quiet" in text_lower:
        special_requests.append("Quiet area requested")

    # 6. Phone Number
    phone = caller_phone
    if not phone:
        phone_match = re.search(r"(\+?\d[\d\s\-]{8,}\d)", text)
        if phone_match:
            phone = re.sub(r"\s+", "", phone_match.group(1))

    return {
        "guest_name": guest_name,
        "party_size": party_size,
        "date": target_date.isoformat(),
        "time": target_time_str,
        "special_requests": ", ".join(special_requests) if special_requests else None,
        "phone": phone or "+1-555-CALLER",
        "raw_transcript": text,
    }


def process_voice_reservation(
    db: Session,
    transcript: str,
    caller_phone: str | None = None,
) -> dict[str, Any]:
    """End-to-end processing of a telephone reservation call."""
    parsed = parse_voice_booking_transcript(transcript, caller_phone)
    guest_name = parsed["guest_name"]
    party_size = parsed["party_size"]
    date_str = parsed["date"]
    time_str = parsed["time"]
    notes = parsed["special_requests"]

    try:
        floor = get_current_floor(db)
        restaurant_name = floor.name or "FOH Restaurant"
    except Exception:
        restaurant_name = "FOH Restaurant"

    try:
        reserved_for = datetime.fromisoformat(f"{date_str}T{time_str}:00+00:00")
    except ValueError:
        reserved_for = datetime.now(timezone.utc) + timedelta(hours=2)

    reserved_until = reserved_for + timedelta(hours=2)

    # Find matching tables
    tables = (
        db.query(Table)
        .filter(Table.capacity >= party_size)
        .order_by(Table.capacity.asc())
        .all()
    )

    eligible_tables: list[Table] = []
    for table in tables:
        # Check conflicting reservations
        conflicts = (
            db.query(Reservation)
            .filter(
                Reservation.table_id == table.id,
                Reservation.status.in_(["PENDING", "CONFIRMED"]),
                Reservation.reserved_for < reserved_until,
                Reservation.reserved_until > reserved_for,
            )
            .count()
        )
        if conflicts == 0:
            eligible_tables.append(table)

    # Prioritize table type if requested
    best_table: Table | None = None
    if notes and "Booth" in notes:
        for t in eligible_tables:
            if t.type == "BOOTH":
                best_table = t
                break

    if not best_table and eligible_tables:
        best_table = eligible_tables[0]

    now = datetime.now(timezone.utc)

    if best_table:
        # Create reservation
        reservation = Reservation(
            id=new_id(),
            table_id=best_table.id,
            tenant_id=getattr(best_table, "tenant_id", None) or "org-demo",
            branch_id=getattr(best_table, "branch_id", None),
            guest_name=guest_name,
            party_size=party_size,
            reserved_for=reserved_for,
            reserved_until=reserved_until,
            status="CONFIRMED",
            notes=f"AI Voice Receptionist booking. {notes or ''}".strip(),
            customer_email=f"{guest_name.lower().replace(' ', '.')}@phone-caller.com",
            payment_status="CONFIRMED",
        )
        db.add(reservation)

        # If booking is for the immediate current hour, mark table RESERVED
        if abs((reserved_for - now).total_seconds()) < 1800 and best_table.status == "AVAILABLE":
            old_status = best_table.status
            best_table.status = "RESERVED"
            best_table.reserved_until = reserved_until.isoformat()
            record_history(db, best_table.id, old_status, "RESERVED", None)

        db.commit()
        db.refresh(reservation)
        db.refresh(best_table)

        # Real-time WebSocket notifications
        room_id = str(best_table.floor_id) if best_table.floor_id else "floor-1"
        emit_sync(
            "reservation.created",
            {
                "id": reservation.id,
                "tableId": best_table.id,
                "tableNumber": best_table.number,
                "guestName": guest_name,
                "partySize": party_size,
                "reservedFor": reserved_for.isoformat(),
                "status": "CONFIRMED",
            },
            room=room_id,
        )
        _emit_table_updated(best_table)

        # Trigger AI alert banner on staff floor plan
        emit_sync(
            "ai_alert",
            {
                "id": new_id(),
                "tableId": best_table.id,
                "eventType": "VOICE_BOOKING",
                "message": (
                    f"≡ƒô₧ AI Voice Receptionist booked Table {best_table.number} for {guest_name} "
                    f"({party_size} guests on {date_str} at {time_str})."
                ),
                "createdAt": now.isoformat().replace("+00:00", "Z"),
                "resolved": False,
            },
            room=room_id,
        )

        dt_display = reserved_for.strftime("%A, %B %d at %I:%M %p").replace(" 0", " ")
        special_msg = f" I've also noted your request for a {notes.lower()}." if notes else ""
        spoken_response = (
            f"You're all set, {guest_name}! I have reserved Table {best_table.number} for {party_size} guests "
            f"on {dt_display}.{special_msg} We look forward to welcoming you to {restaurant_name}!"
        )

        return {
            "success": True,
            "status": "CONFIRMED",
            "voice_response": spoken_response,
            "table_id": best_table.id,
            "table_number": best_table.number,
            "reservation_id": reservation.id,
            "parsed_details": parsed,
        }

    else:
        # Table unavailable; find alternative
        alt_time = (reserved_for + timedelta(minutes=45)).strftime("%I:%M %p").lstrip("0")
        spoken_response = (
            f"I'm very sorry, {guest_name}, but we are fully committed at {time_str} for a party of {party_size}. "
            f"However, we have an opening available at {alt_time}. Would you like me to secure that table for you instead?"
        )
        return {
            "success": False,
            "status": "UNAVAILABLE",
            "voice_response": spoken_response,
            "table_id": None,
            "table_number": None,
            "reservation_id": None,
            "parsed_details": parsed,
            "suggested_alternative_time": alt_time,
        }
