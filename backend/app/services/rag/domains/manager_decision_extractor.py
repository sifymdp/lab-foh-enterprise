"""
Manager Decision Memory RAG Knowledge Extractor
─────────────────────────────────────────────────
Maintains organizational memory for approved manager decisions:
Problem → Manager Decision → Action Taken → Outcome → Timestamp → Branch.

Allows staff and leadership to quickly query:
"Have we solved a similar problem before?"
"What did the manager do last time?"
"Which previous solution worked?"
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.services.rag.domains.registry import RAGMetadata
from app.services.rag.ingestion.ingestion_service import ingestion_service

logger = logging.getLogger(__name__)

DEFAULT_MANAGER_DECISION_RECORDS = [
    {
        "title": "Kitchen Overload & Ticket Queue Surge During Weekend Rush",
        "source": "Manager Operational Decision Log",
        "related_module": "KITCHEN / KDS",
        "content": """# Operational Incident & Manager Resolution: Kitchen Ticket Queue Surge

## 1. Problem Description
- **Incident**: Friday dinner service at 20:00. The KDS queue spiked to 26 active tickets, causing ticket wait times to reach 28 minutes.
- **Root Cause**: Two 8-top walk-in parties were seated simultaneously with three 4-top reservations, triggering a simultaneous order wave across the Saute and Grill stations.
- **Related Module**: Kitchen Operations / Host Stand Pacing.

## 2. Manager Decision & Actions Implemented
- **Decision by Manager (Shift Lead Alex)**:
  1. Immediately paused seating at the host stand for 15 minutes, holding walk-ins in the cocktail lounge with complimentary sparkling water.
  2. Reassigned the Section C back-server to the kitchen line as an expeditor assistant to plate sides and wipe rims.
  3. Temporarily 86'd the Wild Mushroom Risotto for new orders to relieve pressure on the overloaded Saute burners.

## 3. Verified Outcome & Post-Shift Assessment
- **Outcome**: Ticket queue subsided to 11 active tickets within 18 minutes. Average prep time dropped from 28 minutes back to 13.5 minutes.
- **Conclusion / Best Practice**: Stagger large party seatings by at least 12 minutes even when tables are physically ready.
""",
    },
    {
        "title": "Extended Table Cleaning Bottleneck During Shift Turnover",
        "source": "Manager Operational Decision Log",
        "related_module": "FLOOR / CLEANING",
        "content": """# Operational Incident & Manager Resolution: Prolonged Table Reset Delays

## 1. Problem Description
- **Incident**: Sunday brunch service at 12:30. Seven tables remained in 'CLEANING' status simultaneously for more than 10 minutes, leaving arriving reservation parties waiting at the host stand.
- **Root Cause**: Bussers were caught running glassware to the dish pit rather than actively resetting dining surfaces.
- **Related Module**: Floor Operations / Table Management.

## 2. Manager Decision & Actions Implemented
- **Decision by Manager (Lead Host Sarah)**:
  1. Designated one server to handle dish pit transport exclusively.
  2. Directed the remaining two bussers to perform 2-person rapid resets: one clears and sanitizes, the second immediately places linens and silverware.

## 3. Verified Outcome & Post-Shift Assessment
- **Outcome**: Average table reset duration dropped from 10.4 minutes to 3.2 minutes. All 7 tables were available within 8 minutes.
- **Conclusion / Best Practice**: Implement the two-person 'Zone Reset' technique whenever more than 4 tables enter cleaning simultaneously.
""",
    },
    {
        "title": "Walkout Suspicion Triggered by CCTV Vision Anomaly",
        "source": "Manager Operational Decision Log",
        "related_module": "CCTV VISION / SECURITY",
        "content": """# Operational Incident & Manager Resolution: CCTV Walkout Alert on Table T4

## 1. Problem Description
- **Incident**: Evening shift. CCTV vision engine flagged Table T4 with 'UNPAID_WALKOUT_SUSPECT' after 3 consecutive empty scans while digital status was still 'ACTIVE'.
- **Related Module**: Vision Intelligence / FOH Staff.

## 2. Manager Decision & Actions Implemented
- **Decision by Manager**: Checked with the assigned server before approaching the table.
- **Finding**: The server verified the guests had stepped out to take a phone call on the patio with personal belongings still on their chairs.
- **Action**: Manager updated table state to 'ACTIVE', verified CCTV detection, and dismissed the alert in the mismatch interface.

## 3. Verified Outcome & Post-Shift Assessment
- **Outcome**: Guests returned and completed dining normally without incident or guest embarrassment.
- **Best Practice**: Always perform visual human verification of personal belongings before escalating a walkout alert.
""",
    },
]


def seed_manager_decisions_knowledge(
    db: Session,
    tenant_id: str,
    branch_id: str | None = None,
) -> int:
    """Seeds baseline manager decision and operational resolution records."""
    count = 0
    for record in DEFAULT_MANAGER_DECISION_RECORDS:
        meta = RAGMetadata(
            organization_id=tenant_id,
            branch_id=branch_id,
            domain="MANAGER_DECISIONS",
            source_type="manager_decision_log",
            source_id=f"decision_{count + 1}",
            extra={"related_module": record.get("related_module", "OPERATIONS")},
        ).to_dict()

        res = ingestion_service.ingest_document(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            domain="MANAGER_DECISIONS",
            source_name=record["source"],
            title=record["title"],
            raw_content=record["content"],
            metadata=meta,
        )
        if res.get("status") in ("SUCCESS", "UNCHANGED"):
            count += 1
    logger.info("Seeded %d manager decision records for tenant %s.", count, tenant_id)
    return count
