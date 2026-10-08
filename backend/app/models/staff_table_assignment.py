from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class StaffTableAssignment(Base):
    """
    Tracks waiter-to-table assignments.
    """
    __tablename__ = "staff_table_assignments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    staff_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    table_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tables.id", ondelete="CASCADE"), index=True
    )
    branch_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    assigned_by: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE")
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Relationships
    staff: Mapped["User"] = relationship("User", foreign_keys=[staff_id]) # noqa: F821
    table: Mapped["Table"] = relationship("Table", foreign_keys=[table_id]) # noqa: F821
    editor: Mapped["User"] = relationship("User", foreign_keys=[assigned_by]) # noqa: F821
