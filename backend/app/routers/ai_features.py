"""Deterministic, local AI/KDS assistance endpoints.

These algorithms deliberately use the restaurant's own database and remain useful
when no model server is configured.
"""
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from typing import Any

# Keep this router importable in lightweight tooling environments where the
# optional SQLAlchemy type package is not installed.  The database dependency
# still supplies the actual session at runtime.
Session = Any

from app.core.deps import get_current_user, require_kitchen_access
from app.config import settings
from app.database import get_db
from app.models import AIEvent, MenuItem, Order, OrderAnalytics, Table
from app.models.user import User
from app.schemas.ai_features import (
    DemandForecastIn, ModificationImpactIn, PredictionIn, StationRouteIn,
    VoiceCommandIn,
)
from app.schemas.ai import AIEventCreate
from app.services import ai_service, analytics_service, order_service

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/predict-cooking-time")
def predict_cooking_time(body: PredictionIn, db: Session = Depends(get_db),
                         _user: User = Depends(require_kitchen_access)) -> dict:
    station = body.station or "MAIN KITCHEN"
    return analytics_service.predict_cooking_time(
        db, body.item_name, body.quantity, station, body.current_workload
    )


@router.post("/station-routing")
def station_routing(body: StationRouteIn, db: Session = Depends(get_db),
                    _user: User = Depends(require_kitchen_access)) -> dict:
    """Resolve menu items to stations and rank stations by current queue load."""
    routes = []
    loads = {k.upper(): max(0, v) for k, v in body.station_workload.items()}
    # When the caller does not provide a snapshot, use the live KDS queue.
    if not loads:
        for order in db.query(Order).filter(Order.status.in_(("RECEIVED", "PREPARING"))).all():
            for order_item in order.items:
                station = (
                    order_item.menu_item.station
                    if order_item.menu_item and order_item.menu_item.station
                    else "MAIN KITCHEN"
                )
                key = station.upper()
                loads[key] = loads.get(key, 0) + order_item.quantity
    for name in body.items:
        item = db.query(MenuItem).filter(
            (MenuItem.name.ilike(name)) | (MenuItem.id == name)
        ).first()
        station = (item.station if item and item.station else "MAIN KITCHEN").upper()
        routes.append({"item": name, "station": station, "matched": bool(item)})
        loads.setdefault(station, 0)
    return {"routes": routes, "station_workload": loads,
            "recommended_order": sorted(loads, key=lambda key: loads[key])}


def _voice_action(command: str) -> tuple[str, str | None]:
    text = re.sub(r"[^a-z0-9# -]", " ", command.lower())
    text = re.sub(r"\s+", " ", text).strip()
    spoken_digits = {
        "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3",
        "four": "4", "five": "5", "six": "6", "seven": "7",
        "eight": "8", "nine": "9",
    }
    text = re.sub(
        r"(?<=\border )((?:zero|oh|one|two|three|four|five|six|seven|eight|nine)(?:\s+"
        r"(?:zero|oh|one|two|three|four|five|six|seven|eight|nine))+)",
        lambda match: "".join(spoken_digits[word] for word in match.group(1).split()),
        text,
    )
    match = re.search(r"(?:\border\b|#)\s*([a-z0-9-]+)", text)
    if not match:
        # Also accept natural commands such as "ready a1b2" without
        # accidentally treating verbs as identifiers.
        match = re.search(r"\b([0-9a-f]{8,}|[a-z0-9]+-[a-z0-9-]+)\b", text)
    order_id = match.group(1) if match else None
    if any(phrase in text for phrase in ("show ", "list ", "how many", "count ")):
        return "QUERY", order_id
    if any(phrase in text for phrase in ("start ", "begin ", "prepare ", "preparing ")):
        return "PREPARING", order_id
    if re.search(r"\b(ready|finish|complete)\b", text):
        return "READY", order_id
    if re.search(r"\b(serve|served)\b", text):
        return "SERVED", order_id
    return "UNKNOWN", order_id


