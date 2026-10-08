from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.permissions import PERM_AUDIT_VIEW
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit"])


def _map_log(log: AuditLog, user_map: dict[str, User]) -> AuditLogOut:
    actor = user_map.get(log.user_id) if log.user_id else None
    return AuditLogOut(
        id=log.id,
        user_id=log.user_id,
        user_name=actor.name if actor else None,
        user_email=actor.email if actor else None,
        user_role=actor.role if actor else None,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        old_value=log.old_value,
        new_value=log.new_value,
        created_at=log.created_at,
    )


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    resource_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=300, le=1000),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission(PERM_AUDIT_VIEW)),
) -> list[AuditLogOut]:
    stmt = select(AuditLog)

    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)

    if start_date:
        try:
            sd = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            # Strip timezone for naive comparison against SQLite
            sd = sd.replace(tzinfo=None)
            stmt = stmt.where(AuditLog.created_at >= sd)
        except ValueError:
            pass

    if end_date:
        try:
            ed = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            ed = ed.replace(tzinfo=None)
            stmt = stmt.where(AuditLog.created_at <= ed)
        except ValueError:
            pass

    if search:
        search_pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                AuditLog.action.ilike(search_pattern),
                AuditLog.resource_type.ilike(search_pattern),
                AuditLog.resource_id.ilike(search_pattern),
                AuditLog.old_value.ilike(search_pattern),
                AuditLog.new_value.ilike(search_pattern),
            )
        )

    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
    logs = list(db.execute(stmt).scalars().all())

    # Pre-fetch users for name mapping
    user_ids = {l.user_id for l in logs if l.user_id}
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {u.id: u for u in users}

    return [_map_log(l, user_map) for l in logs]


@router.get("/{log_id}", response_model=AuditLogOut)
def get_audit_log_record(
    log_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission(PERM_AUDIT_VIEW)),
) -> AuditLogOut:
    """Fetch a specific audit log record by ID with actor details."""
    log = db.get(AuditLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Audit log record not found")

    actor = db.get(User, log.user_id) if log.user_id else None
    user_map = {actor.id: actor} if actor else {}
    return _map_log(log, user_map)
