from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class ServiceCharge(Base):
    __tablename__ = "service_charges"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("branches.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    rate: Mapped[float] = mapped_column(Numeric(8, 5))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
