from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.core.permissions import normalize_role
from app.models import AIEvent
from app.schemas.ai import AIEventCreate, AIEventOut
from app.services.ollama_service import generate_text, try_generate
from app.socket_manager import emit_sync

ROLE_FILTER: dict[str, list[str]] = {
    "WAITER": ["WAIT_ALERT", "DIRTY_ALERT", "WAITER_CALL"],
    "HOST": ["WAIT_ALERT", "SEATING_SUGGESTION", "WAITER_CALL"],
    "MANAGER": [
        "WAIT_ALERT",
        "DIRTY_ALERT",
        "DEPARTURE_ALERT",
        "SEATING_SUGGESTION",
        "SHIFT_REPORT",
        "WAITER_CALL",
    ],
    "OWNER": [
        "WAIT_ALERT",
        "DIRTY_ALERT",
        "DEPARTURE_ALERT",
        "SEATING_SUGGESTION",
        "SHIFT_REPORT",
        "WAITER_CALL",
    ],
}


def _alert_payload(event: AIEvent) -> dict:
    created = event.created_at
    if created.tzinfo is None:
        created_str = created.isoformat() + "Z"
    else:
        created_str = created.isoformat().replace("+00:00", "Z")
    return {
        "id": event.id,
        "eventType": event.event_type,
        "message": event.message,
        "targetRole": event.target_role,
        "tableId": event.table_id,
        "createdAt": created_str,
        "resolved": event.resolved,
        "acknowledged": getattr(event, "acknowledged", False),
    }


def _emit_ai_alert(db: Session, event: AIEvent) -> None:
    payload = _alert_payload(event)
    if event.table_id:
        from app.models import Table

        table = db.get(Table, event.table_id)
        if table:
            emit_sync("ai_alert", payload, room=str(table.floor_id))
            return
    from app.models import Floor

    floors = db.query(Floor).all()
    for f in floors:
        emit_sync("ai_alert", payload, room=str(f.id))


def _to_out(event: AIEvent) -> AIEventOut:
    created = event.created_at
    if created.tzinfo is None:
        created_str = created.isoformat() + "Z"
    else:
        created_str = created.isoformat().replace("+00:00", "Z")
    meta_raw = getattr(event, "metadata_json", None)
    meta_dict = None
    if meta_raw:
        try:
            import json
            meta_dict = json.loads(meta_raw)
        except Exception:
            meta_dict = None
    return AIEventOut(
        id=event.id,
        table_id=event.table_id,
        event_type=event.event_type,
        message=event.message,
        target_role=event.target_role,
        created_at=created_str,
        resolved=event.resolved,
        acknowledged=getattr(event, "acknowledged", False),
        metadata_json=meta_raw,
        metadata=meta_dict,
    )