@router.post("/voice-command")
def voice_command(body: VoiceCommandIn, db: Session = Depends(get_db),
                  user: User = Depends(require_kitchen_access)) -> dict:
    action, order_id = _voice_action(body.command)
    result: dict = {"command": body.command, "action": action, "order_id": order_id,
                    "executed": False}
    if action == "QUERY":
        text = body.command.lower()
        station_match = re.search(r"\b(grill|fry|pizza|bar|dessert|main kitchen)\b", text)
        item_match = re.search(r"how many\s+(.+?)(?:\s+(?:are|is)\s+pending)?\s*\??$", text)
        if item_match:
            requested_item = item_match.group(1).strip()
            quantity = sum(
                item.quantity
                for order in db.query(Order).filter(Order.status.in_(("RECEIVED", "PREPARING"))).all()
                for item in order.items
                if requested_item in item.item_name.lower()
            )
            result["executed"] = True
            result["message"] = f"{quantity} {requested_item} pending."
            return result
        if station_match:
            station = station_match.group(1).upper()
            matching_orders = [
                order.id
                for order in db.query(Order).filter(Order.status.in_(("RECEIVED", "PREPARING"))).all()
                if any(
                    (item.menu_item.station if item.menu_item and item.menu_item.station else "MAIN KITCHEN").upper()
                    == station
                    for item in order.items
                )
            ]
            result["executed"] = True
            result["message"] = (
                f"{len(matching_orders)} active {station} order(s): "
                + (", ".join(matching_orders) if matching_orders else "none")
            )
            return result
        result["message"] = "Say show grill orders or how many fries are pending."
        return result
    if action == "UNKNOWN":
        result["message"] = "Command not understood. Try: ready order <id>, show grill orders, or how many fries are pending."
        return result
    if not order_id:
        result["message"] = "An order id is required."
        return result
    if body.execute:
        try:
            order = db.get(Order, order_id)
            if not order:
                matches = db.query(Order).filter(Order.id.like(f"{order_id}%")).all()
                if len(matches) == 1:
                    order_id = matches[0].id
                elif len(matches) > 1:
                    result["message"] = "That order reference is ambiguous. Say the full order id."
                    return result
            order = db.get(Order, order_id)
            if not order:
                result["message"] = "Order not found. Check the order id and try again."
                return result

            if order.status == action:
                result["executed"] = True
                result["message"] = f"Order {order.id} is already marked {action.lower()}."
                return result

            # Voice commands are explicit operator instructions. Complete the
            # required workflow steps when a command skips an intermediate state.
            transition_path = {
                "READY": {"RECEIVED": ("PREPARING", "READY"), "PREPARING": ("READY",)},
                "SERVED": {
                    "RECEIVED": ("PREPARING", "READY", "SERVED"),
                    "PREPARING": ("READY", "SERVED"),
                    "READY": ("SERVED",),
                },
            }.get(action, {}).get(order.status, (action,))
            for next_status in transition_path:
                order_service.update_order_status(db, order_id, next_status, user_id=user.id)
            order_id = order.id
        except HTTPException:
            raise
        result["executed"] = True
        result["message"] = f"Order {order_id} marked {action.lower()}."
    return result


