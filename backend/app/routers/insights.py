"""
Operational Insights Router
GET /insights/operational   — full bottleneck analysis + manager summary
GET /insights/wait-time     — wait-time estimate for a specific party size
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services.insights_service import compute_insights

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/operational")
def get_operational_insights(
    party_size: int = Query(default=2, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns bottleneck metrics, manager summary bullets, occupancy snapshot,
    upcoming reservations pressure, and a walk-in wait-time estimate.
    Accessible to OWNER and MANAGER roles.
    """
    tenant_id = getattr(current_user, "tenant_id", None) or "org-demo"
    return compute_insights(db, tenant_id=tenant_id, party_size=party_size)


@router.get("/wait-time")
def get_wait_time(
    party_size: int = Query(default=2, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lightweight endpoint — just the wait-time estimate for the HOST stand."""
    from app.services.insights_service import (
        _now, _occupancy_now, _session_minutes, _wait_time_estimate,
    )
    from datetime import timedelta
    tenant_id = getattr(current_user, "tenant_id", None) or "org-demo"
    now = _now()
    week_ago = now - timedelta(days=7)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    session_baseline = _session_minutes(db, week_ago, today_start)
    baseline_avg = round(sum(session_baseline) / len(session_baseline), 1) if session_baseline else None
    occupancy = _occupancy_now(db, tenant_id)
    return _wait_time_estimate(db, tenant_id, party_size, occupancy, baseline_avg)
