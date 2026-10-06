"""Operational timing alerts for Kitchen Display System and Waiter service.

Tracks:
1. KITCHEN_ORDER_WAITING: Order in RECEIVED > threshold (5 min) without starting prep.
2. KITCHEN_PREPARATION_DELAY: Order in PREPARING > threshold (15 min or estimated prep time).
3. FOOD_READY: Order marked READY -> alerts Waiter / Supervisor immediately.
4. FOOD_WAITING: Order in READY > threshold (5 min) without being served.

Automatically resolves alerts when orders advance:
- RECEIVED -> PREPARING resolves KITCHEN_ORDER_WAITING.
- PREPARING -> READY resolves KITCHEN_PREPARATION_DELAY and creates FOOD_READY.
- READY -> SERVED resolves FOOD_READY and FOOD_WAITING.

Prevents duplicate active alerts for the same order.
"""
from datetime import datetime, timezone
import json
import logging
from sqlalchemy.orm import Session

from app.config import settings
from app.core.ids import new_id
from app.models.ai_event import AIEvent
from app.models.order import Order
from app.models.table import Table
from app.schemas.ai import AIEventCreate
from app.services import ai_service
from app.socket_manager import emit_sync

logger = logging.getLogger(__name__)

# Configurable defaults
RECEIVED_ALERT_MINUTES = getattr(settings, "received_alert_minutes", 5.0) or 5.0
PREPARATION_ALERT_MINUTES = getattr(settings, "preparation_alert_minutes", 15.0) or 15.0
READY_ALERT_MINUTES = getattr(settings, "ready_alert_minutes", 5.0) or 5.0


def _get_active_order_alert(db: Session, order_id: str, event_type: str) -> AIEvent | None:
    """Finds an unresolved alert of given event_type for the specific order."""
    events = (
        db.query(AIEvent)
        .filter(
            AIEvent.event_type == event_type,
            AIEvent.resolved == False,
        )
        .all()
    )
    for ev in events:
        if ev.metadata_json:
            try:
                meta = json.loads(ev.metadata_json)
                if meta.get("order_id") == order_id or meta.get("orderId") == order_id:
                    return ev
            except Exception:
                pass
        if order_id in (ev.message or ""):
            return ev
    return None


def resolve_order_alerts(db: Session, order_id: str, event_types: list[str]) -> int:
    """Resolves active alerts for an order matching specified event types."""
    events = (
        db.query(AIEvent)
        .filter(
            AIEvent.event_type.in_(event_types),
            AIEvent.resolved == False,
        )
        .all()
    )
    resolved_count = 0
    for ev in events:
        matches = False
        if ev.metadata_json:
            try:
                meta = json.loads(ev.metadata_json)
                if meta.get("order_id") == order_id or meta.get("orderId") == order_id:
                    matches = True
            except Exception:
                pass
        if not matches and order_id in (ev.message or ""):
            matches = True

        if matches:
            ev.resolved = True
            resolved_count += 1
            emit_sync("ai_alert_resolved", {"id": ev.id, "eventType": ev.event_type, "orderId": order_id}, room="*")

    if resolved_count > 0:
        db.commit()
    return resolved_count


def on_order_status_transition(db: Session, order: Order, new_status: str) -> None:
    """Handles status changes: records DB timestamps and resolves/creates alerts."""
    now = datetime.now(timezone.utc)
    old_status = order.status
    table = db.get(Table, order.table_id) if order.table_id else None
    table_label = f"Table {table.number}" if table else f"Table {order.table_id}"
    order_num = order.id[-6:].upper()

    if new_status == "PREPARING":
        if not getattr(order, "preparing_at", None):
            order.preparing_at = now
        # Auto-resolve KITCHEN_ORDER_WAITING
        resolve_order_alerts(db, order.id, ["KITCHEN_ORDER_WAITING"])

    elif new_status == "READY":
        if not getattr(order, "ready_at", None):
            order.ready_at = now
        # Auto-resolve KITCHEN_PREPARATION_DELAY
        resolve_order_alerts(db, order.id, ["KITCHEN_PREPARATION_DELAY"])

        # Create FOOD_READY alert for Waiter
        existing = _get_active_order_alert(db, order.id, "FOOD_READY")
        if not existing:
            ai_service.create_alert(
                db,
                AIEventCreate(
                    event_type="FOOD_READY",
                    message=f"{table_label} Order #{order_num} is ready to serve. Please collect the food from the kitchen.",
                    target_role="WAITER",
                    table_id=order.table_id,
                    metadata_json=json.dumps({"order_id": order.id, "table_id": order.table_id, "status": "READY"}),
                ),
            )

    elif new_status == "SERVED":
        if not getattr(order, "served_at", None):
            order.served_at = now
        # Auto-resolve all waiter ready/waiting alerts
        resolve_order_alerts(db, order.id, ["FOOD_READY", "FOOD_WAITING"])


