from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class RolePermission(Base):
    """
    Links specific permission strings to roles.
    """
    __tablename__ = "role_permissions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("roles.id", ondelete="CASCADE"), index=True
    )
    permission: Mapped[str] = mapped_column(String(120), nullable=False)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )

    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="permissions")