def create_alert(db: Session, payload: AIEventCreate) -> AIEventOut:
    import json
    meta_json = None
    if getattr(payload, "metadata", None):
        meta_json = json.dumps(payload.metadata)
    elif getattr(payload, "metadata_json", None):
        meta_json = payload.metadata_json

    event = AIEvent(
        id=new_id(),
        table_id=payload.table_id,
        event_type=payload.event_type,
        message=payload.message,
        target_role=payload.target_role,
        created_at=datetime.now(timezone.utc),
        resolved=False,
        acknowledged=False,
        metadata_json=meta_json,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    _emit_ai_alert(db, event)
    return _to_out(event)


def list_alerts(db: Session, resolved: bool = False, user_role: str | None = None) -> list[AIEventOut]:
    q = db.query(AIEvent).filter(AIEvent.resolved == resolved)
    if user_role:
        normalized = normalize_role(user_role)
        if normalized in ROLE_FILTER:
            q = q.filter(AIEvent.event_type.in_(ROLE_FILTER[normalized]))
    rows = q.order_by(AIEvent.created_at.desc()).all()
    return [_to_out(r) for r in rows]


def acknowledge_alert(db: Session, event_id: str) -> AIEventOut:
    event = db.get(AIEvent, event_id)
    if not event:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    event.acknowledged = True
    db.commit()
    db.refresh(event)
    return _to_out(event)


def resolve_alert(db: Session, event_id: str) -> dict[str, str | bool]:
    event = db.get(AIEvent, event_id)
    if not event:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    event.resolved = True
    db.commit()
    return {"id": event_id, "resolved": True}


def seating_suggest(db: Session, party_size: int) -> str:
    from app.models import Table

    tables = (
        db.query(Table)
        .filter(Table.status == "AVAILABLE", Table.capacity >= party_size)
        .order_by(Table.capacity.asc())
        .limit(6)
        .all()
    )
    if not tables:
        return (
            f"I couldn't find any open tables for a party of {party_size} right now. "
            "You may want to ask guests to wait a few minutes or combine smaller tables."
        )
    lines = [
        f"Table {t.number} seats {t.capacity} ({t.type.lower()} table)"
        for t in tables[:3]
    ]
    prompt = (
        f"A host needs seating for {party_size} guests. "
        f"Available options: {'; '.join(lines)}. "
        "Recommend the top 3 choices in plain conversational English with a short reason for each. "
        "Do not use JSON or bullet codes."
    )
    return generate_text(
        prompt,
        fallback=(
            f"For a party of {party_size}, I'd start with Table {tables[0].number} "
            f"which seats {tables[0].capacity} — it's the best fit without wasting space."
        ),
    )


def shift_report(db: Session, report_date: str | None = None) -> tuple[str, dict]:
    from app.models import DiningSession, Order

    today = report_date or datetime.now(timezone.utc).date().isoformat()
    sessions = db.query(DiningSession).all()
    orders = db.query(Order).all()
    stats = {
        "sessions": len(sessions),
        "orders": len(orders),
        "reportDate": today,
    }
    prompt = (
        f"Write a short plain-English shift summary paragraph for a restaurant manager. "
        f"Stats: {len(sessions)} dining sessions, {len(orders)} orders placed today. "
        "Sound natural, no JSON, no technical codes."
    )
    content = generate_text(
        prompt,
        fallback=(
            f"Tonight's shift saw {len(sessions)} seated parties and {len(orders)} orders "
            "through the floor. Service ran steadily with no major bottlenecks reported."
        ),
    )
    return content, stats


# ---------------------------------------------------------------------------
# Floor assistant (chat)
# ---------------------------------------------------------------------------

# Status → how staff say it out loud.
_STATUS_WORDS: dict[str, str] = {
    "AVAILABLE": "available",
    "RESERVED": "reserved",
    "SEATED": "seated",
    "ACTIVE": "dining",
    "BILLING": "waiting on the bill",
    "PAID": "paid",
    "CLEANING": "needs cleaning",
}


def _floor_snapshot(db: Session) -> dict:
    """Current floor state the assistant answers from."""
    from app.models import Table

    tables = db.query(Table).order_by(Table.number).all()
    by_status: dict[str, list[str]] = {}
    for table in tables:
        by_status.setdefault(table.status, []).append(table.number)

    open_alerts = (
        db.query(AIEvent)
        .filter(AIEvent.resolved == False)  # noqa: E712 — SQL column comparison
        .order_by(AIEvent.created_at.desc())
        .limit(5)
        .all()
    )
    return {
        "total": len(tables),
        "by_status": by_status,
        "capacities": {t.number: t.capacity for t in tables},
        "alerts": [a.message for a in open_alerts],
    }


def _numbers(snapshot: dict, *statuses: str) -> list[str]:
    out: list[str] = []
    for status_name in statuses:
        out.extend(snapshot["by_status"].get(status_name, []))
    return sorted(out)


def _join_tables(numbers: list[str]) -> str:
    if not numbers:
        return "none"
    labels = [f"T{n}" for n in numbers]
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + f" and {labels[-1]}"


def _fallback_answer(message: str, snapshot: dict) -> str:
    """Answer from floor data alone, for when Ollama isn't running.

    Keeps the assistant useful offline — a demo should never hit a dead end
    just because a local model server isn't up.
    """
    text = message.lower()
    available = _numbers(snapshot, "AVAILABLE")
    cleaning = _numbers(snapshot, "CLEANING")
    occupied = _numbers(snapshot, "SEATED", "ACTIVE", "BILLING", "PAID")
    reserved = _numbers(snapshot, "RESERVED")

    # Checked before "open", so "any open alerts?" isn't read as a table query.
    if any(w in text for w in ("alert", "issue", "problem", "warning")):
        alerts = snapshot["alerts"]
        if not alerts:
            return "No open alerts — the floor is clear."
        return "Open alerts:\n" + "\n".join(f"• {a}" for a in alerts)

    if any(w in text for w in ("dirty", "clean", "bus ", "busser")):
        if not cleaning:
            return "Nothing needs cleaning right now — every table is either open or in service."
        return f"{_join_tables(cleaning)} {'needs' if len(cleaning) == 1 else 'need'} cleaning."

    if any(w in text for w in ("available", "free", "open", "empty", "seat", "party of")):
        if not available:
            return (
                "No tables are open at the moment. "
                f"{_join_tables(cleaning)} will free up once cleaned."
                if cleaning
                else "No tables are open at the moment."
            )
        caps = snapshot["capacities"]
        detail = ", ".join(f"T{n} (seats {caps.get(n, '?')})" for n in available)
        return f"{len(available)} table{'s' if len(available) != 1 else ''} open: {detail}."

    if any(w in text for w in ("occupied", "seated", "busy", "dining", "guests")):
        if not occupied:
            return "No tables are occupied right now."
        return f"{_join_tables(occupied)} {'is' if len(occupied) == 1 else 'are'} occupied."

    if "reserved" in text or "reservation" in text:
        if not reserved:
            return "There are no reserved tables right now."
        return f"Reserved: {_join_tables(reserved)}."

    parts = [f"{snapshot['total']} tables on the floor."]
    if available:
        parts.append(f"Open: {_join_tables(available)}.")
    if occupied:
        parts.append(f"Occupied: {_join_tables(occupied)}.")
    if reserved:
        parts.append(f"Reserved: {_join_tables(reserved)}.")
    if cleaning:
        parts.append(f"Needs cleaning: {_join_tables(cleaning)}.")
    if snapshot["alerts"]:
        parts.append(f"{len(snapshot['alerts'])} open alert(s).")
    return " ".join(parts)


def floor_chat(db: Session, message: str, history: list | None = None) -> tuple[str, bool]:
    """Answer a staff question about the floor. Returns (reply, ai_generated)."""
    snapshot = _floor_snapshot(db)

    state_lines = [
        f"- {_STATUS_WORDS.get(status, status.lower())}: "
        + ", ".join(f"T{n}" for n in sorted(numbers))
        for status, numbers in sorted(snapshot["by_status"].items())
    ]
    alert_text = (
        "Open alerts:\n" + "\n".join(f"- {a}" for a in snapshot["alerts"])
        if snapshot["alerts"]
        else "No open alerts."
    )
    recent = ""
    if history:
        turns = history[-6:]
        recent = "\n".join(
            f"{'Staff' if getattr(t, 'role', 'user') == 'user' else 'Assistant'}: {getattr(t, 'content', '')}"
            for t in turns
        )
        recent = f"\nEarlier in this conversation:\n{recent}\n"

    prompt = (
        "You are the floor assistant for a restaurant host stand. Answer the staff "
        "member's question using ONLY the live floor data below. Be brief and "
        "conversational — one or two sentences, plain English, no JSON, no bullet "
        "lists unless listing tables. Refer to tables as T1, T2 and so on.\n\n"
        f"Floor state ({snapshot['total']} tables total):\n"
        + ("\n".join(state_lines) or "- no tables configured")
        + f"\n{alert_text}\n{recent}\n"
        f"Staff question: {message}\nAnswer:"
    )

    reply = try_generate(prompt)
    if reply:
        return reply, True
    return _fallback_answer(message, snapshot), False
