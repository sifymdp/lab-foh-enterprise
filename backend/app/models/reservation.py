from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Reservation(Base):
    """
    A held table slot that exists BEFORE any dining session.
    Lifecycle: PENDING → SEATED (when host seats the party)
                       → RELEASED (manual release or no-show auto-release)
                       → CANCELLED (guest cancels)
    The auto-release background worker checks: status=PENDING AND reserved_until < now
    and flips to RELEASED, then sets table status back to AVAILABLE.
    """
    __tablename__ = "reservations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    table_id: Mapped[str] = mapped_column(String(64), ForeignKey("tables.id"), index=True)
    # Multi-tenant fields
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    guest_name: Mapped[str] = mapped_column(String(120))
    party_size: Mapped[int] = mapped_column(Integer)
    # when the party is expected to arrive
    reserved_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # auto-release fires after this passes with no seating
    reserved_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # PENDING | SEATED | RELEASED | CANCELLED | CONFIRMED | EXPIRED
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    payment_status: Mapped[str] = mapped_column(String(20), default="UNPAID")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # one reservation becomes at most one session
    session: Mapped["DiningSession | None"] = relationship(  # noqa: F821
        "DiningSession",
        back_populates="reservation",
        foreign_keys="DiningSession.reservation_id",
        uselist=False,
    )
    table: Mapped["Table"] = relationship("Table", foreign_keys=[table_id])  # noqa: F821
