"""AI assistant chat for owners/managers.

Runs a tool-calling agent loop against Groq (llama-3.3-70b via OpenAI-
compatible API).  The model sees a live snapshot of the floor plus a set of
whitelisted tools that map onto the same service functions the UI uses — so
every change the assistant makes goes through the normal validation, status
machine, history, and socket events.

When Groq is unreachable the assistant degrades to deterministic answers
computed straight from the database.
"""

from __future__ import annotations

import json
import logging
import re
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.core.status_machine import VALID_TRANSITIONS
from app.models import AIEvent, DiningSession, MenuItem, Order, Reservation, Table
from app.models.user import User
from app.schemas.ai import ChatAction
from app.schemas.menu import MenuItemUpdate
from app.schemas.reservation import ReservationCreate
from app.schemas.session import SeatGuestIn
from app.services import menu_service, reservation_service, session_service, table_service
from app.services.groq_llm import chat_completion

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 6
VALID_STATUSES = list(VALID_TRANSITIONS.keys())


# ——— helpers ————————————————————————————————————————————————————————————————


def _find_table(db: Session, table_number: Any) -> Table:
    if table_number is None or str(table_number).strip() == "":
        raise ValueError("Missing 'table_number' — retry the tool call with the table number, e.g. table_number='2'.")
    raw = str(table_number).strip().lstrip("Tt").strip()
    tables = db.query(Table).all()
    for table in tables:
        if str(table.number) == raw:
            return table
    known = ", ".join(sorted((f"T{t.number}" for t in tables), key=lambda s: (len(s), s)))
    raise ValueError(f"No table numbered '{table_number}'. Known tables: {known}")


def _find_menu_item(db: Session, item_name: str) -> MenuItem:
    name = item_name.strip().lower()
    items = db.query(MenuItem).all()
    exact = [i for i in items if i.name.lower() == name]
    if exact:
        return exact[0]
    partial = [i for i in items if name in i.name.lower()]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        raise ValueError(
            f"'{item_name}' matches several items: {', '.join(i.name for i in partial)}. Be more specific."
        )
    raise ValueError(f"No menu item matching '{item_name}'.")


def _parse_when(value: str) -> datetime:
    """Accept full ISO timestamps or bare HH:MM (today, local server time)."""
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        pass
    match = re.fullmatch(r"(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)?", text)
    if not match:
        raise ValueError(f"Could not understand time '{value}'. Use HH:MM or an ISO timestamp.")
    hour, minute = int(match.group(1)), int(match.group(2))
    meridiem = (match.group(3) or "").lower()
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    now = datetime.now().astimezone()
    when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if when < now:
        when += timedelta(days=1)
    return when


def _status_path(current: str, target: str) -> list[str] | None:
    """Shortest chain of valid transitions from current to target (BFS)."""
    if current == target:
        return []
    queue: deque[tuple[str, list[str]]] = deque([(current, [])])
    seen = {current}
    while queue:
        state, path = queue.popleft()
        for nxt in VALID_TRANSITIONS.get(state, []):
            if nxt in seen:
                continue
            if nxt == target:
                return path + [nxt]
            seen.add(nxt)
            queue.append((nxt, path + [nxt]))
    return None


# ——— snapshot (grounding context for every request) —————————————————————————


def build_snapshot(db: Session) -> str:
    tables = db.query(Table).order_by(Table.number).all()
    lines = []
    for t in tables:
        extra = ""
        session = table_service.active_session_for_table(db, t.id)
        if session:
            extra = f" — {session.guest_name or 'guests'}, party of {session.party_size}"
        lines.append(f"T{t.number} (seats {t.capacity}, {t.type.lower()}): {t.status}{extra}")

    by_status: dict[str, list[str]] = {}
    for t in tables:
        by_status.setdefault(t.status, []).append(f"T{t.number}")
    summary = "; ".join(f"{status}: {', '.join(nums)}" for status, nums in sorted(by_status.items()))
    free = by_status.get("AVAILABLE", [])
    free_line = (
        f"AVAILABLE right now: {', '.join(free)} ({len(free)} of {len(tables)})"
        if free
        else f"AVAILABLE right now: NONE — all {len(tables)} tables are taken"
    )

    now = datetime.now(timezone.utc)
    pending_res = db.query(Reservation).filter(Reservation.status == "PENDING").count()
    open_alerts = db.query(AIEvent).filter(AIEvent.resolved.is_(False)).count()
    unavailable_items = db.query(MenuItem).filter(MenuItem.available.is_(False)).count()

    return (
        f"Time now (UTC): {now.strftime('%Y-%m-%d %H:%M')}\n"
        f"Tables:\n" + "\n".join(lines) + "\n"
        f"Summary — {summary}\n"
        f"{free_line}\n"
        f"Pending reservations: {pending_res}. Unresolved alerts: {open_alerts}. "
        f"Menu items 86'd (unavailable): {unavailable_items}."
    )


# ——— tools ——————————————————————————————————————————————————————————————————


def _tool_list_reservations(db: Session, user: User, args: dict) -> dict:
    rows = reservation_service.list_reservations(db)
    tables = {t.id: t.number for t in db.query(Table).all()}
    return {
        "reservations": [
            {
                "table": f"T{tables.get(r.table_id, '?')}",
                "guest": r.guest_name,
                "partySize": r.party_size,
                "time": r.reserved_for,
                "status": r.status,
            }
            for r in rows[:25]
        ]
    }


