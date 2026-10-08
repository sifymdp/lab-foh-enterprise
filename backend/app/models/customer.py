from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CustomerOTP(Base):
    """Temporary OTP store for customer reservation authentication."""
    __tablename__ = "customer_otps"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=True
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CustomerWaitlistEntry(Base):
    """Customer self-service AI waitlist entry."""
    __tablename__ = "customer_waitlist"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=True
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), index=True)
    guest_name: Mapped[str] = mapped_column(String(120))
    requested_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    guests: Mapped[int] = mapped_column(Integer)
    # WAITING | NOTIFIED | SEATED | CANCELLED
    status: Mapped[str] = mapped_column(String(20), default="WAITING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
