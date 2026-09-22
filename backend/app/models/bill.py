from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Bill(Base):
    """
    One bill per dining session.
    Status flow: DRAFT → OPEN → READY_FOR_PAYMENT → PAID | CANCELLED | REFUNDED
    Contains full financial breakdown: items, discount, service charge, tax, grand total.
    """
    __tablename__ = "bills"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Human-readable sequential bill number (e.g. "B1024")
    bill_number: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("dining_sessions.id", ondelete="CASCADE"), unique=True, index=True, nullable=True
    )
    order_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Multi-tenant fields
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )

    # Who created / last updated this bill
    created_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Financial fields — use Numeric(10,2) for all money; never float arithmetic
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    discount_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    service_charge_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    # Stripe legacy — kept for backward compat with QR guest-payment flow
    stripe_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_client_secret: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Notes / remarks
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # DRAFT | OPEN | READY_FOR_PAYMENT | PAID | CANCELLED | REFUNDED
    # kept as 'status' for backward compat; bill_status is the canonical new field
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    bill_status: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Relationships
    session: Mapped["DiningSession | None"] = relationship(  # noqa: F821
        "DiningSession", back_populates="bill", foreign_keys=[session_id]
    )
    payment: Mapped["Payment | None"] = relationship(  # noqa: F821
        "Payment", back_populates="bill", uselist=False
    )
    creator: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[created_by]
    )
