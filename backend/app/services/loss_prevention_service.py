import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.models import AIEvent, Bill, DiningSession, Order, Table
from app.schemas.ai import AIEventCreate
from app.services import ai_service, table_service
from app.socket_manager import emit_sync

logger = logging.getLogger(__name__)


def calculate_table_exposure(db: Session, table_id: str) -> dict[str, Any] | None:
    """Calculate any unpaid financial exposure for a table's current dining session."""
    session = table_service.active_session_for_table(db, table_id)
    if not session:
        return None

    # Check existing Bill
    bill = db.query(Bill).filter(Bill.session_id == session.id).first()
    if bill and bill.status == "PAID":
        return None

    items_map: dict[str, dict[str, Any]] = {}
    total_amount = 0.0

    if bill and bill.total is not None:
        total_amount = float(bill.total)

    # Gather itemized orders
    for order in session.orders or []:
        for item in order.items or []:
            key = f"{item.item_name}-{item.unit_price}"
            unit_price = float(item.unit_price)
            if key not in items_map:
                items_map[key] = {
                    "item_name": item.item_name,
                    "unit_price": unit_price,
                    "quantity": item.quantity,
                    "line_total": round(unit_price * item.quantity, 2),
                }
            else:
                items_map[key]["quantity"] += item.quantity
                items_map[key]["line_total"] = round(
                    items_map[key]["unit_price"] * items_map[key]["quantity"], 2
                )

    item_list = list(items_map.values())
    if not total_amount:
        total_amount = round(sum(i["line_total"] for i in item_list), 2)

    # If nothing was ordered and no bill exists, there is no unpaid exposure
    if total_amount <= 0:
        return None

    return {
        "session_id": session.id,
        "table_id": table_id,
        "guest_name": session.guest_name or "Walk-in Guest",
        "party_size": session.party_size,
        "seated_at": session.seated_at.isoformat() if session.seated_at else None,
        "unpaid_total": total_amount,
        "item_count": sum(i["quantity"] for i in item_list),
        "items": item_list,
        "has_bill": bill is not None,
        "bill_id": bill.id if bill else None,
    }


def trigger_walkout_alert(
    db: Session,
    table: Table,
    exposure: dict[str, Any],
    reason: str = "Guests vacated table with unpaid balance",
) -> AIEvent:
    """Fire a high-urgency WALKOUT_ALERT across all roles and WebSocket subscribers."""
    unpaid = exposure.get("unpaid_total", 0.0)
    item_count = exposure.get("item_count", 0)
    guest_name = exposure.get("guest_name", "Walk-in Guest")

    message = (
        f"≡ƒÜ¿ EMERGENCY: Walkout detected at Table {table.number}! "
        f"Guests vacated with unpaid balance of ${unpaid:.2f} ({item_count} items). "
        f"Guest: {guest_name}."
    )

    metadata = {
        "alert_category": "LOSS_PREVENTION",
        "severity": "CRITICAL",
        "table_id": table.id,
        "table_number": table.number,
        "session_id": exposure.get("session_id"),
        "unpaid_total": unpaid,
        "item_count": item_count,
        "guest_name": guest_name,
        "party_size": exposure.get("party_size"),
        "items": exposure.get("items", []),
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
    }

    event = ai_service.create_alert(
        db,
        AIEventCreate(
            table_id=table.id,
            event_type="WALKOUT_ALERT",
            target_role=None,  # Broadcast to all roles
            message=message,
            metadata=metadata,
        ),
    )

    table.walkout_alert_sent = True
    db.commit()

    # Broadcast specific walkout event for immediate UI popups/chimes
    emit_sync(
        "walkout_detected",
        {
            "eventId": event.id,
            "tableId": table.id,
            "tableNumber": table.number,
            "message": message,
            "metadata": metadata,
        },
        room=str(table.floor_id),
    )
    table_service._emit_table_updated(table)

    logger.warning("Walkout alert triggered for Table %s: $%s at risk", table.number, unpaid)
    return event


