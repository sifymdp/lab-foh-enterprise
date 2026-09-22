from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Discount(Base):
    __tablename__ = "discounts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bill_id: Mapped[str] = mapped_column(String(64), ForeignKey("bills.id", ondelete="CASCADE"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("branches.id"), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64))
    percent: Mapped[float] = mapped_column(Numeric(8, 3))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="APPROVED")
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