def evaluate_kitchen_alerts(db: Session) -> dict[str, int]:
    """Scans active approved orders and creates time-based alerts if thresholds are exceeded."""
    now = datetime.now(timezone.utc)
    rec_thresh = getattr(settings, "received_alert_minutes", 5.0) or 5.0
    prep_thresh = getattr(settings, "preparation_alert_minutes", 15.0) or 15.0
    ready_thresh = getattr(settings, "ready_alert_minutes", 5.0) or 5.0

    created = 0
    active_orders = (
        db.query(Order)
        .filter(
            Order.status.in_(["RECEIVED", "CONFIRMED", "PREPARING", "READY"]),
            Order.approval_status == "APPROVED",
        )
        .all()
    )

    for order in active_orders:
        table = db.get(Table, order.table_id) if order.table_id else None
        table_label = f"Table {table.number}" if table else f"Table {order.table_id}"
        order_num = order.id[-6:].upper()

        # 1. RECEIVED ORDER WAITING ALERT
        if order.status in ("RECEIVED", "CONFIRMED"):
            ref_time = getattr(order, "received_at", None) or order.placed_at
            if ref_time:
                if ref_time.tzinfo is None:
                    ref_time = ref_time.replace(tzinfo=timezone.utc)
                elapsed_min = (now - ref_time).total_seconds() / 60.0
                if elapsed_min >= rec_thresh:
                    existing = _get_active_order_alert(db, order.id, "KITCHEN_ORDER_WAITING")
                    if not existing:
                        ai_service.create_alert(
                            db,
                            AIEventCreate(
                                event_type="KITCHEN_ORDER_WAITING",
                                message=f"⚠️ ORDER WAITING: {table_label} Order #{order_num} has been waiting for {int(elapsed_min)} minutes. Please start preparing the order.",
                                target_role="KITCHEN",
                                table_id=order.table_id,
                                metadata_json=json.dumps({
                                    "order_id": order.id,
                                    "table_id": order.table_id,
                                    "waiting_minutes": round(elapsed_min, 1),
                                    "status": order.status,
                                }),
                            ),
                        )
                        created += 1

        # 2. PREPARATION DELAY ALERT
        elif order.status == "PREPARING":
            ref_time = getattr(order, "preparing_at", None) or order.placed_at
            if ref_time:
                if ref_time.tzinfo is None:
                    ref_time = ref_time.replace(tzinfo=timezone.utc)
                elapsed_min = (now - ref_time).total_seconds() / 60.0
                expected_min = float(getattr(order, "estimated_prep_time_minutes", 15) or prep_thresh)
                if elapsed_min >= expected_min:
                    existing = _get_active_order_alert(db, order.id, "KITCHEN_PREPARATION_DELAY")
                    if not existing:
                        ai_service.create_alert(
                            db,
                            AIEventCreate(
                                event_type="KITCHEN_PREPARATION_DELAY",
                                message=f"⚠️ PREPARATION DELAY: {table_label} Order #{order_num} Preparing for {int(elapsed_min)} minutes (Expected: {int(expected_min)}m). Please check this order.",
                                target_role="KITCHEN",
                                table_id=order.table_id,
                                metadata_json=json.dumps({
                                    "order_id": order.id,
                                    "table_id": order.table_id,
                                    "elapsed_minutes": round(elapsed_min, 1),
                                    "expected_minutes": expected_min,
                                    "status": order.status,
                                }),
                            ),
                        )
                        created += 1

        # 3. READY FOOD WAITING ALERT (Waiter delayed in collecting)
        elif order.status == "READY":
            ref_time = getattr(order, "ready_at", None) or order.placed_at
            if ref_time:
                if ref_time.tzinfo is None:
                    ref_time = ref_time.replace(tzinfo=timezone.utc)
                elapsed_min = (now - ref_time).total_seconds() / 60.0
                if elapsed_min >= ready_thresh:
                    existing = _get_active_order_alert(db, order.id, "FOOD_WAITING")
                    if not existing:
                        ai_service.create_alert(
                            db,
                            AIEventCreate(
                                event_type="FOOD_WAITING",
                                message=f"⚠️ FOOD WAITING: {table_label} Order #{order_num} has been READY for {int(elapsed_min)} minutes. Please collect and serve the order.",
                                target_role="WAITER",
                                table_id=order.table_id,
                                metadata_json=json.dumps({
                                    "order_id": order.id,
                                    "table_id": order.table_id,
                                    "ready_minutes": round(elapsed_min, 1),
                                    "status": order.status,
                                }),
                            ),
                        )
                        created += 1

    return {"active_scanned": len(active_orders), "alerts_created": created}
