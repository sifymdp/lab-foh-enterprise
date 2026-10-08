"""Audit Event Recorder for AI Agent."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.models.ai_audit import AIAuditEvent
from app.services.ai_agent.security.redactor import safe_json_dumps

logger = logging.getLogger(__name__)


def record_ai_audit(
    db: Session,
    user_id: str | None,
    tenant_id: str | None,
    branch_id: str | None,
    conversation_id: str | None,
    classification: str,
    intent: str | None,
    tool: str | None = None,
    params: dict | None = None,
    permission_result: str = "ALLOWED",
    policy_result: str = "ALLOWED",
    execution_result: str = "SUCCESS",
    blocked_reason: str | None = None,
    model_used: str | None = None,
    provider_used: str | None = None,
    latency_ms: float | None = None,
) -> None:
    """Safely commits an audit log entry for an AI operation.

    Never persists financial data.
    """
    try:
        record = AIAuditEvent(
            id=new_id(),
            user_id=user_id,
            tenant_id=tenant_id,
            branch_id=branch_id,
            conversation_id=conversation_id,
            created_at=datetime.now(timezone.utc),
            classification=classification,
            intent=intent,
            tool=tool,
            params_redacted=safe_json_dumps(params) if params else None,
            permission_result=permission_result,
            policy_result=policy_result,
            execution_result=execution_result,
            blocked_reason=blocked_reason,
            model_used=model_used,
            provider_used=provider_used,
            latency_ms=latency_ms,
        )
        db.add(record)
        db.commit()
    except Exception as exc:
        logger.error("Failed to commit AI audit event: %s", exc)
        db.rollback()
