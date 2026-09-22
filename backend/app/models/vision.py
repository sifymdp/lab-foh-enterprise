"""
Vision & CCTV Database Models
───────────────────────────────
Stores cameras, calibration data, table ROIs (polygons/boxes),
temporal vision observations, and CCTV ↔ FOH status mismatches.
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Camera(Base):
    """
    Physical or virtual CCTV camera deployed in the restaurant.
    """
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )
    floor_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("floors.id", ondelete="SET NULL"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    section: Mapped[str | None] = mapped_column(String(64), nullable=True)  # e.g., "Indoor", "Patio"
    stream_url: Mapped[str] = mapped_column(String(500), nullable=False)    # RTSP, webcam index "0", or video file path
    resolution: Mapped[str | None] = mapped_column(String(32), default="1280x720")
    fps: Mapped[float] = mapped_column(Float, default=15.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    calibration_status: Mapped[str] = mapped_column(String(32), default="UNCONFIGURED")  # UNCONFIGURED | READY | ERROR
    last_ping_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    # Relationships
    calibrations: Mapped[list["CameraCalibration"]] = relationship(
        "CameraCalibration", back_populates="camera", cascade="all, delete-orphan"
    )
    rois: Mapped[list["TableROI"]] = relationship(
        "TableROI", back_populates="camera", cascade="all, delete-orphan"
    )
    observations: Mapped[list["VisionObservation"]] = relationship(
        "VisionObservation", back_populates="camera", cascade="all, delete-orphan"
    )
    mismatches: Mapped[list["VisionMismatch"]] = relationship(
        "VisionMismatch", back_populates="camera", cascade="all, delete-orphan"
    )


class CameraCalibration(Base):
    """
    Geometric calibration and homography transformation reference for a camera.
    """
    __tablename__ = "camera_calibrations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    camera_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cameras.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # JSON list of reference points: [{"x": 100, "y": 200, "floor_x": 10, "floor_y": 20}, ...]
    reference_points: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON 3x3 homography matrix or perspective parameters
    transformation_matrix: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="CALIBRATED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    camera: Mapped["Camera"] = relationship("Camera", back_populates="calibrations")


class TableROI(Base):
    """
    Region of Interest defining a table's physical seating zone in a camera's field of view.
    Can be a polygon (list of [x, y] coordinates) or bounding box.
    """
    __tablename__ = "table_rois"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    camera_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cameras.id", ondelete="CASCADE"), index=True, nullable=False
    )
    table_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tables.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # JSON polygon: [{"x": 100, "y": 150}, {"x": 250, "y": 150}, ...]
    polygon_points: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON bounding box: {"x": 100, "y": 150, "width": 150, "height": 100}
    bounds: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    camera: Mapped["Camera"] = relationship("Camera", back_populates="rois")
    table: Mapped["Table"] = relationship("Table")  # noqa: F821


class VisionObservation(Base):
    """
    Periodic observation snapshot of a table from the AI vision pipeline.
    """
    __tablename__ = "vision_observations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )
    camera_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cameras.id", ondelete="CASCADE"), index=True, nullable=False
    )
    table_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tables.id", ondelete="CASCADE"), index=True, nullable=False
    )
    detected_people_count: Mapped[int] = mapped_column(Integer, default=0)
    # JSON array of active ByteTrack persistent IDs: [12, 17, 19]
    tracked_person_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # UNKNOWN | POSSIBLE_OCCUPIED | OCCUPIED_CONFIRMED | POSSIBLE_EMPTY | EMPTY_CONFIRMED
    occupancy_state: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    digital_status: Mapped[str] = mapped_column(String(32), default="AVAILABLE")
    is_mismatch: Mapped[bool] = mapped_column(Boolean, default=False)
    mismatch_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, index=True)

    camera: Mapped["Camera"] = relationship("Camera", back_populates="observations")
    table: Mapped["Table"] = relationship("Table")  # noqa: F821


class VisionMismatch(Base):
    """
    Actionable discrepancy detected between FOH Digital State and physical CCTV observation.
    Requires Host / Manager human verification (or timeout auto-resolution).
    """
    __tablename__ = "vision_mismatches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )
    camera_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cameras.id", ondelete="CASCADE"), index=True, nullable=False
    )
    table_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tables.id", ondelete="CASCADE"), index=True, nullable=False
    )
    table_number: Mapped[str] = mapped_column(String(32), nullable=False)
    digital_status: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g., "AVAILABLE"
    observed_state: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g., "OCCUPIED_CONFIRMED"
    detected_people: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # UNRECORDED_OCCUPANCY | STALE_OCCUPANCY | UNPAID_WALKOUT_SUSPECT | SEATED_AT_DIRTY_TABLE
    mismatch_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # PENDING | VERIFIED_CONFIRMED | DISMISSED | AUTO_RESOLVED
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    verified_by_user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    camera: Mapped["Camera"] = relationship("Camera", back_populates="mismatches")
    table: Mapped["Table"] = relationship("Table")  # noqa: F821
    verified_by: Mapped["User | None"] = relationship("User", foreign_keys=[verified_by_user_id])  # noqa: F821
