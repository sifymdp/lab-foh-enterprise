from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class SystemConfiguration(Base):
    """
    Key-value settings for each tenant/branch, supporting version control.
    """
    __tablename__ = "system_configurations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="CASCADE"), index=True, nullable=True
    )
    key: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False) # JSON or plain text value
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
