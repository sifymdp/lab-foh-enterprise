"""Sanitized Operational Adapters.

Extracts operational telemetry and facts from existing FOH tables while
ENFORCING A COMPLETE FINANCIAL AND BILLING EMBARGO.
Prices, revenue, bills, taxes, and payment fields are completely excluded.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.models.session import DiningSession
from app.models.menu_item import MenuItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.reservation import Reservation
from app.models.table import Table
from app.models.user import User
from app.services.ai_agent.security.egress_scanner import scan_payload_for_financial_leak


# ── Strict Output Schemas (extra="forbid") ───────────────────────────────────

class TableStatusModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_number: str
    capacity: int
    table_type: str
    status: str
    guest_name: str | None = None
    party_size: int | None = None
    occupied_minutes: int | None = None


class ShiftOperationsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: str
    seated_parties: int
    total_covers: int
    orders_placed: int
    active_tables_count: int
    available_tables_count: int
    cleaning_tables_count: int


class MenuItemOpsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    category: str
    available: bool
    prep_time_minutes: int
    orders_count: int


class ReservationOpsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_number: str
    guest_name: str
    party_size: int
    reserved_for: str
    status: str


# ── Operational Data Extraction Functions ───────────────────────────────────

def get_sanitized_table_snapshot(db: Session, user: User) -> list[TableStatusModel]:
    """Retrieves operational table snapshot without billing or financial info."""
    q = db.query(Table).filter(Table.tenant_id == user.tenant_id)
    if user.branch_id:
        q = q.filter(Table.branch_id == user.branch_id)
    tables = q.order_by(Table.number).all()

    now = datetime.now(timezone.utc)
    results = []
    for t in tables:
        # Find active session
        session = (
            db.query(DiningSession)
            .filter(
                DiningSession.table_id == t.id,
                DiningSession.closed_at.is_(None),
            )
            .order_by(DiningSession.seated_at.desc())
            .first()
        )

        occupied_min = None
        if session and session.seated_at:
            delta = now - session.seated_at.replace(tzinfo=timezone.utc) if session.seated_at.tzinfo is None else now - session.seated_at
            occupied_min = int(delta.total_seconds() // 60)

        results.append(
            TableStatusModel(
                table_number=str(t.number),
                capacity=t.capacity,
                table_type=str(t.type).lower(),
                status=str(t.status),
                guest_name=session.guest_name if session else None,
                party_size=session.party_size if session else None,
                occupied_minutes=occupied_min,
            )
        )

    # Verification scan
    scan_payload_for_financial_leak([r.model_dump() for r in results])
    return results


def get_sanitized_shift_operations(db: Session, user: User) -> ShiftOperationsSummary:
    """Computes daily operational throughput without ANY financial or revenue data."""
    today = datetime.now(timezone.utc).date()

    q_sessions = db.query(DiningSession).filter(DiningSession.tenant_id == user.tenant_id)
    if user.branch_id:
        q_sessions = q_sessions.filter(DiningSession.branch_id == user.branch_id)
    sessions = q_sessions.all()
    todays_sessions = [s for s in sessions if s.seated_at and s.seated_at.date() == today]

    q_orders = db.query(Order).filter(Order.tenant_id == user.tenant_id)
    if user.branch_id:
        q_orders = q_orders.filter(Order.branch_id == user.branch_id)
    orders = q_orders.all()
    todays_orders = [o for o in orders if o.placed_at and o.placed_at.date() == today]

    q_tables = db.query(Table).filter(Table.tenant_id == user.tenant_id)
    if user.branch_id:
        q_tables = q_tables.filter(Table.branch_id == user.branch_id)
    tables = q_tables.all()

    active_count = sum(1 for t in tables if t.status in ("SEATED", "ACTIVE", "BILLING"))
    available_count = sum(1 for t in tables if t.status == "AVAILABLE")
    cleaning_count = sum(1 for t in tables if t.status == "CLEANING")
    total_covers = sum(s.party_size for s in todays_sessions)

    summary = ShiftOperationsSummary(
        date=today.isoformat(),
        seated_parties=len(todays_sessions),
        total_covers=total_covers,
        orders_placed=len(todays_orders),
        active_tables_count=active_count,
        available_tables_count=available_count,
        cleaning_tables_count=cleaning_count,
    )

    scan_payload_for_financial_leak(summary.model_dump())
    return summary


def get_sanitized_menu_performance(db: Session, user: User) -> list[MenuItemOpsSummary]:
    """Evaluates menu performance based strictly on order counts and preparation times."""
    q_items = db.query(MenuItem).filter(MenuItem.tenant_id == user.tenant_id)
    if user.branch_id:
        q_items = q_items.filter(MenuItem.branch_id == user.branch_id)
    items = q_items.all()

    # Aggregate item orders
    order_counts: dict[str, int] = {}
    for item in items:
        count = (
            db.query(OrderItem)
            .filter(OrderItem.menu_item_id == item.id)
            .count()
        )
        order_counts[item.id] = count

    results = [
        MenuItemOpsSummary(
            name=i.name,
            category=i.category,
            available=i.available,
            prep_time_minutes=i.prep_time_minutes or 15,
            orders_count=order_counts.get(i.id, 0),
        )
        for i in items
    ]

    scan_payload_for_financial_leak([r.model_dump() for r in results])
    return results


def get_sanitized_reservations(db: Session, user: User) -> list[ReservationOpsSummary]:
    """Retrieves upcoming reservations with table, guest, and schedule details."""
    q_res = db.query(Reservation).filter(Reservation.tenant_id == user.tenant_id)
    if user.branch_id:
        q_res = q_res.filter(Reservation.branch_id == user.branch_id)
    reservations = q_res.order_by(Reservation.reserved_for).all()

    tables = {t.id: t.number for t in db.query(Table).filter(Table.tenant_id == user.tenant_id).all()}

    results = [
        ReservationOpsSummary(
            table_number=f"T{tables.get(r.table_id, '?')}",
            guest_name=r.guest_name,
            party_size=r.party_size,
            reserved_for=r.reserved_for.isoformat() if hasattr(r.reserved_for, "isoformat") else str(r.reserved_for),
            status=r.status,
        )
        for r in reservations[:30]
    ]

    scan_payload_for_financial_leak([r.model_dump() for r in results])
    return results
