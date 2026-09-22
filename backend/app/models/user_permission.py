from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class UserPermission(Base):
    """
    Direct user permission assignments (overriding role defaults).
    """
    __tablename__ = "user_permissions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    permission: Mapped[str] = mapped_column(String(120), nullable=False)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id]) # noqa: F821
