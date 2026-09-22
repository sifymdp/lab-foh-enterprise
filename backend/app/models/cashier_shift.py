from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CashierShift(Base):
    """
    Tracks a single cashier work shift.
    Workflow: opened_at (start) → closed_at (end) → cash reconciliation.
    Status: OPEN | CLOSED
    """
    __tablename__ = "cashier_shifts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cashier_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Multi-tenant fields
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )

    # Opening cash in the till at shift start
    opening_cash: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    # Closing cash declared by cashier at shift end
    closing_cash: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Payment-method totals accumulated during shift
    cash_sales: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    card_sales: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    upi_sales: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    qr_sales: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    online_sales: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    refund_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    discount_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    # Computed at shift close: opening_cash + cash_sales - refunds
    expected_cash: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Actual cash counted at end
    actual_cash: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    # actual_cash - expected_cash (negative = shortage, positive = overage)
    difference: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # OPEN | CLOSED
    status: Mapped[str] = mapped_column(String(20), default="OPEN")

    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    cashier: Mapped["User"] = relationship("User", foreign_keys=[cashier_id])  # noqa: F821
