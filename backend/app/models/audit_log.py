from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """
    Append-only log of RBAC / billing / payment actions.
    No update or delete endpoint is ever exposed for this table —
    normal users (including OWNER) can only read it, never modify it.
    """

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Multi-tenant fields
    tenant_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=True
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource_type: Mapped[str] = mapped_column(String(40), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # JSON-encoded strings — kept as TEXT so this works unmodified on SQLite and Postgres
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
