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
    source_type: Mapped[str] = mapped_column(String(32), default="RTSP")    # RTSP | ONVIF | WEBCAM | VIDEO_FILE | DEMO_STREAM | SYNTHETIC
    is_online: Mapped[bool] = mapped_column(Boolean, default=True)
    health_status: Mapped[str] = mapped_column(String(32), default="ONLINE")  # ONLINE | OFFLINE | CONNECTING | LOW_FPS | FRAME_TIMEOUT | VISION_ERROR
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
    suggestions: Mapped[list["FloorPlanSuggestion"]] = relationship(
        "FloorPlanSuggestion", back_populates="camera", cascade="all, delete-orphan"
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


class FloorPlanSuggestion(Base):
    """
    AI-detected candidate table or position change proposed from video observation.
    Requires manager review and approval before database commit.
    """
    __tablename__ = "floor_plan_ai_suggestions"

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
    floor_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("floors.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # MATCHED | POSITION_CHANGE | SIZE_CHANGE | NEW_TABLE | REMOVED_TABLE | UNCERTAIN
    suggestion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    existing_table_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tables.id", ondelete="SET NULL"), nullable=True
    )
    table_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    suggested_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_position: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_position: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON: {"x": 340, "y": 210, "width": 120, "height": 80, "shape": "RECTANGLE", "shape_confidence": 0.91}
    detected_position: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON: {"x": 120, "y": 80, "width": 240, "height": 160} in camera pixel space
    camera_bbox: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    drift_distance: Mapped[float | None] = mapped_column(Float, nullable=True)  # px offset from stored position
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # PENDING | APPROVED | REJECTED | APPLIED | IGNORED
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    camera: Mapped["Camera"] = relationship("Camera", back_populates="suggestions")
    existing_table: Mapped["Table | None"] = relationship("Table", foreign_keys=[existing_table_id])  # noqa: F821
    reviewer: Mapped["User | None"] = relationship("User", foreign_keys=[reviewed_by])  # noqa: F821


class FloorPlanVersion(Base):
    """
    Lightweight versioning snapshot of floor plan table layouts after approved AI changes.
    """
    __tablename__ = "floor_plan_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    floor_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("floors.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # JSON array of all table positions and states at this version
    snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, index=True)

