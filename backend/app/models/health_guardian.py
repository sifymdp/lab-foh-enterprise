"""
Enterprise Backend Health Guardian Database Models
──────────────────────────────────────────────────
Persists 12-hour comprehensive audit runs, component-level health check results,
system incidents, automated recovery action logs, and alerts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HealthAudit(Base):
    """
    Comprehensive or periodic health audit record.
    Tracks scheduled and actual runs (every 12 hours), overall platform status,
    and aggregate diagnostic metrics.
    """
    __tablename__ = "health_audits"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # SCHEDULED_12H | PERIODIC_PROBE | MANUAL_TRIGGER | EVENT_TRIGGERED
    audit_type: Mapped[str] = mapped_column(String(32), default="SCHEDULED_12H", index=True)
    # HEALTHY | DEGRADED | UNHEALTHY | RECOVERING | UNKNOWN
    overall_status: Mapped[str] = mapped_column(String(32), default="HEALTHY", index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    # JSON dictionary summary of results across all components
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Active execution lock owner identifier (hostname or worker id)
    lock_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    next_scheduled_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    results: Mapped[list["HealthCheckResult"]] = relationship(
        "HealthCheckResult", back_populates="audit", cascade="all, delete-orphan"
    )


class HealthCheckResult(Base):
    """
    Granular probe result for a specific subsystem during an audit cycle.
    """
    __tablename__ = "health_check_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    audit_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("health_audits.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # DATABASE | API_ROUTES | WEBSOCKETS | JOBS | AI_RAG | CCTV_VISION | DIGITAL_TWIN | STORAGE
    component: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    # PASS | WARN | FAIL | SKIPPED
    status: Mapped[str] = mapped_column(String(32), default="PASS", index=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(String(500), default="Healthy")
    # Structured JSON metrics e.g. {"pool_size": 10, "checked_out": 2, "error_rate": 0.0}
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    audit: Mapped["HealthAudit"] = relationship("HealthAudit", back_populates="results")


class SystemIncident(Base):
    """
    Tracked operational incident discovered by health checks or runtime errors.
    """
    __tablename__ = "system_incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    component: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    # LOW | MEDIUM | HIGH | CRITICAL
    severity: Mapped[str] = mapped_column(String(32), default="MEDIUM", index=True)
    # TRANSIENT | DEPENDENCY_UNAVAILABLE | RESOURCE_EXHAUSTION | CONFIGURATION_ERROR |
    # AUTH_ERROR | DATA_INTEGRITY_VIOLATION | APPLICATION_DEFECT | SECURITY_INCIDENT | UNKNOWN
    error_category: Mapped[str] = mapped_column(String(64), default="UNKNOWN", index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # OPEN | RECOVERING | RESOLVED | ESCALATED | SUPPRESSED
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    recovery_logs: Mapped[list["RecoveryActionLog"]] = relationship(
        "RecoveryActionLog", back_populates="incident", cascade="all, delete-orphan"
    )


class RecoveryActionLog(Base):
    """
    Immutable audit log of an automated or manual recovery action taken for an incident.
    """
    __tablename__ = "recovery_action_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("system_incidents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    action_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # ATTEMPTED | SUCCESS | FAILED | ABORTED | VERIFICATION_FAILED
    status: Mapped[str] = mapped_column(String(32), default="ATTEMPTED")
    preconditions_met: Mapped[bool] = mapped_column(Boolean, default=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    incident: Mapped["SystemIncident"] = relationship("SystemIncident", back_populates="recovery_logs")


class HealthAlert(Base):
    """
    Deduplicated alerts emitted by the health guardian with cooldown support.
    """
    __tablename__ = "health_alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    component: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="MEDIUM")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # PENDING | SENT | ACKNOWLEDGED | RESOLVED
    status: Mapped[str] = mapped_column(String(32), default="SENT")
    channel: Mapped[str] = mapped_column(String(32), default="SYSTEM_LOG")  # SYSTEM_LOG | WEBSOCKET | EMAIL | WEBHOOK
    dedup_key: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
