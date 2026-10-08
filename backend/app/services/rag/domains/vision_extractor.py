"""
Vision Event Knowledge Extractor for RAG
─────────────────────────────────────────
Summarizes camera vision discrepancies, table detection instability,
and CCTV vs FOH digital state mismatches into searchable knowledge.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.vision import VisionMismatch
from app.services.rag.ingestion.ingestion_service import ingestion_service

logger = logging.getLogger(__name__)


def sync_vision_events_to_rag(
    db: Session,
    tenant_id: str,
    branch_id: str | None = None,
    days_back: int = 14,
) -> int:
    """
    Summarizes recent CCTV/YOLO vision mismatches and camera events
    into a structured knowledge document within the 'VISION' domain.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days_back)

    mismatches = (
        db.query(VisionMismatch)
        .filter(
            VisionMismatch.tenant_id == tenant_id,
            VisionMismatch.created_at >= cutoff,
        )
        .order_by(VisionMismatch.created_at.desc())
        .limit(50)
        .all()
    )

    lines = [
        f"# CCTV Vision Intelligence & Anomaly Archive (Past {days_back} Days)",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "Summarizes spatial and temporal discrepancies between physical CCTV cameras and FOH digital states.\n",
    ]

    lines.append("## Table Discrepancy & Mismatch Log")
    if not mismatches:
        lines.append("- No camera vision mismatches recorded in the selected operational window.")
    else:
        for m in mismatches:
            time_str = m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else "Unknown"
            res_str = f"Status: {m.status}"
            if m.verification_notes:
                res_str += f" | Notes: {m.verification_notes}"

            lines.append(
                f"- Table {m.table_number}: Mismatch Type '{m.mismatch_type}' detected by Camera {m.camera_id} at {time_str}. "
                f"Observed {m.observed_state} ({m.detected_people} persons, confidence {round(m.confidence, 2)}) "
                f"while digital status was {m.digital_status}. {res_str}."
            )

    full_text = "\n".join(lines)
    doc_title = f"CCTV Vision Anomaly & Mismatch Log ({days_back}d Window)"

    res = ingestion_service.ingest_document(
        db=db,
        tenant_id=tenant_id,
        branch_id=branch_id,
        domain="VISION",
        source_name="FOH Computer Vision Pipeline",
        title=doc_title,
        raw_content=full_text,
        metadata={
            "domain": "VISION",
            "mismatches_indexed_count": len(mismatches),
        },
    )

    logger.info("Indexed vision events into RAG for tenant %s (count=%d).", tenant_id, len(mismatches))
    return len(mismatches)