def _tool_list_menu(db: Session, user: User, args: dict) -> dict:
    items = menu_service.list_all(db)
    return {
        "menu": [
            {"name": i.name, "price": i.price, "category": i.category, "available": i.available}
            for i in items
        ]
    }


def _tool_list_sessions(db: Session, user: User, args: dict) -> dict:
    tables = {t.id: t.number for t in db.query(Table).all()}
    active = (
        db.query(DiningSession)
        .filter(DiningSession.status.in_(("SEATED", "ACTIVE", "BILLING", "PAID")))
        .all()
    )
    return {
        "activeSessions": [
            {
                "table": f"T{tables.get(s.table_id, '?')}",
                "guest": s.guest_name,
                "partySize": s.party_size,
                "status": s.status,
            }
            for s in active
        ]
    }


def _tool_shift_stats(db: Session, user: User, args: dict) -> dict:
    today = datetime.now(timezone.utc).date()
    sessions = db.query(DiningSession).all()
    todays_sessions = [s for s in sessions if s.seated_at and s.seated_at.date() == today]
    orders = db.query(Order).all()
    todays_orders = [o for o in orders if o.placed_at and o.placed_at.date() == today]
    covers = sum(s.party_size for s in todays_sessions)
    return {
        "date": today.isoformat(),
        "seatedParties": len(todays_sessions),
        "covers": covers,
        "ordersToday": len(todays_orders),
    }


def _tool_seat_party(db: Session, user: User, args: dict) -> dict:
    table = _find_table(db, args.get("table_number"))
    party_size = int(args.get("party_size") or 2)
    guest_name = str(args.get("guest_name") or "Walk-in").strip() or "Walk-in"
    session = session_service.seat_guest(
        db,
        SeatGuestIn(table_id=table.id, guest_name=guest_name, party_size=party_size),
        host_id=user.id,
    )
    return {
        "ok": True,
        "summary": f"Seated {guest_name} (party of {party_size}) at T{table.number}",
        "session": {"table": f"T{table.number}", "status": session.status},
    }


def _tool_set_table_status(db: Session, user: User, args: dict) -> dict:
    table = _find_table(db, args.get("table_number"))
    target = str(args.get("status") or "").strip().upper()
    if target not in VALID_STATUSES:
        raise ValueError(f"Unknown status '{args.get('status')}'. Valid: {', '.join(VALID_STATUSES)}")
    if table.status == target:
        return {"ok": True, "summary": f"T{table.number} is already {target}"}
    path = _status_path(table.status, target)
    if path is None:
        raise ValueError(f"No valid path from {table.status} to {target} for T{table.number}")
    start = table.status
    for step in path:
        table_service.patch_table_status(db, table.id, step, user.id)
    return {
        "ok": True,
        "summary": f"T{table.number}: {start} → {target}"
        + (f" (via {' → '.join(path[:-1])})" if len(path) > 1 else ""),
    }


def _tool_close_table(db: Session, user: User, args: dict) -> dict:
    table = _find_table(db, args.get("table_number"))
    session = table_service.active_session_for_table(db, table.id)
    if not session:
        raise ValueError(f"T{table.number} has no active dining session to close.")
    session_service.close_session(db, session.id, user.id)
    return {"ok": True, "summary": f"Closed T{table.number}'s session — table moved to CLEANING"}


def _tool_reserve_table(db: Session, user: User, args: dict) -> dict:
    table = _find_table(db, args.get("table_number"))
    guest_name = str(args.get("guest_name") or "").strip()
    if not guest_name:
        raise ValueError("A guest name is required for the reservation.")
    party_size = int(args.get("party_size") or 2)
    when = _parse_when(str(args.get("time") or ""))
    duration = int(args.get("duration_minutes") or 90)
    payload = ReservationCreate(
        table_id=table.id,
        guest_name=guest_name,
        party_size=party_size,
        reserved_for=when.isoformat(),
        reserved_until=(when + timedelta(minutes=duration)).isoformat(),
        notes=str(args.get("notes") or "") or None,
    )
    reservation_service.create_reservation(db, payload, user.id)
    local = when.astimezone().strftime("%H:%M on %b %d")
    return {
        "ok": True,
        "summary": f"Reserved T{table.number} for {guest_name} (party of {party_size}) at {local}",
    }


def _tool_cancel_reservation(db: Session, user: User, args: dict) -> dict:
    guest = str(args.get("guest_name") or "").strip().lower()
    table_number = args.get("table_number")
    query = db.query(Reservation).filter(Reservation.status == "PENDING")
    rows = query.all()
    if table_number:
        table = _find_table(db, table_number)
        rows = [r for r in rows if r.table_id == table.id]
    if guest:
        rows = [r for r in rows if guest in (r.guest_name or "").lower()]
    if not rows:
        raise ValueError("No matching pending reservation found.")
    if len(rows) > 1:
        listing = ", ".join(f"{r.guest_name} (party {r.party_size})" for r in rows)
        raise ValueError(f"Several reservations match: {listing}. Specify the guest name and table.")
    reservation = rows[0]
    reservation_service.release_reservation(db, reservation.id, user.id)
    tables = {t.id: t.number for t in db.query(Table).all()}
    return {
        "ok": True,
        "summary": f"Cancelled {reservation.guest_name}'s reservation for T{tables.get(reservation.table_id, '?')}",
    }


