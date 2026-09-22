import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    user_id: str | None,
    tenant_id: str | None,
    branch_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    commit: bool = True,
) -> AuditLog:
    """
    Single write point for audit trail entries. Call this from services
    (billing_service, discount approval, user/role management, payment
    webhooks) rather than from routers directly, so the log stays
    consistent regardless of which endpoint triggered the action.

    Never raises on serialization issues — a bad audit write must not
    block the underlying business operation (bill/payment), it only
    degrades the audit trail.
    """
    try:
        old_json = json.dumps(old_value) if old_value is not None else None
    except (TypeError, ValueError):
        old_json = str(old_value)
    try:
        new_json = json.dumps(new_value) if new_value is not None else None
    except (TypeError, ValueError):
        new_json = str(new_value)

    entry = AuditLog(
        id=new_id(),
        user_id=user_id,
        tenant_id=tenant_id,
        branch_id=branch_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_value=old_json,
        new_value=new_json,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry

