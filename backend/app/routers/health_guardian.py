"""
Health Guardian - REST API Router
─────────────────────────────────
Provides endpoints for inspecting platform health metrics, 12-hour audit history,
system incidents, and triggering manual diagnostics.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_manager_or_owner
from app.database import get_db
from app.models.user import User
from app.services.health_guardian.guardian_service import (
    get_latest_health_summary,
    list_recent_audits,
    list_system_incidents,
    resolve_system_incident,
    run_comprehensive_audit,
)

router = APIRouter(prefix="/health-guardian", tags=["health-guardian"])


class ResolveIncidentIn(BaseModel):
    notes: str = "Resolved by administrator"


@router.get("/status")
def get_health_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Returns real-time platform health summary, component scores, and next scheduled audit."""
    return get_latest_health_summary(db)


@router.get("/audits")
def get_audits(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Returns recent 12-hour and manual comprehensive health audits."""
    return list_recent_audits(db, limit=limit)


@router.get("/incidents")
def get_incidents(
    status_filter: str | None = Query(None, description="OPEN | RECOVERING | RESOLVED"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Returns tracked system incidents and automated recovery audit records."""
    return list_system_incidents(db, status_filter=status_filter)


@router.post("/trigger-audit")
def trigger_audit(
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_owner),
) -> dict:
    """Manually initiates an immediate comprehensive audit and self-recovery cycle."""
    return run_comprehensive_audit(db, audit_type="MANUAL_TRIGGER")


@router.post("/resolve-incident/{incident_id}")
def resolve_incident(
    incident_id: str,
    payload: ResolveIncidentIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_owner),
) -> dict:
    """Marks an incident as acknowledged/resolved with administrator notes."""
    success = resolve_system_incident(db, incident_id, user.id, payload.notes)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return {"ok": True, "message": "Incident marked as resolved"}