def _tool_set_menu_item(db: Session, user: User, args: dict) -> dict:
    item = _find_menu_item(db, str(args.get("item_name") or ""))
    changes = []
    patch: dict[str, Any] = {}
    if args.get("available") is not None:
        available = args["available"]
        if isinstance(available, str):
            available = available.strip().lower() in ("true", "yes", "1", "available")
        patch["available"] = bool(available)
        changes.append("back on the menu" if patch["available"] else "86'd (unavailable)")
    if args.get("price") is not None:
        patch["price"] = float(args["price"])
        changes.append(f"price set to {patch['price']:.2f}")
    if not patch:
        raise ValueError("Nothing to change — provide 'available' and/or 'price'.")
    menu_service.update_item(db, item.id, MenuItemUpdate(**patch))
    return {"ok": True, "summary": f"{item.name}: {', '.join(changes)}"}


def _tool_send_alert(db: Session, user: User, args: dict) -> dict:
    from app.schemas.ai import AIEventCreate
    from app.services import ai_service

    message = str(args.get("message") or "").strip()
    if not message:
        raise ValueError("Alert message is required.")
    role = str(args.get("target_role") or "WAITER").strip().upper()
    if role not in ("WAITER", "HOST", "MANAGER", "OWNER"):
        role = "WAITER"
    ai_service.create_alert(
        db,
        AIEventCreate(event_type="WAIT_ALERT", message=message, target_role=role),
    )
    return {"ok": True, "summary": f"Alert sent to {role.lower()}s: \"{message}\""}


ToolFn = Callable[[Session, User, dict], dict]

