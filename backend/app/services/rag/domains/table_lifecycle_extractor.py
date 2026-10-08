"""
Table Lifecycle RAG Knowledge Extractor
────────────────────────────────────────
Builds and maintains searchable historical knowledge around individual dining tables.
Tracks the complete operational lifecycle:
Available → Reserved → Seated → Active → Billing → Paid → Cleaning → Available.

CRITICAL SECURITY CONSTRAINT:
Strictly zero billing/payment figures (prices, currencies, credit cards) are included.
Approved operational information only (turnover, durations, statuses, mismatches).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.cleaning import CleaningEvent
from app.models.session import DiningSession
from app.models.status_history import StatusHistory
from app.models.table import Table
from app.models.vision import VisionMismatch
from app.services.rag.domains.registry import RAGMetadata
from app.services.rag.ingestion.ingestion_service import ingestion_service

logger = logging.getLogger(__name__)

DEFAULT_TABLE_LIFECYCLE_PROFILES = [
    {
        "table_number": "12",
        "title": "Table T12 Historical Operational & Lifecycle Profile",
        "source": "FOH Table History Archive",
        "content": """# Table T12 Operational Lifecycle Profile (4-Top Window Booth)

## 1. Physical Specifications & Location Characteristics
- **Capacity**: 4 guests (Booth seating).
- **Location**: Section B (Window wall, adjacent to patio access doorway).
- **Floor Position**: Coordinate (X: 420, Y: 180), Rotation: 0°.
- **Operational Nuance**: Near patio exterior door; experienced draft complaints during winter months.

## 2. Typical Lifecycle Durations & Turnover Patterns
- **Available to Seated**: Averages 4.5 minutes during peak evening hours.
- **Seated to Active (Dining Duration)**: Average dining duration is 58 minutes for dinner service.
- **Cleaning & Reset Duration**: Averages 8.2 minutes (slightly above the 5-minute standard due to booth upholstery inspection).

## 3. Historical Operational Incidents & Vision Mismatches
- **Cleaning Delay Pattern**: Frequently flagged for extended cleaning duration during Friday peak shifts when busser staffing was split between patio and main floor.
- **CCTV Vision Mismatches**: Recorded 2 'UNRECORDED_OCCUPANCY' alerts caused by guests self-seating at T12 after patio drinks before host check-in.
- **Manager Interventions**: Manager reassigned dedicated Section B busser on weekends, reducing cleaning reset time from 8.2 minutes down to 4.1 minutes.
""",
    },
    {
        "table_number": "8",
        "title": "Table T8 Historical Operational & Lifecycle Profile",
        "source": "FOH Table History Archive",
        "content": """# Table T8 Operational Lifecycle Profile (2-Top Intimate Dining)

## 1. Physical Specifications & Location Characteristics
- **Capacity**: 2 guests (Deuce table).
- **Location**: Section A (Center dining room).
- **Floor Position**: Coordinate (X: 240, Y: 120), Rotation: 0°.

## 2. Typical Lifecycle Durations & Turnover Patterns
- **Turnover Rate**: High turnover velocity — averages 2.8 turns per dinner shift.
- **Dining Duration**: Averages 42 minutes for lunch, 49 minutes for dinner.
- **Cleaning & Reset**: Rapid turnover — average reset duration is 3.4 minutes.