@router.get("/anomalies")
def detect_anomalies(db: Session = Depends(get_db),
                     _user: User = Depends(require_kitchen_access)) -> dict:
    """Detect delays, historical patterns, and create actionable role alerts."""
    rows = db.query(OrderAnalytics).all()
    values = [float(r.actual_cooking_time) for r in rows if r.actual_cooking_time is not None]
    mean = sum(values) / len(values) if values else 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values) if values else 0.0
    deviation = variance ** 0.5
    historical = [
        {"order_id": r.order_id, "item_name": r.item_name,
         "actual_minutes": float(r.actual_cooking_time),
         "reason": "duration above historical baseline"}
        for r in rows
        if r.actual_cooking_time is not None and deviation > 0
        and float(r.actual_cooking_time) > mean + 2 * deviation
    ]
    now = datetime.now(timezone.utc)
    delayed = []
    alerts_created = []
    for order in db.query(Order).filter(Order.status.in_(("RECEIVED", "PREPARING", "READY"))).all():
        table = db.get(Table, order.table_id)
        table_label = table.number if table else "Table"
        if order.status == "RECEIVED":
            started = order.placed_at
            warning_minutes = getattr(settings, "received_alert_minutes", 10.0)
            event_type = "KITCHEN_ORDER_WAITING"
            target_role = "KITCHEN"
            warning_text = "Order has not been started."
        elif order.status == "READY":
            started = getattr(order, "ready_at", None) or getattr(order, "placed_at", None)
            if not started:
                continue
            warning_minutes = getattr(settings, "ready_alert_minutes", 5.0)
            event_type = "FOOD_WAITING"
            target_role = "WAITER"
            warning_text = "Food is waiting to be served."
        else:
            started = getattr(order, "preparation_started_at", None) or getattr(order, "placed_at", None)
            if not started:
                continue
            warning_minutes = getattr(settings, "preparation_alert_minutes", 20.0)
            event_type = "KITCHEN_PREPARATION_DELAY"
            target_role = "KITCHEN"
            warning_text = "Order preparation is taking longer than expected."
        started = started.replace(tzinfo=timezone.utc) if started.tzinfo is None else started
        elapsed_minutes = (now - started).total_seconds() / 60
        estimates = [
            analytics_service.predict_cooking_time(
                db,
                item.item_name,
                item.quantity,
                (
                    item.menu_item.station
                    if item.menu_item and item.menu_item.station
                    else "MAIN KITCHEN"
                ),
            )["estimated_minutes"]
            for item in order.items
        ]
        estimated_minutes = max(estimates, default=analytics_service.get_default_estimate("order"))
        if elapsed_minutes >= warning_minutes:
            delay = round(max(0, elapsed_minutes - warning_minutes), 1)
            delayed.append({
                "order_id": order.id,
                "status": order.status,
                "delay_minutes": delay,
                "warning": warning_text,
            })
            message = (
                f"Table {table_label} Order #{order.id} has been {order.status.lower()} for {max(1, int(math.ceil(elapsed_minutes)))} minutes. "
                f"{warning_text}"
            )
            existing = db.query(AIEvent).filter(
                AIEvent.event_type == event_type,
                AIEvent.message.contains(order.id),
                AIEvent.resolved.is_(False),
            ).first()
            if not existing:
                event = ai_service.create_alert(
                    db,
                    AIEventCreate(
                        event_type=event_type,
                        message=message,
                        target_role=target_role,
                        table_id=order.table_id,
                    ),
                )
                alerts_created.append(event.model_dump())
            else:
                if existing.message != message:
                    existing.message = message
                    db.commit()
        else:
            existing_alerts = db.query(AIEvent).filter(
                AIEvent.event_type == event_type,
                AIEvent.message.contains(order.id),
                AIEvent.resolved.is_(False),
            ).all()
            for al in existing_alerts:
                al.resolved = True
            if existing_alerts:
                db.commit()

    station_metrics: dict[str, dict[str, float | int]] = {}
    for row in rows:
        if row.station and row.actual_cooking_time is not None:
            metric = station_metrics.setdefault(row.station, {"orders": 0, "total_minutes": 0.0})
            metric["orders"] += 1
            metric["total_minutes"] += float(row.actual_cooking_time)
    for metric in station_metrics.values():
        metric["average_minutes"] = round(
            float(metric["total_minutes"]) / int(metric["orders"]), 1
        )
        del metric["total_minutes"]

    patterns = []
    for station, metric in station_metrics.items():
        if float(metric["average_minutes"]) > max(mean * 1.25, mean + 3):
            patterns.append({
                "station": station,
                "average_minutes": metric["average_minutes"],
                "suggestion": f"Add 1 more person to {station} during busy periods.",
            })
    return {"baseline_minutes": round(mean, 2), "historical_anomalies": historical,
            "delayed_orders": delayed, "patterns": patterns,
            "station_metrics": station_metrics, "alerts_created": alerts_created}


