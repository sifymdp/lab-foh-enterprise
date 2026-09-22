from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Order(Base):
    """
    One order round per session/table submission.
    Status flows: RECEIVED → CONFIRMED → PREPARING → READY → SERVED
    """
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("dining_sessions.id", ondelete="CASCADE"), index=True
    )
    table_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tables.id", ondelete="CASCADE"), index=True
    )
    # Multi-tenant fields
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )

    # Staff who created/placed this order (waiter or QR guest)
    created_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # RECEIVED | CONFIRMED | PREPARING | READY | SERVED
    status: Mapped[str] = mapped_column(String(20), default="RECEIVED")

    # Kitchen notes / special instructions
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 'bot' (QR/customer) | 'waiter' (manual entry)
    source: Mapped[str] = mapped_column(String(10), default="bot")
    # PENDING | APPROVED | REJECTED
    approval_status: Mapped[str] = mapped_column(String(10), default="PENDING")

    session: Mapped["DiningSession"] = relationship(  # noqa: F821
        "DiningSession", back_populates="orders"
    )
    items: Mapped[list["OrderItem"]] = relationship(  # noqa: F821
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
