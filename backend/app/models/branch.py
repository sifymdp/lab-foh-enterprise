from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Branch(Base):
    """
    Location/outlet of an organization.
    Example: "Joe's Pizza - NYC", "Joe's Pizza - LA", etc.
    """

    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(  # noqa: F821
        "Organization", back_populates="branches"
    )
    users: Mapped[list["User"]] = relationship(  # noqa: F821
        "User", back_populates="branch", foreign_keys="User.branch_id"
    )
