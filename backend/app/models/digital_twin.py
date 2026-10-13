"""
Restaurant Digital Twin Database Models
──────────────────────────────────────
Persists authoritative digital twin snapshots, reconciliation states,
and isolated what-if simulation experiments.
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DigitalTwinSnapshot(Base):
    """
    Periodic or event-driven snapshot of the restaurant floor plan, table states,
    and live overlays for fast reconnection and cold starts.
    """
    __tablename__ = "digital_twin_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )
    floor_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("floors.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    # JSON containing complete table map, status summary, active dining sessions, and overlays
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    reconciliation_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, index=True)


class DigitalTwinSimulation(Base):
    """
    What-if operational simulation sandbox.
    Stores input assumptions, hypothetical adjustments, and projected capacity/workload metrics.
    Completely isolated from real operational records.
    """
    __tablename__ = "digital_twin_simulations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )
    floor_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("floors.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # SECTION_CLOSURE | CAPACITY_STRESS | SURGE_ARRIVAL | STAFF_BOTTLENECK | CUSTOM
    scenario_type: Mapped[str] = mapped_column(String(64), default="CAPACITY_STRESS", index=True)
    # Input assumptions in JSON (e.g. disabled_table_ids, arrival_surge_percent, staff_count)
    assumptions_json: Mapped[str] = mapped_column(Text, nullable=False)
    # Output metrics in JSON (e.g. max_capacity, projected_turns, bottleneck_risk, wait_time_min)
    results_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # PENDING | RUNNING | COMPLETED | FAILED
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED", index=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, index=True)
