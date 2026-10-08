from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RefundRequest(Base):
    """
    Refund/discount-approval/bill-cancellation request.
    Cashier cannot approve their own request.
    Status: PENDING → APPROVED | REJECTED
    """
    __tablename__ = "refund_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bill_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("bills.id", ondelete="CASCADE"), index=True
    )
    payment_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )
    # Multi-tenant fields
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )

    requested_by: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # REFUND | DISCOUNT | CANCELLATION
    request_type: Mapped[str] = mapped_column(String(20), default="REFUND")
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    reason: Mapped[str] = mapped_column(Text)

    # PENDING | APPROVED | REJECTED
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    requester: Mapped["User"] = relationship("User", foreign_keys=[requested_by])  # noqa: F821
    approver: Mapped["User | None"] = relationship("User", foreign_keys=[approved_by])  # noqa: F821