## 3. Operational Observations & History
- Excellent operational stability. Zero vision mismatches recorded over the last 30 operational days.
- Ideal allocation table for walk-in couples and fast corporate lunch diners.
""",
    },
]


def seed_table_lifecycle_knowledge(
    db: Session,
    tenant_id: str,
    branch_id: str | None = None,
) -> int:
    """Seeds baseline operational table lifecycle profiles."""
    count = 0
    for record in DEFAULT_TABLE_LIFECYCLE_PROFILES:
        meta = RAGMetadata(
            organization_id=tenant_id,
            branch_id=branch_id,
            domain="TABLE_LIFECYCLE",
            source_type="table_lifecycle_profile",
            source_id=f"table_{record['table_number']}",
            table_id=record["table_number"],
            extra={"table_number": record["table_number"]},
        ).to_dict()

        res = ingestion_service.ingest_document(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            domain="TABLE_LIFECYCLE",
            source_name=record["source"],
            title=record["title"],
            raw_content=record["content"],
            metadata=meta,
        )
        if res.get("status") in ("SUCCESS", "UNCHANGED"):
            count += 1
    logger.info("Seeded %d table lifecycle profiles for tenant %s.", count, tenant_id)
    return count


def sync_table_lifecycle_to_rag(
    db: Session,
    tenant_id: str,
    branch_id: str | None = None,
    days_back: int = 14,
) -> int:
    """
    Synthesizes active tables and their recent operational transitions
    into distinct searchable lifecycle knowledge records per table.
    """
    tables = db.query(Table).filter(Table.tenant_id == tenant_id).all()
    if not tables:
        return seed_table_lifecycle_knowledge(db, tenant_id, branch_id)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    count = 0

    for tbl in tables:
        # Fetch status transitions for this table
        transitions = (
            db.query(StatusHistory)
            .filter(StatusHistory.table_id == tbl.id, StatusHistory.changed_at >= cutoff)
            .order_by(StatusHistory.changed_at.desc())
            .limit(10)
            .all()
        )

        # Fetch cleaning events for this table
        cleaning_events = (
            db.query(CleaningEvent)
            .filter(CleaningEvent.table_id == tbl.id, CleaningEvent.started_at >= cutoff)
            .order_by(CleaningEvent.started_at.desc())
            .limit(5)
            .all()
        )

        # Fetch vision mismatches for this table
        mismatches = (
            db.query(VisionMismatch)
            .filter(VisionMismatch.table_id == tbl.id, VisionMismatch.created_at >= cutoff)
            .order_by(VisionMismatch.created_at.desc())
            .limit(5)
            .all()
        )

        lines = [
            f"# Table T{tbl.number} Historical Lifecycle & Operational Performance",
            f"Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "Operational performance record tracking seating velocity, transitions, and cleaning duration.\n",
            "## Table Specifications",
            f"- **Table Number**: T{tbl.number}",
            f"- **Capacity**: {tbl.capacity} seats",
            f"- **Current Operational Status**: `{tbl.status}`",
            f"- **Section / Geometry**: Type: {tbl.type}, Position: ({tbl.x}, {tbl.y})",
        ]

        lines.append("\n## Recent Status Transitions (Operational Events)")
        if transitions:
            for tr in transitions:
                time_str = tr.changed_at.strftime("%Y-%m-%d %H:%M") if tr.changed_at else "Unknown"
                lines.append(f"- [{time_str}] Changed from `{tr.from_status or 'INIT'}` → `{tr.to_status}`")
        else:
            lines.append("- No recent status transitions recorded in the selected window.")

        lines.append("\n## Cleaning Duration & Reset Performance")
        if cleaning_events:
            for ce in cleaning_events:
                dur = ce.duration_seconds // 60 if ce.duration_seconds else "N/A"
                lines.append(f"- Reset on {ce.started_at.strftime('%Y-%m-%d %H:%M')}: {dur} minutes (Status: {ce.status})")
        else:
            lines.append("- Standard cleaning performance; no prolonged cleaning anomalies recorded.")

        lines.append("\n## CCTV Vision Verification & Mismatch History")
        if mismatches:
            for mm in mismatches:
                lines.append(f"- [{mm.created_at.strftime('%Y-%m-%d')}] Anomaly: `{mm.mismatch_type}` | Status: `{mm.status}`")
        else:
            lines.append("- Zero camera vision discrepancies recorded for this table.")

        meta = RAGMetadata(
            organization_id=tenant_id,
            branch_id=branch_id or tbl.branch_id,
            domain="TABLE_LIFECYCLE",
            source_type="table_lifecycle_sync",
            source_id=f"table_{tbl.number}",
            table_id=tbl.id,
            extra={"table_number": tbl.number, "capacity": tbl.capacity},
        ).to_dict()

        res = ingestion_service.ingest_document(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id or tbl.branch_id,
            domain="TABLE_LIFECYCLE",
            source_name=f"Table T{tbl.number} Lifecycle Record",
            title=f"Table T{tbl.number} Operational Lifecycle & History",
            raw_content="\n".join(lines),
            metadata=meta,
        )
        if res.get("status") in ("SUCCESS", "UNCHANGED"):
            count += 1

    return count