# name → (handler, mutates_state, JSON schema for the model)
TOOLS: dict[str, tuple[ToolFn, bool, dict]] = {
    "list_reservations": (_tool_list_reservations, False, {
        "description": "List reservations with guest, table, time and status.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }),
    "list_menu": (_tool_list_menu, False, {
        "description": "List all menu items with price, category and availability.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }),
    "list_sessions": (_tool_list_sessions, False, {
        "description": "List active dining sessions (who is seated where).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }),
    "get_shift_stats": (_tool_shift_stats, False, {
        "description": "Today's stats: seated parties, covers, orders, paid revenue.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }),
    "seat_party": (_tool_seat_party, True, {
        "description": "Seat a walk-in party at a table (table must be AVAILABLE or RESERVED).",
        "parameters": {"type": "object", "properties": {
            "table_number": {"type": "string", "description": "Table number, e.g. '3' or 'T3'"},
            "party_size": {"type": "integer"},
            "guest_name": {"type": "string"},
        }, "required": ["table_number", "party_size"]},
    }),
    "set_table_status": (_tool_set_table_status, True, {
        "description": "Change a table's status (AVAILABLE, RESERVED, SEATED, ACTIVE, BILLING, PAID, CLEANING). Walks the status machine if needed.",
        "parameters": {"type": "object", "properties": {
            "table_number": {"type": "string"},
            "status": {"type": "string"},
        }, "required": ["table_number", "status"]},
    }),
    "close_table": (_tool_close_table, True, {
        "description": "Close a table's active dining session and send the table to CLEANING.",
        "parameters": {"type": "object", "properties": {
            "table_number": {"type": "string"},
        }, "required": ["table_number"]},
    }),
    "reserve_table": (_tool_reserve_table, True, {
        "description": "Create a reservation for a table.",
        "parameters": {"type": "object", "properties": {
            "table_number": {"type": "string"},
            "guest_name": {"type": "string"},
            "party_size": {"type": "integer"},
            "time": {"type": "string", "description": "HH:MM (24h or with am/pm) or ISO timestamp"},
            "duration_minutes": {"type": "integer"},
            "notes": {"type": "string"},
        }, "required": ["table_number", "guest_name", "party_size", "time"]},
    }),
    "cancel_reservation": (_tool_cancel_reservation, True, {
        "description": "Cancel a pending reservation, matched by guest name and/or table number.",
        "parameters": {"type": "object", "properties": {
            "guest_name": {"type": "string"},
            "table_number": {"type": "string"},
        }, "required": []},
    }),
    "set_menu_item": (_tool_set_menu_item, True, {
        "description": "Update a menu item: mark it available/unavailable (86) and/or change its price.",
        "parameters": {"type": "object", "properties": {
            "item_name": {"type": "string"},
            "available": {"type": "boolean"},
            "price": {"type": "number"},
        }, "required": ["item_name"]},
    }),
    "send_alert": (_tool_send_alert, True, {
        "description": "Send a staff alert message to a role (WAITER, HOST, MANAGER, OWNER).",
        "parameters": {"type": "object", "properties": {
            "message": {"type": "string"},
            "target_role": {"type": "string"},
        }, "required": ["message"]},
    }),
}


def _openai_tool_specs() -> list[dict]:
    """Build OpenAI-format tool specs for the Groq API."""
    return [
        {
            "type": "function",
            "function": {"name": name, **spec},
        }
        for name, (_fn, _mutates, spec) in TOOLS.items()
    ]


# Small local models frequently rename tool arguments — map common variants
# back onto the canonical parameter names before executing.
ARG_ALIASES: dict[str, tuple[str, ...]] = {
    "table_number": ("table", "tableNumber", "table_no", "number", "table_id", "tableId"),
    "party_size": ("partySize", "size", "guests", "people", "party"),
    "guest_name": ("guestName", "name", "guest", "customer"),
    "item_name": ("itemName", "item", "menu_item", "menuItem", "dish"),
    "status": ("new_status", "newStatus", "state", "table_status", "tableStatus"),
    "time": ("reserved_for", "reservedFor", "when", "datetime", "reservation_time", "at"),
    "message": ("text", "alert", "content", "msg"),
    "target_role": ("role", "targetRole", "to"),
    "price": ("new_price", "newPrice", "amount"),
    "available": ("availability", "is_available", "isAvailable"),
    "duration_minutes": ("duration", "minutes", "durationMinutes"),
    "notes": ("note",),
}


def _normalize_args(args: dict) -> dict:
    normalized = dict(args)
    for canonical, aliases in ARG_ALIASES.items():
        if normalized.get(canonical) is None:
            for alias in aliases:
                if normalized.get(alias) is not None:
                    normalized[canonical] = normalized[alias]
                    break
    return normalized


def _execute_tool(db: Session, user: User, name: str, args: dict) -> tuple[dict, ChatAction | None]:
    fn, mutates, _spec = TOOLS[name]
    try:
        result = fn(db, user, _normalize_args(args or {}))
    except (ValueError, HTTPException) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        return {"error": str(detail)}, (
            ChatAction(tool=name, summary=str(detail), ok=False) if mutates else None
        )
    action = None
    if mutates:
        action = ChatAction(tool=name, summary=str(result.get("summary", name)), ok=True)
    return result, action


# ——— deterministic answers (used for accuracy-critical reads + offline mode) ——


def _availability_answer(db: Session) -> str:
    tables = db.query(Table).order_by(Table.number).all()
    available = [t for t in tables if t.status == "AVAILABLE"]
    if not available:
        busy: dict[str, list[str]] = {}
        for t in tables:
            busy.setdefault(t.status, []).append(f"T{t.number}")
        detail = "; ".join(f"{status.title()}: {', '.join(nums)}" for status, nums in sorted(busy.items()))
        return f"No tables are available right now — {detail}."
    listing = ", ".join(f"T{t.number} (seats {t.capacity})" for t in available)
    return f"{len(available)} of {len(tables)} tables available: {listing}."


def _party_fit_answer(db: Session, size: int) -> str:
    tables = db.query(Table).order_by(Table.number).all()
    available = [t for t in tables if t.status == "AVAILABLE"]
    fitting = sorted((t for t in available if t.capacity >= size), key=lambda t: t.capacity)
    if not fitting:
        return f"No open table seats {size} right now."
    best = fitting[0]
    others = ", ".join(f"T{t.number}" for t in fitting[1:4])
    return (
        f"For a party of {size}, T{best.number} (seats {best.capacity}) is the best fit right now."
        + (f" Other options: {others}." if others else "")
    )


# Read-only availability questions get exact answers computed from the DB —
# never trust the LLM to relay table statuses.
_MUTATION_WORDS = re.compile(
    r"\b(free up|make|set|change|mark|move|reserve|book|seat|assign|cancel|close|clear|update|86)\b"
)
_AVAILABILITY_WORDS = re.compile(r"\b(available|avail|free|open|empty|vacant|unoccupied)\b")
_TABLE_WORDS = re.compile(r"\btables?\b|\bseats?\b|\bseating\b")


def _availability_question(text: str) -> bool:
    t = text.lower()
    if _MUTATION_WORDS.search(t):
        return False
    return bool(_AVAILABILITY_WORDS.search(t) and _TABLE_WORDS.search(t))


def _extract_table_number(text: str) -> str | None:
    """
    Extract table number from natural language input with high precision.
    Prevents false matches on words like 'to', 'for', 'the', 'at', 'a'.
    """
    # 1. Matches "table 1", "table #1", "tbl 2", "table t1", "table-1"
    m = re.search(r"\b(?:table|tbl)\s*#?\s*t?([0-9]+)\b", text, re.IGNORECASE)
    if m:
        return m.group(1)

    # 2. Matches "t1", "t2", "t10", "t-1", "t#1" (preceded by boundary or punctuation)
    m = re.search(r"(?:^|[\s,.:;?!/(])t[-#]?([0-9]+)\b", text, re.IGNORECASE)
    if m:
        return m.group(1)

    # 3. Matches "to 1", "for 1", "at 1", "on 1"
    m = re.search(r"\b(?:to|for|at|on)\s+t?#?([0-9]+)\b", text, re.IGNORECASE)
    if m:
        return m.group(1)

    # 4. Spelled numbers: "table one", "table two", etc.
    word_map = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        "eleven": "11", "twelve": "12",
    }
    for word, num in word_map.items():
        if re.search(rf"\b(?:table|tbl|t)\s+{word}\b", text, re.IGNORECASE):
            return num

    # 5. Command + bare number: e.g. "bill 1", "clean 2", "free 3", "seat 4 at 1"
    m = re.search(r"\b(?:bill|clean|free|seat|close|mark|clear|bus|settle|paid)\s+t?#?([0-9]+)\b", text, re.IGNORECASE)
    if m:
        return m.group(1)

    # 6. Alphanumeric tables if explicitly prefixed with table: "table A1"
    m = re.search(r"\b(?:table|tbl)\s+([a-zA-Z0-9]+)\b", text, re.IGNORECASE)
    if m:
        val = m.group(1).upper().lstrip("T")
        if val not in ("THE", "A", "AN", "TO", "FOR", "NOW", "PLEASE", "ALL", "NEW", "AS"):
            return val

    return None


def _fallback_process(db: Session, user: User, message: str) -> tuple[str, list[ChatAction]]:
    """Intelligent local natural language engine.

    Parses operational commands and queries when no cloud LLM is active (or if
    cloud API is unreachable), executing the exact same tools and status
    transitions so the system remains fully functional in local/offline environments.
    """
    text = message.strip()
    lower = text.lower()
    actions: list[ChatAction] = []

    # 1. Greetings & Help
    if re.search(r"^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening))\b", lower) or lower in (
        "who are you", "what can you do", "help", "commands", "?"
    ):
        return (
            f"Hello, {user.name}! I am your Front of House AI Assistant. "
            "I can monitor floor status, seat guests, manage reservations, update menu items, and send alerts.\n\n"
            "**Quick commands you can try:**\n"
            "• *\"Seat party of 4 at T5\"* or *\"Seat John party of 2 at T1\"*\n"
            "• *\"Send bill to T1\"* or *\"Mark T1 as paid\"*\n"
            "• *\"Clean table 2\"* or *\"Make T1 available\"*\n"
            "• *\"Reserve T3 for Sarah party of 4 at 7:30 PM\"*\n"
            "• *\"Show reservations\"* or *\"Show menu\"*\n"
            "• *\"86 Ribeye Steak\"* or *\"Make Ribeye Steak available\"*\n"
            "• *\"Shift report\"* or *\"Which tables are free?\"*\n"
            "• *\"Alert waiter table 4 needs water\"*\n\n"
            "How can I assist you right now?",
            [],
        )

    # 2. Bill Table (e.g. "sent bill to t1", "send bill to t1", "bill table 2", "checkout t1", "print bill for t3")
    is_bill = bool(
        re.search(r"\b(bill|billing|check|checkout|invoice|payment\s+request|send\s+bill|sent\s+bill|give\s+bill|print\s+bill)\b", lower)
        and not re.search(r"\b(shift|revenue|stats|report|cancel|paid)\b", lower)
    )
    if is_bill:
        t_num = _extract_table_number(lower)
        if t_num:
            res, action = _execute_tool(db, user, "set_table_status", {"table_number": t_num, "status": "BILLING"})
            if action:
                actions.append(action)
            if action and action.ok:
                return (
                    f"Done! Table T{t_num} has been set to BILLING. "
                    "The bill has been sent and is ready for payment (Cash, Card, or QR).",
                    actions,
                )
            return f"Could not set Table T{t_num} to billing: {res.get('error')}", actions
        return (
            "Which table would you like to bill? For example: *\"Send bill to T1\"* or *\"Bill table 2\"*.",
            [],
        )

    # 3. Mark Paid / Payment Received (e.g. "mark t1 as paid", "t1 paid", "payment received for table 2")
    is_paid = bool(
        re.search(r"\b(mark\s+paid|mark\s+as\s+paid|paid|payment\s+received|collected\s+cash|settle|settled)\b", lower)
        and not re.search(r"\b(shift|revenue|stats|report)\b", lower)
    )
    if is_paid:
        t_num = _extract_table_number(lower)
        if t_num:
            res, action = _execute_tool(db, user, "set_table_status", {"table_number": t_num, "status": "CLEANING"})
            if action:
                actions.append(action)
            if action and action.ok:
                return (
                    f"Payment confirmed for Table T{t_num}! The dining session is completed and the table is now set to CLEANING.",
                    actions,
                )
            return f"Could not mark Table T{t_num} as paid: {res.get('error')}", actions
        return "Which table would you like to mark as paid? e.g. *\"Mark T1 as paid\"*.", []

    # 4. Clean / Bus Table (e.g. "clean table 2", "clean t2", "bus table 3", "clear t1")
    is_clean = bool(
        re.search(r"\b(clean|bus|clear|cleared|dirty)\b", lower)
        and not re.search(r"\b(menu|item|dish|price)\b", lower)
    )
    if is_clean:
        t_num = _extract_table_number(lower)
        if t_num:
            res, action = _execute_tool(db, user, "set_table_status", {"table_number": t_num, "status": "CLEANING"})
            if action:
                actions.append(action)
            if action and action.ok:
                return f"Table T{t_num} is now marked CLEANING for the busser.", actions
            return f"Could not set Table T{t_num} to cleaning: {res.get('error')}", actions
        return "Which table would you like to clean? e.g. *\"Clean table 2\"*.", []

    # 5. Make Table Available / Free (e.g. "make t1 available", "free table 2", "table 3 is open")
    is_free = bool(
        re.search(r"\b(make|mark|set|free)\s+.*\b(available|free|open|ready)\b", lower)
        or re.search(r"\b(?:free\s+table|free\s+t\d+|open\s+table|available\s+table)\b", lower)
        or re.search(r"\bfree\s+up\s+t?#?\d+\b", lower)
    )
    if is_free:
        t_num = _extract_table_number(lower)
        if t_num:
            res, action = _execute_tool(db, user, "set_table_status", {"table_number": t_num, "status": "AVAILABLE"})
            if action:
                actions.append(action)
            if action and action.ok:
                return f"Table T{t_num} is now marked AVAILABLE and ready for new guests.", actions
            return f"Could not free Table T{t_num}: {res.get('error')}", actions
        return "Which table would you like to make available? e.g. *\"Make T1 available\"*.", []

    # 6. Close Table (e.g. "close table 1", "close t1", "wrap up t2")
    is_close = bool(
        re.search(r"\b(close|wrap\s+up|finish)\s+(?:table\s+|session\s+|t)?", lower)
        and not re.search(r"\b(shift|register|drawer|menu)\b", lower)
    )
    if is_close:
        t_num = _extract_table_number(lower)
        if t_num:
            res, action = _execute_tool(db, user, "close_table", {"table_number": t_num})
            if action:
                actions.append(action)
            if action and action.ok:
                return f"Closed dining session on Table T{t_num}. The table is now in CLEANING state.", actions
            return f"Could not close Table T{t_num}: {res.get('error')}", actions
        return "Which table would you like to close? e.g. *\"Close table 3\"*.", []

    # 7. Seating Walk-ins / Guests
    # e.g. "seat party of 4 at T5", "seat 2 at table 1", "seat Alice party of 3 at T4", "seat T5"
    if re.search(r"\b(seat|seated)\b", lower):
        t_num = _extract_table_number(lower)
        if t_num:
            # Parse party size
            p_match = re.search(r"\b(?:party\s+of|pax|for|guests?|people)\s*([0-9]+)\b", lower) or re.search(r"\bseat\s+([0-9]+)\b", lower)
            party_size = int(p_match.group(1)) if p_match else 2
            # Parse guest name if provided: e.g. "seat Alice at T1"
            name_match = re.search(r"\bseat\s+([A-Za-z]+)\s+(?:party|at|for|on)\b", text)
            guest_name = name_match.group(1).title() if name_match and name_match.group(1).lower() not in ("a", "party", "guests", "table", "at", "for") else "Walk-in"

            res, action = _execute_tool(
                db, user, "seat_party",
                {"table_number": t_num, "party_size": party_size, "guest_name": guest_name}
            )
            if action:
                actions.append(action)
            if action and action.ok:
                return (
                    f"Done! I've seated {guest_name} (party of {party_size}) at Table T{t_num}. "
                    "The table is now marked SEATED.",
                    actions,
                )
            return (
                f"Couldn't seat party at Table T{t_num}: {res.get('error', 'unknown error')}. "
                f"{_availability_answer(db)}",
                actions,
            )

    # 7. Shift Stats & Analytics
    if re.search(r"\b(shift\s+stats|shift\s+report|how\s+are\s+we\s+doing|today'?s\s+performance|daily\s+stats|revenue)\b", lower):
        stats = _tool_shift_stats(db, user, {})
        return (
            f"**Shift Summary for Today ({stats['date']})**:\n"
            f"• **Seated Parties**: {stats['seatedParties']} ({stats['covers']} total covers)\n"
            f"• **Orders Placed**: {stats['ordersToday']}\n"
            f"• **Paid Revenue**: ${stats['paidRevenueToday']:.2f}\n\n"
            f"{_availability_answer(db)}",
            [],
        )

    # 8. List Reservations
    if re.search(r"\b(?:list|show|view|check|get|any)\s+(?:all\s+)?reservations?\b", lower) or lower == "reservations":
        res_data = _tool_list_reservations(db, user, {})
        items = res_data.get("reservations", [])
        if not items:
            return "There are currently no upcoming reservations on file.", []
        lines = [
            f"• **{r['guest']}** (party of {r['partySize']}) at **{r['table']}** — {r['time']} [{r['status']}]"
            for r in items
        ]
        return "Here are the upcoming reservations:\n" + "\n".join(lines), []

    # 9. Book Reservation
    # e.g. "reserve T3 for Sarah at 7:00pm", "reserve table 2 for Alex party of 4 at 8pm"
    res_match = re.search(
        r"\breserve\s+(?:table\s+|t)?([a-zA-Z0-9]+)\s+for\s+([A-Za-z\s]+?)(?:\s+(?:party\s+of\s+|pax\s+)(\d+))?\s+(?:at\s+)([0-9:apmAPM\s]+)",
        text,
        re.IGNORECASE,
    )
    if res_match:
        t_raw, guest, party, when_str = res_match.groups()
        t_num = t_raw.upper().lstrip("T")
        p_size = int(party or 2)
        res, action = _execute_tool(
            db, user, "reserve_table",
            {"table_number": t_num, "guest_name": guest.strip(), "party_size": p_size, "time": when_str.strip()}
        )
        if action:
            actions.append(action)
        if action and action.ok:
            return f"Reservation confirmed! Reserved Table T{t_num} for {guest.strip()} (party of {p_size}) at {when_str.strip()}.", actions
        return f"Could not reserve Table T{t_num}: {res.get('error')}", actions

    # 10. Cancel Reservation
    cancel_res_match = re.search(
        r"\bcancel\s+reservation\s+(?:for\s+([a-zA-Z\s]+)|(?:on|at)\s+(?:table\s+|t)?([a-zA-Z0-9]+))",
        lower,
    )
    if cancel_res_match:
        guest, t_raw = cancel_res_match.groups()
        args: dict[str, Any] = {}
        if guest:
            args["guest_name"] = guest.strip()
        if t_raw:
            args["table_number"] = t_raw.upper().lstrip("T")
        res, action = _execute_tool(db, user, "cancel_reservation", args)
        if action:
            actions.append(action)
        if action and action.ok:
            return f"Reservation cancelled: {res.get('summary')}", actions
        return f"Could not cancel reservation: {res.get('error')}", actions

    # 11. Menu: 86 / Un-86 / Price
    un86_match = (
        re.search(r"\bmake\s+([a-zA-Z0-9\s]+?)\s+available\b", lower)
        or re.search(r"\b(?:un-86|un86|enable|make\s+available|back\s+on\s+menu)\s+([a-zA-Z0-9\s]+)$", lower)
    )
    if un86_match:
        dish = un86_match.group(1).strip()
        res, action = _execute_tool(db, user, "set_menu_item", {"item_name": dish, "available": True})
        if action:
            actions.append(action)
        if action and action.ok:
            return f"**{dish.title()}** is back in stock and available on POS and guest menus.", actions
        return f"Could not update menu item '{dish}': {res.get('error')}", actions

    mark86_match = (
        re.search(r"\bmake\s+([a-zA-Z0-9\s]+?)\s+unavailable\b", lower)
        or re.search(r"\b(?:86|disable|out\s+of\s+stock)\s+([a-zA-Z0-9\s]+)$", lower)
    )
    if mark86_match:
        dish = mark86_match.group(1).strip()
        res, action = _execute_tool(db, user, "set_menu_item", {"item_name": dish, "available": False})
        if action:
            actions.append(action)
        if action and action.ok:
            return f"I've 86'd **{dish.title()}** — it is now marked unavailable across POS and customer views.", actions
        return f"Could not 86 '{dish}': {res.get('error')}", actions

    price_match = re.search(r"\b(?:set|change|update)\s+price\s+of\s+([a-zA-Z0-9\s]+?)\s+to\s+\$?([0-9.]+)", lower)
    if price_match:
        dish, pr = price_match.groups()
        res, action = _execute_tool(db, user, "set_menu_item", {"item_name": dish.strip(), "price": float(pr)})
        if action:
            actions.append(action)
        if action and action.ok:
            return f"Updated price of **{dish.strip().title()}** to ${float(pr):.2f}.", actions
        return f"Could not update price for '{dish}': {res.get('error')}", actions

    if re.search(r"\b(?:show|list|view|what\s+is\s+on\s+the)\s+menu\b", lower) or lower == "menu":
        items = _tool_list_menu(db, user, {}).get("menu", [])
        if not items:
            return "No menu items found in the system.", []
        lines = [
            f"• **{i['name']}** (${float(i['price']):.2f}) — {i['category']}" + (" *(86'd)*" if not i["available"] else "")
            for i in items[:20]
        ]
        return f"Here is the active menu ({len(items)} items):\n" + "\n".join(lines), []

    # 12. Staff Alerts
    # e.g. "alert waiter table 4 needs water", "notify kitchen order delayed"
    alert_match = re.search(r"\b(?:alert|notify|tell)\s+(waiters?|hosts?|managers?|kitchen|chefs?)\s*[:-]?\s*(.+)", text, re.IGNORECASE)
    if alert_match:
        target, msg = alert_match.groups()
        t_clean = target.upper().rstrip("S")
        if t_clean in ("KITCHEN", "CHEF"):
            t_clean = "CHEF"
        elif t_clean in ("WAITER", "HOST", "MANAGER", "OWNER"):
            pass
        else:
            t_clean = "WAITER"
        res, action = _execute_tool(db, user, "send_alert", {"target_role": t_clean, "message": msg.strip()})
        if action:
            actions.append(action)
        if action and action.ok:
            return f"Staff alert broadcasted to {t_clean.lower()}s: \"{msg.strip()}\"", actions
        return f"Could not send alert: {res.get('error')}", actions

    # 13. Specific Table Inquiry
    # e.g. "who is at table 1?", "check T4", "status of table 2", "how is t1 doing", "is t1 available"
    if re.search(r"\b(?:who\s+is\s+at|status\s+of|check|what\s+about|how\s+is|is\s+t\d+|is\s+table)\b", lower):
        t_num = _extract_table_number(lower)
        if t_num:
            try:
                table = _find_table(db, t_num)
                session = table_service.active_session_for_table(db, table.id)
                if session:
                    seated_min = _minutes_between(session.seated_at, _now()) or 0
                    return (
                        f"**Table T{table.number}** (seats {table.capacity}, {table.type.lower()}) is currently **{table.status}**.\n"
                        f"• Guest: **{session.guest_name or 'Walk-in'}** (party of {session.party_size})\n"
                        f"• Seated: ~{round(seated_min)} min ago\n"
                        f"• Status: {session.status}",
                        [],
                    )
                return (
                    f"**Table T{table.number}** (seats {table.capacity}, {table.type.lower()}) is currently **{table.status}** with no active dining session.",
                    [],
                )
            except Exception as e:
                return str(e), []

    # 14. Party size recommendation
    party_match = re.search(r"(?:party|group|table)\s*(?:of|for)\s*(\d+)|(\d+)\s*(?:people|guests|pax)", lower)
    if party_match:
        size = int(party_match.group(1) or party_match.group(2))
        return _party_fit_answer(db, size), []

    # 15. Availability check
    if _AVAILABILITY_WORDS.search(lower):
        return _availability_answer(db), []

    # 16. Fallback Snapshot
    tables = db.query(Table).order_by(Table.number).all()
    by_status: dict[str, list[str]] = {}
    for t in tables:
        by_status.setdefault(t.status, []).append(f"T{t.number}")
    lines = [f"{status.title()}: {', '.join(nums)}" for status, nums in sorted(by_status.items())]

    return (
        f"**Floor Status Snapshot**: {'; '.join(lines)}.\n\n"
        "**Available actions:**\n"
        "• *\"Seat a party of 4 at T5\"*\n"
        "• *\"Send bill to T1\"* or *\"Mark T1 as paid\"*\n"
        "• *\"Clean table 2\"* or *\"Make T1 available\"*\n"
        "• *\"Show reservations\"* or *\"Shift report\"*\n"
        "• *\"86 Burger\"* or *\"Alert waiter table 3 needs service\"*\n\n"
        "*(Running in Fast Local Engine · Configure GROQ_API_KEY or GEMINI_API_KEY in backend/.env for conversational AI)*",
        [],
    )


def _summarize_actions(actions: list[ChatAction]) -> str:
    done = [a.summary for a in actions if a.ok]
    failed = [a.summary for a in actions if not a.ok]
    parts = []
    if done:
        parts.append("Done: " + "; ".join(done) + ".")
    if failed:
        parts.append("Couldn't complete: " + "; ".join(failed) + ".")
    return " ".join(parts)


# ——— system prompt ——————————————————————————————————————————————————————————

SYSTEM_PROMPT_TEMPLATE = """\
You are FOH Assistant — the intelligent AI copilot for a premium restaurant's \
front-of-house operations. You speak to staff the way a seasoned maitre d' \
would: warm, professional, concise, and always helpful.

## Your personality
- Friendly but efficient — like a trusted colleague, not a chatbot
- Use natural, conversational English — never output raw JSON, code, or markdown tables
- When reporting data, present it in clean sentences or short lists
- Always explain *why* you're recommending something, not just what
- If you make a change, confirm what you did and why it matters

## Who you're speaking to
You are currently assisting **{user_name}** ({user_role}), who has full authority \
over floor operations.

## Rules
1. The LIVE FLOOR SNAPSHOT below is the ONLY source of truth for table statuses. \
   Never guess, assume, or rely on earlier messages — they may be stale.
2. Use the provided tools whenever the user asks you to change something \
   (seat guests, reserve/free tables, close sessions, 86 menu items, change prices, \
   send staff alerts) or needs data the snapshot doesn't show \
   (reservation lists, full menu, active sessions, shift stats).
3. After using a tool, explain what you did in plain language.
4. If a tool call fails, explain the error in a helpful, non-technical way and \
   suggest what the user can do instead.
5. Keep replies to 1–3 sentences for simple questions, up to a short paragraph \
   for complex ones.
6. When listing tables, use the format T1, T2, etc.

## Live floor snapshot
{snapshot}
"""


# ——— main entry ——————————————————————————————————————————————————————————————


def chat(db: Session, user: User, messages: list[dict]) -> tuple[str, list[ChatAction]]:
    last_user_message = next(
        (str(m.get("content") or "") for m in reversed(messages) if m.get("role") == "user"), ""
    )
    from app.services.ai_agent import ai_orchestrator
    res = ai_orchestrator.process_request(db, user, last_user_message)
    chat_actions = [
        ChatAction(
            type=a.type,
            route=a.route,
            filter=a.filter,
            table_ids=a.table_ids,
            summary=f"{a.type} -> {a.route}" if a.route else a.type,
            ok=True,
        )
        for a in res.actions
    ]
    return res.response.summary, chat_actions
    if not active_provider:
        # No cloud LLM configured — route through intelligent local engine
        return _fallback_process(db, user, last_user_message)

    # Cloud LLM is available — run conversational agent loop with tool-calling
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        user_name=user.name,
        user_role=user.role.title(),
        snapshot=build_snapshot(db),
    )

    convo: list[dict] = [{"role": "system", "content": system_prompt}]
    for msg in messages[-12:]:
        role = msg.get("role")
        content = str(msg.get("content") or "")
        if role in ("user", "assistant") and content:
            convo.append({"role": role, "content": content})

    tool_specs = _openai_tool_specs()
    actions: list[ChatAction] = []

    for _round in range(MAX_TOOL_ROUNDS):
        reply_msg = chat_completion(convo, tools=tool_specs, temperature=0.1)

        # If LLM API fails or times out, fall back gracefully to local engine
        if reply_msg is None:
            return _fallback_process(db, user, last_user_message)

        tool_calls = reply_msg.get("tool_calls") or []

        if not tool_calls:
            content = (reply_msg.get("content") or "").strip()
            if content:
                return content, actions
            if actions:
                return _summarize_actions(actions), actions
            return _fallback_process(db, user, last_user_message)

        # Process tool calls
        convo.append(reply_msg)
        for call in tool_calls:
            fn_info = call.get("function") or {}
            name = fn_info.get("name") or ""
            raw_args = fn_info.get("arguments") or "{}"
            if isinstance(raw_args, str):
                try:
                    raw_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    raw_args = {}

            if name not in TOOLS:
                result: dict = {"error": f"Unknown tool '{name}'"}
                action = None
            else:
                result, action = _execute_tool(db, user, name, raw_args)
            if action:
                actions.append(action)

            convo.append({
                "role": "tool",
                "tool_call_id": call.get("id", ""),
                "content": json.dumps(result),
            })

    # Exhausted tool rounds
    if actions:
        return _summarize_actions(actions), actions
    return _fallback_process(db, user, last_user_message)
