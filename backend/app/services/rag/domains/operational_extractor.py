"""
Operational Event Knowledge Extractor for RAG
──────────────────────────────────────────────
Extracts meaningful operational events (turnaround delays, long dining sessions,
and peak bottlenecks) and indexes them into the 'OPERATIONAL_HISTORY' domain.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.cleaning import CleaningEvent
from app.models.session import DiningSession
from app.models.table import Table
from app.services.rag.ingestion.ingestion_service import ingestion_service

logger = logging.getLogger(__name__)


def sync_operational_history_to_rag(
    db: Session,
    tenant_id: str,
    branch_id: str | None = None,
    days_back: int = 14,
) -> int:
    """
    Summarizes meaningful operational events from the past N days
    into compact, searchable knowledge records.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days_back)

    # 1. Query extended dining sessions (> 75 minutes)
    extended_sessions = (
        db.query(DiningSession)
        .join(Table, DiningSession.table_id == Table.id)
        .filter(
            Table.tenant_id == tenant_id,
            DiningSession.seated_at >= cutoff,
        )
        .all()
    )

    # 2. Query prolonged cleaning events (> 8 minutes)
    cleaning_events = (
        db.query(CleaningEvent)
        .join(Table, CleaningEvent.table_id == Table.id)
        .filter(
            Table.tenant_id == tenant_id,
            CleaningEvent.started_at >= cutoff,
        )
        .all()
    )

    lines = [
        f"# Operational Shift & Bottleneck Archive (Past {days_back} Days)",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "Contains summarized historical performance signals to explain turnover and delay trends.\n",
    ]

    lines.append("## Dining Session Duration Observations")
    long_count = 0
    for s in extended_sessions:
        if s.seated_at and s.closed_at:
            dur = (s.closed_at - s.seated_at).total_seconds() / 60.0
            if dur > 70.0:
                long_count += 1
                table_num = s.table.number if s.table else "Unknown"
                lines.append(
                    f"- Table {table_num}: Party of {s.party_size or 2} occupied table for {round(dur)} mins "
                    f"(Seated {s.seated_at.strftime('%Y-%m-%d %H:%M')}). Exceeded target turnaround."
                )

    if long_count == 0:
        lines.append("- No significantly delayed dining sessions recorded in this period.")

    lines.append("\n## Table Cleaning & Turnaround Bottlenecks")
    clean_delay_count = 0
    for c in cleaning_events:
        if c.started_at and c.completed_at:
            c_dur = (c.completed_at - c.started_at).total_seconds() / 60.0
            if c_dur > 8.0:
                clean_delay_count += 1
                lines.append(
                    f"- Table {c.table_number or c.table_id}: Cleaning duration was {round(c_dur, 1)} mins "
                    f"on {c.started_at.strftime('%Y-%m-%d %H:%M')}. Exceeded target 3-5 min SOP window."
                )

    if clean_delay_count == 0:
        lines.append("- Table turnover cleaning durations remained consistently within target SOP limits.")

    full_text = "\n".join(lines)
    doc_title = f"Operational Bottlenecks & Turnaround Archive ({days_back}d Window)"

    res = ingestion_service.ingest_document(
        db=db,
        tenant_id=tenant_id,
        branch_id=branch_id,
        domain="OPERATIONAL_HISTORY",
        source_name="FOH Operational Analytics Engine",
        title=doc_title,
        raw_content=full_text,
        metadata={
            "domain": "OPERATIONAL_HISTORY",
            "delayed_sessions_count": long_count,
            "delayed_cleanings_count": clean_delay_count,
        },
    )

    logger.info("Indexed operational history archive for tenant %s (status=%s).", tenant_id, res.get("status"))
    return 1 if res.get("status") in ("SUCCESS", "UNCHANGED") else 0
