from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DiningSession(Base):
    __tablename__ = "dining_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    table_id: Mapped[str] = mapped_column(String(64), ForeignKey("tables.id"), index=True)
    # Multi-tenant fields
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )
    guest_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    party_size: Mapped[int] = mapped_column(Integer)
    seated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20))
    host_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"), nullable=True)

    # set when the session ends (close_session / mark-paid / Stripe webhook)
    # enables session duration queries without scanning status_history
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # FK back to the reservation that preceded this session (NULL for walk-ins)
    reservation_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("reservations.id"), nullable=True
    )

    # set when guest taps Request Bill on the QR page
    requested_bill_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # one Stripe PaymentIntent per session — prevents double-charging
    stripe_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # CASH | STRIPE — recorded when session closes
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # relationships
    reservation: Mapped["Reservation | None"] = relationship(  # noqa: F821
        "Reservation", back_populates="session", foreign_keys=[reservation_id]
    )
    orders: Mapped[list["Order"]] = relationship(  # noqa: F821
        "Order", back_populates="session", cascade="all, delete-orphan"
    )
    bill: Mapped["Bill | None"] = relationship(  # noqa: F821
        "Bill", back_populates="session", uselist=False
    )
