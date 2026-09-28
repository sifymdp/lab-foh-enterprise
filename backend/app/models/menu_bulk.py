from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MenuImport(Base):
    """
    Tracks an uploaded Excel menu file through its lifecycle:
    PENDING_REVIEW -> APPROVED (applied to DB) or REJECTED.
    """
    __tablename__ = "menu_imports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    uploaded_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    file_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="PENDING_REVIEW", index=True)

    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    deactivated_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    raw_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    items: Mapped[list["MenuImportItem"]] = relationship(
        "MenuImportItem", back_populates="menu_import", cascade="all, delete-orphan", order_by="MenuImportItem.row_number"
    )
    uploader: Mapped["User | None"] = relationship("User", foreign_keys=[uploaded_by])  # noqa: F821
    approver: Mapped["User | None"] = relationship("User", foreign_keys=[approved_by])  # noqa: F821


class MenuImportItem(Base):
    """
    Individual row parsed and categorized from the uploaded menu Excel.
    Actions: NEW | UPDATED | UNCHANGED | ERROR | POSSIBLE_DUPLICATE
    """
    __tablename__ = "menu_import_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    import_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("menu_imports.id", ondelete="CASCADE"), index=True
    )
    row_number: Mapped[int] = mapped_column(Integer)
    item_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    item_name: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(60))
    action: Mapped[str] = mapped_column(String(30), index=True)  # NEW, UPDATED, UNCHANGED, ERROR, POSSIBLE_DUPLICATE
    status: Mapped[str] = mapped_column(String(20), default="VALID")  # VALID, WARNING, ERROR

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    warning_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    similarity_match: Mapped[str | None] = mapped_column(String(120), nullable=True)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # JSON text storing complete snapshots before & after
    old_values: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_values: Mapped[str | None] = mapped_column(Text, nullable=True)

    menu_import: Mapped["MenuImport"] = relationship("MenuImport", back_populates="items")


class MenuVersion(Base):
    """
    Immutable versioned snapshot of the restaurant menu, created each time
    a bulk Excel import or major catalog revision is approved.
    """
    __tablename__ = "menu_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_number: Mapped[int] = mapped_column(Integer, index=True)
    version_tag: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "v1", "v2"
    tenant_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    import_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("menu_imports.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_items: Mapped[int] = mapped_column(Integer, default=0)
    new_items_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_items_count: Mapped[int] = mapped_column(Integer, default=0)
    deactivated_items_count: Mapped[int] = mapped_column(Integer, default=0)

    # Complete JSON snapshot of all active menu items at this version point
    snapshot_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
    change_logs: Mapped[list["MenuChangeLog"]] = relationship(
        "MenuChangeLog", back_populates="version", cascade="all, delete-orphan"
    )


class MenuChangeLog(Base):
    """
    Granular audit log of exact field changes applied during a menu version release.
    """
    __tablename__ = "menu_change_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("menu_versions.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    item_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    item_name: Mapped[str] = mapped_column(String(120), index=True)
    field_name: Mapped[str] = mapped_column(String(60))  # e.g. "price", "category", "available"
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    version: Mapped["MenuVersion"] = relationship("MenuVersion", back_populates="change_logs")