@router.post("/demand-forecast")
def demand_forecast(body: DemandForecastIn, db: Session = Depends(get_db),
                    _user: User = Depends(get_current_user)) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=28)
    orders = db.query(Order).filter(Order.placed_at >= since).all()
    counts = Counter(item.item_name for order in orders for item in order.items)
    days = max(1, min(28, (datetime.now(timezone.utc) - since).days))
    forecast = [{"item_name": name, "historical_quantity": qty,
                 "daily_rate": round(qty / days, 2),
                 "forecast_quantity": round(qty / days * body.horizon_days)}
                for name, qty in counts.most_common()]
    return {"horizon_days": body.horizon_days, "based_on_days": days, "forecast": forecast}


@router.post("/orders/{order_id}/modification-impact")
def modification_impact(order_id: str, body: ModificationImpactIn,
                        db: Session = Depends(get_db),
                        _user: User = Depends(require_kitchen_access)) -> dict:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    current = sum(item.quantity for item in order.items)
    add_items = dict(body.add_items)
    remove_items = dict(body.remove_items)
    if body.modification_text:
        # Keep this local and transparent: structured fields win, while common
        # guest phrases remain usable without requiring an LLM or vector store.
        text = body.modification_text.lower()
        if "extra sauce" in text or "add sauce" in text:
            add_items.setdefault("sauce", 1)
        if "extra" in text and "onion" in text:
            add_items.setdefault("onion", 1)
        if "no onion" in text or "without onion" in text:
            remove_items.setdefault("onion", 1)
    added = sum(max(0, quantity) for quantity in add_items.values())
    removed = sum(max(0, quantity) for quantity in remove_items.values())
    before = max(1, current)
    after = max(1, current + added - min(removed, current))
    base = max((analytics_service.get_default_estimate(i.item_name) for i in order.items), default=10)
    before_time = base * (1 + max(0, before - 1) * 0.6) * (1 + body.current_workload * 0.2)
    after_time = base * (1 + max(0, after - 1) * 0.6) * (1 + body.current_workload * 0.2)
    normalized_text = (body.modification_text or "").lower()
    text_adjustment = 0.0
    if any(phrase in normalized_text for phrase in ("no onion", "without onion", "no onions")):
        text_adjustment -= 2.0
    if "extra sauce" in normalized_text:
        text_adjustment += 1.0
    after_time = max(1.0, after_time + text_adjustment)
    stations = {
        (item.menu_item.station if item.menu_item and item.menu_item.station else "MAIN KITCHEN").upper()
        for item in order.items
    }
    active_orders = db.query(Order).filter(
        Order.id != order.id, Order.status.in_(("RECEIVED", "PREPARING"))
    ).all()
    impacted_orders = [
        {"order_id": candidate.id, "reason": "shares an active station"}
        for candidate in active_orders
        if any(
            (item.menu_item.station if item.menu_item and item.menu_item.station else "MAIN KITCHEN").upper()
            in stations
            for item in candidate.items
        )
    ]
    return {"order_id": order_id, "current_items": current, "projected_items": after,
            "estimated_minutes_before": round(before_time, 1),
            "estimated_minutes_after": round(after_time, 1),
            "delta_minutes": round(after_time - before_time, 1),
            "requires_reprint": bool(added or removed),
            "suggested_routing": sorted(stations),
            "batchable": len(impacted_orders) > 0,
            "impacted_orders": impacted_orders}
