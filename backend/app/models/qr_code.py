from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TableQRCode(Base):
    """
    Secure QR token for each table. The QR URL encodes the token, not the
    raw table ID, so guests can't guess other tables' order endpoints.

    One active token per table at a time (is_active=True).
    Tokens can be rotated by setting the current one inactive and creating a new one.
    For MVP: tokens don't expire (expires_at=NULL). Expiry can be enabled in Phase 2.

    QR URL pattern:  /menu?token=<token>
    The /menu endpoint resolves the token → table_id internally.
    """
    __tablename__ = "table_qr_codes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    table_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tables.id", ondelete="CASCADE"), index=True
    )
    # UUIDv4 token — included in the QR code URL, never the raw table_id
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # NULL = never expires (MVP default); set a datetime to enable rotation
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    table: Mapped["Table"] = relationship("Table")  # noqa: F821
