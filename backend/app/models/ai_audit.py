from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AIAuditEvent(Base):
    """Immutable audit record for AI Agent interactions and security enforcement.

    CRITICAL SECURITY REQUIREMENT:
    No financial amounts, bill IDs, payment identifiers, or confidential figures
    may be persisted into this table. Blocked events record classification and reasons only.
    """
    __tablename__ = "ai_audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    branch_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    classification: Mapped[str] = mapped_column(String(64), index=True)
    intent: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tool: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    params_redacted: Mapped[str | None] = mapped_column(Text, nullable=True)

    permission_result: Mapped[str] = mapped_column(String(32), default="ALLOWED")
    policy_result: Mapped[str] = mapped_column(String(32), default="ALLOWED")
    execution_result: Mapped[str] = mapped_column(String(32), default="SUCCESS")
    blocked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    model_used: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
