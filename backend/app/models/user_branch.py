from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class UserBranch(Base):
    """
    Links users to multiple branches for scoping data access.
    """
    __tablename__ = "user_branches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    branch_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id]) # noqa: F821
    branch: Mapped["Branch"] = relationship("Branch", foreign_keys=[branch_id]) # noqa: F821
