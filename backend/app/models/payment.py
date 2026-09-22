from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Payment(Base):
    """
    One payment record per bill.
    Payment methods: CASH | CARD | UPI | QR | ONLINE
    Status: PENDING → SUCCESS | FAILED | CANCELLED | REFUNDED
    Created by cashier; confirmed via webhook or manual confirmation.
    """
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bill_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("bills.id", ondelete="CASCADE"), unique=True, index=True
    )
    # Multi-tenant fields
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )

    # CASH | CARD | UPI | QR | ONLINE  (STRIPE kept for backward compat)
    method: Mapped[str] = mapped_column(String(20))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))

    # External transaction reference (UPI txn ID, card auth code, etc.)
    # Do NOT store full card numbers or CVV — only safe references
    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Legacy Stripe field — kept for backward compat
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # PENDING | SUCCESS | FAILED | CANCELLED | REFUNDED
    payment_status: Mapped[str] = mapped_column(String(20), default="SUCCESS", index=True)

    # Who processed the payment
    created_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Shift FK — links payment to the cashier's shift for reconciliation
    shift_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("cashier_shifts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    bill: Mapped["Bill"] = relationship("Bill", back_populates="payment")  # noqa: F821
    transactions: Mapped[list["PaymentTransaction"]] = relationship(  # noqa: F821
        "PaymentTransaction", back_populates="payment", cascade="all, delete-orphan"
    )
    processor: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])  # noqa: F821


class PaymentTransaction(Base):
    """
    Log of every payment event/webhook received for a payment.
    The event_id unique constraint is the idempotency key.
    """
    __tablename__ = "payment_transactions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("payments.id", ondelete="CASCADE"), index=True
    )
    # Unique event/webhook ID — prevents duplicate processing
    stripe_event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # e.g. payment.succeeded, payment.failed, payment_intent.succeeded
    event_type: Mapped[str] = mapped_column(String(80))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    payment: Mapped["Payment"] = relationship("Payment", back_populates="transactions")  # noqa: F821
