from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StatusHistory(Base):
    __tablename__ = "status_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    table_id: Mapped[str] = mapped_column(String(64), ForeignKey("tables.id"), index=True)
    # FK enforced — use SET NULL so history survives session deletion
    session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("dining_sessions.id", ondelete="SET NULL"), nullable=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # NULL on first record
    to_status: Mapped[str] = mapped_column(String(20))
    # NULL = system / camera triggered the change
    changed_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
