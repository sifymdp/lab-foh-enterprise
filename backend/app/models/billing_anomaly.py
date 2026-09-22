from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class BillingAnomaly(Base):
    __tablename__ = "billing_anomalies"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bill_id: Mapped[str] = mapped_column(String(64), ForeignKey("bills.id", ondelete="CASCADE"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    risk_score: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(20))
    reasons: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(String(30), default="rules-v1")
    review_status: Mapped[str] = mapped_column(String(20), default="OPEN")
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