def resolve_walkout_incident(
    db: Session,
    event_id: str,
    resolution_type: str,
    user_id: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Resolve a walkout alert with an audit trail and appropriate table/bill updates.
    
    resolution_type:
      - 'PAID_COUNTER': Guest paid at cashier/POS
      - 'FALSE_ALARM': Guest stepped out temporarily (e.g. smoking/phone call)
      - 'LOGGED_UNRECOVERED': Loss written off and logged
    """
    event = db.get(AIEvent, event_id)
    if not event:
        raise ValueError(f"AIEvent {event_id} not found")

    metadata: dict[str, Any] = {}
    if event.metadata_json:
        try:
            metadata = json.loads(event.metadata_json)
        except Exception:
            metadata = {}

    table = db.get(Table, event.table_id) if event.table_id else None
    session_id = metadata.get("session_id")
    session = db.get(DiningSession, session_id) if session_id else None

    now = datetime.now(timezone.utc)
    metadata["resolution"] = resolution_type
    metadata["resolved_by"] = user_id
    metadata["resolved_at"] = now.isoformat()
    if notes:
        metadata["notes"] = notes

    event.resolved = True
    event.metadata_json = json.dumps(metadata)

    if table:
        table.walkout_alert_sent = False
        table.consecutive_empty_scans = 0

    if resolution_type == "PAID_COUNTER":
        if session:
            # Mark bill as paid
            bill = db.query(Bill).filter(Bill.session_id == session.id).first()
            if bill:
                bill.status = "PAID"
                bill.paid_at = now
            session.status = "PAID"
            session.payment_method = "CASH_COUNTER"
            session.closed_at = now

        if table:
            # Table is free to be cleaned
            table.status = "CLEANING"
            table.cleaning_started_at = now.isoformat().replace("+00:00", "Z")
            table_service.record_history(db, table.id, table.status, "CLEANING", user_id, session_id)

    elif resolution_type == "FALSE_ALARM":
        # Guest returned or stepped outside ΓÇö reset empty counter, keep current status
        if table:
            table.consecutive_empty_scans = 0

    elif resolution_type == "LOGGED_UNRECOVERED":
        if session:
            session.closed_at = now
            session.payment_method = "UNPAID_WALKOUT"
        if table:
            table.status = "CLEANING"
            table.cleaning_started_at = now.isoformat().replace("+00:00", "Z")
            table_service.record_history(db, table.id, table.status, "CLEANING", user_id, session_id)

    db.commit()
    if table:
        table_service._emit_table_updated(table)

    room_id = str(table.floor_id) if table and table.floor_id else "floor-1"
    emit_sync(
        "walkout_resolved",
        {"eventId": event.id, "tableId": table.id if table else None, "resolution": resolution_type},
        room=room_id,
    )

    return {
        "event_id": event.id,
        "resolved": True,
        "resolution": resolution_type,
        "resolved_at": metadata["resolved_at"],
    }


def get_loss_prevention_summary(db: Session) -> dict[str, Any]:
    """Provide high-level metrics for prevented vs unrecovered walkout losses."""
    events = (
        db.query(AIEvent)
        .filter(AIEvent.event_type.in_(["WALKOUT_ALERT", "DEPARTURE_ALERT"]))
        .all()
    )

    total_incidents = len(events)
    active_alerts = 0
    prevented_amount = 0.0
    unrecovered_amount = 0.0
    active_exposure = 0.0

    recent_incidents = []

    for ev in events:
        meta: dict[str, Any] = {}
        if ev.metadata_json:
            try:
                meta = json.loads(ev.metadata_json)
            except Exception:
                meta = {}

        amount = float(meta.get("unpaid_total", 0.0))
        res = meta.get("resolution")

        if not ev.resolved:
            active_alerts += 1
            active_exposure += amount
        elif res == "PAID_COUNTER":
            prevented_amount += amount
        elif res == "LOGGED_UNRECOVERED":
            unrecovered_amount += amount

        recent_incidents.append(
            {
                "id": ev.id,
                "table_number": meta.get("table_number"),
                "unpaid_total": amount,
                "created_at": ev.created_at.isoformat(),
                "resolved": ev.resolved,
                "resolution": res,
                "guest_name": meta.get("guest_name"),
            }
        )

    # Sort descending by creation date
    recent_incidents.sort(key=lambda x: x["created_at"], reverse=True)

    return {
        "total_incidents": total_incidents,
        "active_alerts": active_alerts,
        "active_exposure": round(active_exposure, 2),
        "prevented_amount": round(prevented_amount, 2),
        "unrecovered_amount": round(unrecovered_amount, 2),
        "recent_incidents": recent_incidents[:10],
    }


def simulate_walkout_scenario(db: Session, table_identifier: str) -> dict[str, Any]:
    """Simulate a walkout detection on a table for live demonstrations and testing."""
    # Find table by ID or number
    table = db.query(Table).filter((Table.id == table_identifier) | (Table.number == str(table_identifier))).first()
    if not table:
        raise ValueError(f"Table '{table_identifier}' not found")

    # If table has no active session, create a simulated dining session and order
    session = table_service.active_session_for_table(db, table.id)
    if not session:
        now = datetime.now(timezone.utc)
        session = DiningSession(
            id=new_id(),
            table_id=table.id,
            guest_name="Simulated Guest (VIP)",
            party_size=table.capacity,
            seated_at=now,
            status="BILLING",
        )
        db.add(session)
        table.status = "BILLING"

        # Add simulated order
        order = Order(
            id=new_id(),
            session_id=session.id,
            table_id=table.id,
            placed_at=now,
            status="SERVED",
        )
        db.add(order)

        from app.models.order_item import OrderItem

        item1 = OrderItem(
            id=new_id(),
            order_id=order.id,
            item_name="Dry-Aged Ribeye Steak",
            unit_price=48.00,
            quantity=2,
        )
        item2 = OrderItem(
            id=new_id(),
            order_id=order.id,
            item_name="Cabernet Sauvignon 2019",
            unit_price=35.00,
            quantity=1,
        )
        db.add(item1)
        db.add(item2)
        db.commit()
        db.refresh(table)
        db.refresh(session)

    exposure = calculate_table_exposure(db, table.id)
    if not exposure:
        exposure = {
            "session_id": session.id,
            "table_id": table.id,
            "guest_name": session.guest_name or "Walk-in Guest",
            "party_size": session.party_size,
            "unpaid_total": 131.00,
            "item_count": 3,
            "items": [
                {"item_name": "Dry-Aged Ribeye Steak", "unit_price": 48.0, "quantity": 2, "line_total": 96.0},
                {"item_name": "Cabernet Sauvignon 2019", "unit_price": 35.0, "quantity": 1, "line_total": 35.0},
            ],
        }

    event = trigger_walkout_alert(db, table, exposure, reason="Simulated walkout detection")
    return {
        "success": True,
        "event_id": event.id,
        "table_number": table.number,
        "unpaid_total": exposure["unpaid_total"],
        "message": event.message,
    }
