"""
Operational Insights Service
─────────────────────────────
Reads real data from the DB and computes rule-based operational metrics:
  - Kitchen preparation speed (order placed → READY)
  - Dining session duration vs. 7-day baseline
  - Table cleaning turnaround time
  - Billing speed (order READY → bill PAID)
  - Current occupancy and upcoming reservation pressure
  - Wait-time estimate for walk-ins
  - Bottleneck severity ranking across the full workflow

No external AI API required — deterministic analytics on your own data.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.bill import Bill
from app.models.cleaning import CleaningEvent
from app.models.order import Order
from app.models.reservation import Reservation
from app.models.session import DiningSession
from app.models.table import Table


# ── helpers ─────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _minutes_between(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    a = _as_utc(a)
    b = _as_utc(b)
    diff = (b - a).total_seconds()
    return round(diff / 60, 1) if diff >= 0 else None


def _pct_change(current: float, baseline: float) -> float | None:
    """Return % change; None if baseline is zero."""
    if baseline == 0:
        return None
    return round((current - baseline) / baseline * 100, 1)


def _severity(pct: float | None) -> str:
    """Convert a % deviation into a severity label."""
    if pct is None:
        return "info"
    if abs(pct) >= 25:
        return "alert"
    if abs(pct) >= 12:
        return "warning"
    return "ok"


# ── kitchen speed ─────────────────────────────────────────────────────────

def _kitchen_prep_minutes(db: Session, since: datetime, until: datetime) -> list[float]:
    """
    For orders placed in [since, until] that reached READY or SERVED,
    return list of (ready_timestamp - placed_at) durations in minutes.

    We approximate READY time by using the session closed_at for SERVED orders
    (since we don't store a separate ready_at column on Order).
    For simplicity: if order.status in (READY, SERVED) and session has closed_at,
    use (session.closed_at - order.placed_at) as upper-bound proxy.
    """
    rows = (
        db.execute(
            select(Order.placed_at, DiningSession.closed_at)
            .join(DiningSession, Order.session_id == DiningSession.id)
            .where(
                Order.placed_at >= since,
                Order.placed_at < until,
                Order.status.in_(["READY", "SERVED"]),
                DiningSession.closed_at.isnot(None),
            )
        )
        .all()
    )
    durations: list[float] = []
    for placed_at, closed_at in rows:
        m = _minutes_between(placed_at, closed_at)
        if m is not None and 1 <= m <= 120:
            durations.append(m)
    return durations


# ── cleaning speed ─────────────────────────────────────────────────────────

def _cleaning_minutes(db: Session, since: datetime, until: datetime) -> list[float]:
    rows = (
        db.execute(
            select(CleaningEvent.requested_at, CleaningEvent.completed_at)
            .where(
                CleaningEvent.requested_at >= since,
                CleaningEvent.requested_at < until,
                CleaningEvent.status == "COMPLETED",
                CleaningEvent.completed_at.isnot(None),
            )
        )
        .all()
    )
    durations: list[float] = []
    for requested_at, completed_at in rows:
        m = _minutes_between(requested_at, completed_at)
        if m is not None and 0 <= m <= 60:
            durations.append(m)
    return durations


# ── session duration ─────────────────────────────────────────────────────

def _session_minutes(db: Session, since: datetime, until: datetime) -> list[float]:
    rows = (
        db.execute(
            select(DiningSession.seated_at, DiningSession.closed_at)
            .where(
                DiningSession.seated_at >= since,
                DiningSession.seated_at < until,
                DiningSession.closed_at.isnot(None),
            )
        )
        .all()
    )
    durations: list[float] = []
    for seated_at, closed_at in rows:
        m = _minutes_between(seated_at, closed_at)
        if m is not None and 5 <= m <= 240:
            durations.append(m)
    return durations


# ── billing speed ─────────────────────────────────────────────────────────

def _billing_minutes(db: Session, since: datetime, until: datetime) -> list[float]:
    """Time from bill generation to bill PAID."""
    rows = (
        db.execute(
            select(Bill.generated_at, Bill.paid_at)
            .where(
                Bill.generated_at >= since,
                Bill.generated_at < until,
                Bill.status == "PAID",
                Bill.paid_at.isnot(None),
            )
        )
        .all()
    )
    durations: list[float] = []
    for generated_at, paid_at in rows:
        m = _minutes_between(generated_at, paid_at)
        if m is not None and 0 <= m <= 60:
            durations.append(m)
    return durations



# ── occupancy ────────────────────────────────────────────────────────────

def _occupancy_now(db: Session, tenant_id: str) -> dict[str, Any]:
    total = db.scalar(
        select(func.count(Table.id)).where(Table.tenant_id == tenant_id)
    ) or 0
    active = db.scalar(
        select(func.count(DiningSession.id)).where(
            DiningSession.tenant_id == tenant_id,
            DiningSession.status.in_(["ACTIVE", "SEATED"]),
        )
    ) or 0
    cleaning = db.scalar(
        select(func.count(CleaningEvent.id)).where(
            CleaningEvent.status.in_(["REQUESTED", "IN_PROGRESS"]),
        )
    ) or 0
    pct = round(active / total * 100) if total else 0
    return {"total": total, "active": active, "cleaning": cleaning, "pct": pct}


# ── upcoming reservations ─────────────────────────────────────────────────

def _upcoming_reservations(db: Session, tenant_id: str) -> list[dict]:
    now = _now()
    soon = now + timedelta(hours=2)
    rows = (
        db.execute(
            select(Reservation.guest_name, Reservation.party_size, Reservation.reserved_for)
            .where(
                Reservation.tenant_id == tenant_id,
                Reservation.status == "PENDING",
                Reservation.reserved_for >= now,
                Reservation.reserved_for <= soon,
            )
            .order_by(Reservation.reserved_for)
        )
        .all()
    )
    return [
        {
            "guest": r.guest_name,
            "party_size": r.party_size,
            "reserved_for": _as_utc(r.reserved_for).isoformat(),
        }
        for r in rows
    ]


# ── wait time estimate ────────────────────────────────────────────────────

def _wait_time_estimate(
    db: Session,
    tenant_id: str,
    party_size: int,
    occupancy: dict,
    baseline_session_min: float | None,
) -> dict[str, Any]:
    """
    Estimate wait for a walk-in party.
    Logic:
      - If occupancy < 80 %: very likely seated within 5 min (find a table).
      - Otherwise estimate based on remaining dining time of current sessions.
        Remaining ≈ baseline_session_min - avg_elapsed for current sessions.
    """
    now = _now()
    pct = occupancy["pct"]
    if pct < 70:
        return {"low": 0, "high": 5, "confidence": "high",
                "note": "Tables available — likely seated immediately."}

    # average elapsed time of current active sessions
    active_rows = db.execute(
        select(DiningSession.seated_at)
        .where(
            DiningSession.tenant_id == tenant_id,
            DiningSession.status.in_(["ACTIVE", "SEATED"]),
        )
    ).scalars().all()

    elapsed_mins: list[float] = []
    for seated_at in active_rows:
        m = _minutes_between(seated_at, now)
        if m is not None:
            elapsed_mins.append(m)

    avg_elapsed = sum(elapsed_mins) / len(elapsed_mins) if elapsed_mins else 0
    baseline = baseline_session_min or 60.0

    remaining = max(0, baseline - avg_elapsed)
    low  = max(0, math.floor(remaining * 0.7))
    high = math.ceil(remaining * 1.3)

    confidence = "high" if len(elapsed_mins) >= 5 else "medium" if len(elapsed_mins) >= 2 else "low"
    return {
        "low": low,
        "high": high,
        "confidence": confidence,
        "note": f"Based on {len(elapsed_mins)} active sessions averaging {round(avg_elapsed)} min elapsed.",
    }


# ── public function ───────────────────────────────────────────────────────

def compute_insights(db: Session, tenant_id: str, party_size: int = 2) -> dict[str, Any]:
    """
    Master function called by the /insights endpoint.
    Returns a fully structured payload ready for the frontend.
    """
    now      = _now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    # Baseline: 7-day window excluding today
    base_start = week_ago
    base_end   = today_start

    # ── collect raw durations ──────────────────────────────────────────
    kitchen_today    = _kitchen_prep_minutes(db, today_start, now)
    kitchen_baseline = _kitchen_prep_minutes(db, base_start, base_end)

    cleaning_today    = _cleaning_minutes(db, today_start, now)
    cleaning_baseline = _cleaning_minutes(db, base_start, base_end)

    session_today    = _session_minutes(db, today_start, now)
    session_baseline = _session_minutes(db, base_start, base_end)

    billing_today    = _billing_minutes(db, today_start, now)
    billing_baseline = _billing_minutes(db, base_start, base_end)

    # ── compute averages ───────────────────────────────────────────────
    def avg(lst: list[float]) -> float | None:
        return round(sum(lst) / len(lst), 1) if lst else None

    k_today   = avg(kitchen_today)
    k_base    = avg(kitchen_baseline)
    cl_today  = avg(cleaning_today)
    cl_base   = avg(cleaning_baseline)
    s_today   = avg(session_today)
    s_base    = avg(session_baseline)
    b_today   = avg(billing_today)
    b_base    = avg(billing_baseline)

    # ── pct changes & severity ─────────────────────────────────────────
    k_pct  = _pct_change(k_today,  k_base)  if k_today  and k_base  else None
    cl_pct = _pct_change(cl_today, cl_base) if cl_today and cl_base else None
    s_pct  = _pct_change(s_today,  s_base)  if s_today  and s_base  else None
    b_pct  = _pct_change(b_today,  b_base)  if b_today  and b_base  else None

    k_sev  = _severity(k_pct)
    cl_sev = _severity(cl_pct)
    s_sev  = _severity(s_pct)
    b_sev  = _severity(b_pct)

    # ── occupancy ──────────────────────────────────────────────────────
    occupancy = _occupancy_now(db, tenant_id)

    # ── upcoming reservations ─────────────────────────────────────────
    upcoming = _upcoming_reservations(db, tenant_id)

    # ── wait time ─────────────────────────────────────────────────────
    wait = _wait_time_estimate(db, tenant_id, party_size, occupancy, s_base)

    # ── bottleneck summary ────────────────────────────────────────────
    stages = [
        {
            "stage": "Kitchen Preparation",
            "icon": "🍳",
            "current_min": k_today,
            "baseline_min": k_base,
            "pct_change": k_pct,
            "severity": k_sev,
            "sample_count": len(kitchen_today),
            "insight": _kitchen_insight(k_today, k_base, k_pct, k_sev),
        },
        {
            "stage": "Table Cleaning",
            "icon": "🧹",
            "current_min": cl_today,
            "baseline_min": cl_base,
            "pct_change": cl_pct,
            "severity": cl_sev,
            "sample_count": len(cleaning_today),
            "insight": _cleaning_insight(cl_today, cl_base, cl_pct, cl_sev),
        },
        {
            "stage": "Dining Duration",
            "icon": "🍽",
            "current_min": s_today,
            "baseline_min": s_base,
            "pct_change": s_pct,
            "severity": s_sev,
            "sample_count": len(session_today),
            "insight": _session_insight(s_today, s_base, s_pct, s_sev),
        },
        {
            "stage": "Billing & Checkout",
            "icon": "💵",
            "current_min": b_today,
            "baseline_min": b_base,
            "pct_change": b_pct,
            "severity": b_sev,
            "sample_count": len(billing_today),
            "insight": _billing_insight(b_today, b_base, b_pct, b_sev),
        },
    ]

    # ── overall status ────────────────────────────────────────────────
    severities = [st["severity"] for st in stages]
    if "alert" in severities:
        overall = "alert"
    elif "warning" in severities:
        overall = "warning"
    else:
        overall = "ok"

    # ── manager summary bullets ───────────────────────────────────────
    summary_bullets = _build_summary(stages, occupancy, upcoming)

    return {
        "generated_at": now.isoformat(),
        "overall_status": overall,
        "occupancy": occupancy,
        "upcoming_reservations": upcoming,
        "wait_time_estimate": wait,
        "stages": stages,
        "summary": summary_bullets,
        "baseline_days": 7,
    }


# ── natural language builders ─────────────────────────────────────────────

def _kitchen_insight(today, base, pct, sev):
    if today is None:
        return "No kitchen data recorded today yet."
    if base is None or pct is None:
        return f"Kitchen average is {today} min today — not enough history to compare."
    direction = "up" if pct > 0 else "down"
    if sev == "ok":
        return f"Kitchen preparation is on track at {today} min avg ({abs(pct)}% {direction} vs. baseline)."
    if sev == "warning":
        return f"Kitchen is running {abs(pct)}% slower than usual ({today} min vs. {base} min baseline). Monitor closely."
    return f"⚠ Kitchen preparation is {abs(pct)}% above normal ({today} min vs. {base} min). This is the main bottleneck."


def _cleaning_insight(today, base, pct, sev):
    if today is None:
        return "No completed cleaning events recorded today."
    if base is None or pct is None:
        return f"Table cleaning averages {today} min today."
    direction = "up" if pct > 0 else "down"
    if sev == "ok":
        return f"Table cleaning is efficient at {today} min avg ({abs(pct)}% {direction})."
    if sev == "warning":
        return f"Cleaning is taking {abs(pct)}% longer than usual ({today} min vs. {base} min). Delays may affect seatings."
    return f"⚠ Table cleaning is {abs(pct)}% over normal ({today} min vs. {base} min). Turnaround is impacting availability."


def _session_insight(today, base, pct, sev):
    if today is None:
        return "No completed sessions today yet."
    if base is None or pct is None:
        return f"Average dining duration is {today} min today."
    direction = "higher" if pct > 0 else "lower"
    if sev == "ok":
        return f"Dining duration is normal at {today} min ({abs(pct)}% {direction} than baseline)."
    if sev == "warning":
        return f"Guests are staying {abs(pct)}% {direction} than usual ({today} min vs. {base} min). Table turnover may slow."
    return f"⚠ Dining sessions are running {abs(pct)}% {direction} than normal ({today} vs. {base} min). Review table availability."


def _billing_insight(today, base, pct, sev):
    if today is None:
        return "No completed bill payments recorded today."
    if base is None or pct is None:
        return f"Billing averages {today} min today."
    direction = "slower" if pct > 0 else "faster"
    if sev == "ok":
        return f"Checkout is smooth at {today} min avg ({abs(pct)}% {direction} than normal)."
    if sev == "warning":
        return f"Checkout is {abs(pct)}% {direction} than usual ({today} min vs. {base} min). Check cashier queue."
    return f"⚠ Billing is {abs(pct)}% above normal ({today} min vs. {base} min). Cashier may need support."


def _build_summary(stages: list[dict], occupancy: dict, upcoming: list[dict]) -> list[dict]:
    bullets: list[dict] = []

    for st in stages:
        sev = st["severity"]
        if sev == "alert":
            bullets.append({"level": "alert", "text": st["insight"]})
        elif sev == "warning":
            bullets.append({"level": "warning", "text": st["insight"]})
        elif st["current_min"] is not None:
            bullets.append({"level": "ok", "text": st["insight"]})

    # occupancy pressure
    pct = occupancy["pct"]
    if pct >= 90:
        bullets.append({"level": "alert", "text": f"Restaurant is at {pct}% capacity — full house conditions."})
    elif pct >= 75:
        bullets.append({"level": "warning", "text": f"Occupancy is high at {pct}%. Monitor table availability."})
    else:
        bullets.append({"level": "ok", "text": f"Occupancy is comfortable at {pct}%."})

    # cleaning backlog
    if occupancy["cleaning"] >= 3:
        bullets.append({"level": "warning",
                         "text": f"{occupancy['cleaning']} tables currently in cleaning — may delay seatings."})

    # upcoming pressure
    if len(upcoming) >= 3:
        bullets.append({"level": "info",
                         "text": f"{len(upcoming)} reservations arriving in the next 2 hours. Prepare tables."})
    elif upcoming:
        bullets.append({"level": "info", "text": f"{len(upcoming)} reservation(s) expected in the next 2 hours."})

    if not bullets:
        bullets.append({"level": "ok", "text": "All operational metrics are within normal range."})

    return bullets
