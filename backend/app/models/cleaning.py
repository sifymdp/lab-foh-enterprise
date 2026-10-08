from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CleaningEvent(Base):
    """
    Created automatically the moment a session closes — either via the
    Stripe webhook (card payment confirmed) or a staff Mark Paid tap (cash).

    Camera monitors the table every 30 seconds after a 1-minute grace period.
    Dirty signal uses plates, bowls, and glasses ONLY — cutlery is excluded
    because it is reset on clean tables too (design doc p.8).

    Status lifecycle:
        REQUESTED → IN_PROGRESS → COMPLETED
                                → SKIPPED   (manager override)

    Alert thresholds (design doc p.9):
        10 min still dirty → alert_fired_at set, section server notified
        20 min still dirty → escalated_at set, manager notified
        No camera          → time-based fallback alert fires at 15 min
    """
    __tablename__ = "cleaning_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    table_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tables.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # NULL if cleaning was triggered outside a session (e.g. manual reset)
    dining_session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("dining_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Staff member who cleaned; NULL when camera auto-confirmed clean
    assigned_to_user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # REQUESTED | IN_PROGRESS | COMPLETED | SKIPPED
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="REQUESTED")

    # YOLO verification fields
    # True when camera confirmed the table is clear (no plates/bowls/glasses)
    verified_by_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Confidence score from the final clearing scan (0.0 – 1.0)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Path to the OpenCV frame snapshot that confirmed clear
    verification_frame_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Escalation timestamps — populated by the alert worker
    alert_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Lifecycle timestamps
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Computed on completion: (completed_at - requested_at) in seconds
    # Used by the cleaning_performance TimescaleDB continuous aggregate
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # One CleaningEvent may be linked to the DepartureEvent that triggered it
    departure_event: Mapped["DepartureEvent | None"] = relationship(  # noqa: F821
        "DepartureEvent", back_populates="cleaning_event", uselist=False
    )

    def __repr__(self) -> str:
        return f"<CleaningEvent id={self.id} table_id={self.table_id} status={self.status}>"


class DepartureEvent(Base):
    """
    Logged when YOLOv8 confirms guests have left a PAID table.
    Requires 3 consecutive empty scans (90 seconds) before firing —
    same rule as arrival detection (design doc p.7).

    Also created manually (staff tap) or inferred from payment events
    when no camera is configured.

    source values:
        YOLO    — 3 consecutive empty scans confirmed by YOLOv8
        MANUAL  — staff triggered the departure manually
        PAYMENT — inferred from Stripe webhook or Mark Paid tap (no camera)

    The background worker reads unlinked DepartureEvents and creates the
    corresponding CleaningEvent, then sets cleaning_event_id here.
    """
    __tablename__ = "departure_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    table_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tables.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # NULL for walk-ins where session is not yet linked at detection time
    dining_session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("dining_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Set by the worker once the CleaningEvent is created for this departure
    cleaning_event_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("cleaning_events.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # YOLO | MANUAL | PAYMENT
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="YOLO")

    # YOLO detection metadata (NULL for MANUAL and PAYMENT sources)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # How many consecutive empty scans triggered this event (target: 3)
    consecutive_empty_scans: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # OpenCV / camera metadata
    camera_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    frame_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set after human confirmation or a second YOLO validation pass
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cleaning_event: Mapped["CleaningEvent | None"] = relationship(
        "CleaningEvent",
        back_populates="departure_event",
        foreign_keys=[cleaning_event_id],
    )

    def __repr__(self) -> str:
        return (
            f"<DepartureEvent id={self.id} table_id={self.table_id} "
            f"source={self.source} detected_at={self.detected_at}>"
        )
