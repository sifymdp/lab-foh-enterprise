from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from app.database import Base


class OrderAnalytics(Base):
    """Store historical data for each completed order (Member 2 KDS Feature)."""
    __tablename__ = "order_analytics"

    id = Column(String(64), primary_key=True)
    order_id = Column(String(64), unique=True, index=True)

    # Multi-tenant fields
    tenant_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=True)
    branch_id = Column(String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True)

    # What was ordered
    item_name = Column(String(120), index=True)
    item_count = Column(Integer)
    station = Column(String(32), index=True)

    # How long it took (in minutes)
    actual_cooking_time = Column(Float)

    # When it happened
    created_at = Column(DateTime, default=datetime.utcnow)

    # Complexity: "simple", "medium", "complex"
    complexity = Column(String(20), default="medium")
