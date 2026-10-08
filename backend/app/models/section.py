from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Section(Base):
    """
    Normalised polygon-based floor zone (Indoor / Outdoor / Bar / VIP).

    floors.sections already stores zone data as a JSON blob for the Konva
    canvas. This table is the relational counterpart used for analytics,
    AI seating context, and capacity tracking per zone.

    section_type values: indoor | outdoor | bar | vip
    polygon_points: JSON string "[[x1,y1],[x2,y2],...]" — Konva.js compatible
    color_hex: "#RRGGBB" — tile overlay colour on the floor canvas
    """
    __tablename__ = "sections"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    floor_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("floors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Multi-tenant fields
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # indoor | outdoor | bar | vip
    section_type: Mapped[str] = mapped_column(String(20), nullable=False, default="indoor")
    # Konva.js polygon vertex array stored as JSON string
    polygon_points: Mapped[str | None] = mapped_column(Text, nullable=True)
    color_hex: Mapped[str | None] = mapped_column(String(7), nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Section id={self.id} name={self.name!r} type={self.section_type}>"
