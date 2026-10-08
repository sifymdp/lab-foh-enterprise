"""
Customer Experience RAG Knowledge Extractor
─────────────────────────────────────────────
Stores, normalizes, and indexes customer complaints, service feedback,
reviews, recurring service defects, and operational resolution histories.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.customer import CustomerWaitlistEntry
from app.services.rag.domains.registry import RAGMetadata
from app.services.rag.ingestion.ingestion_service import ingestion_service

logger = logging.getLogger(__name__)

DEFAULT_CUSTOMER_EXPERIENCE_RECORDS = [
    {
        "title": "Customer Feedback & Complaints Log: Q3 Service Performance",
        "source": "Guest Relations & Feedback Archive",
        "source_type": "complaints_summary",
        "content": """# Customer Experience & Complaints Analysis: Q3

## 1. Summary of Most Common Guest Complaints
The three most frequently reported customer concerns across dinner service shifts are:
1. **Extended Table Reset Times (38% of complaints)**: Guests with reservations reported waiting 10-15 minutes past their booking time while previous tables were in 'CLEANING' status.
2. **Appetizer vs Main Course Pacing (27% of complaints)**: Appetizers arriving simultaneously with or after main courses during peak rush (19:30 - 21:00).
3. **Drafty Seating Near Patio Entrance (18% of complaints)**: Guests seated at Tables T11 and T12 reported cold drafts when the patio sliding door was frequently left open.

## 2. Customer Reviews & Sentiment Highlights
- **High Praise**: Food quality, cocktail presentation, and server friendliness received consistent 5-star ratings.
- **Service Friction Points**: Weekend wait times quoted at the host stand frequently exceeded the initial estimate by 10 to 15 minutes when walk-in volume surged unexpectedly.

## 3. Resolution History & Implemented Action Plans
- **Pacing Protocol Update**: Implemented a mandatory 7-minute kitchen fire hold between appetizer confirmation and main course firing on the POS terminal.
- **Patio Door Automatic Closer**: Installed an automatic pneumatic door closer on the patio exit to resolve draft complaints around Tables T11 and T12.
- **Wait Time Buffer**: Added a 10-minute dynamic buffer to the digital waitlist estimation algorithm during 100% dining room occupancy periods.
""",
    },
    {
        "title": "Front-of-House Service Recovery & Resolution Protocol",
        "source": "Customer Service Operations Manual",
        "source_type": "resolution_policy",
        "content": """# Front-of-House Service Recovery Protocol (LAST Framework)

## 1. The LAST Service Recovery Standard
When a guest reports an issue with food, pacing, or seating:
- **L - Listen**: Allow the guest to explain without interruption; acknowledge their perspective empathetically.
- **A - Apologize**: Offer a sincere, personal apology on behalf of the restaurant without blaming kitchen staff or systems.
- **S - Solve**: Propose an immediate concrete remedy:
  - Food quality issue: Immediately re-fire dish with kitchen rush priority; offer complimentary beverage or dessert.
  - Table delay: Offer complimentary beverage at the lounge while table reset is expedited.
- **T - Thank**: Thank the guest for bringing the issue to our attention.

## 2. Escalation Thresholds for Shift Managers
- Delays exceeding 25 minutes for main courses require immediate table visit by the Shift Manager.
- Foreign object or allergen concern requires immediate dish removal, manager check-in, and incident report filing.
""",
    },
]


def seed_customer_experience_knowledge(
    db: Session,
    tenant_id: str,
    branch_id: str | None = None,
) -> int:
    """Idempotently seeds standard customer experience and complaint resolution knowledge."""
    count = 0
    for record in DEFAULT_CUSTOMER_EXPERIENCE_RECORDS:
        meta = RAGMetadata(
            organization_id=tenant_id,
            branch_id=branch_id,
            domain="CUSTOMER_EXPERIENCE",
            source_type=record.get("source_type", "feedback_log"),
            source_id=f"ce_{count + 1}",
        ).to_dict()

        res = ingestion_service.ingest_document(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            domain="CUSTOMER_EXPERIENCE",
            source_name=record["source"],
            title=record["title"],
            raw_content=record["content"],
            metadata=meta,
        )
        if res.get("status") in ("SUCCESS", "UNCHANGED"):
            count += 1
    logger.info("Seeded %d customer experience records for tenant %s.", count, tenant_id)
    return count


def sync_customer_experience_to_rag(
    db: Session,
    tenant_id: str,
    branch_id: str | None = None,
) -> int:
    """Syncs live waitlist and guest feedback records into the CUSTOMER_EXPERIENCE domain."""
    waitlist_entries = (
        db.query(CustomerWaitlistEntry)
        .filter(CustomerWaitlistEntry.tenant_id == tenant_id)
        .order_by(CustomerWaitlistEntry.created_at.desc())
        .limit(30)
        .all()
    )

    if not waitlist_entries:
        return seed_customer_experience_knowledge(db, tenant_id, branch_id)

    lines = [
        "# Live Guest Waitlist & Service Demand Feedback",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "Summarizes recent guest queue entries, waitlist cancellations, and seating velocity.\n",
        "## Recent Waitlist Guest Activity",
    ]

    for w in waitlist_entries:
        time_str = w.created_at.strftime("%Y-%m-%d %H:%M") if w.created_at else "Unknown"
        lines.append(
            f"- **Party: {w.guest_name}** ({w.guests} guests) | Status: `{w.status}` | Requested: {time_str}"
        )

    meta = RAGMetadata(
        organization_id=tenant_id,
        branch_id=branch_id,
        domain="CUSTOMER_EXPERIENCE",
        source_type="waitlist_feedback_sync",
        source_id="waitlist_live_sync",
    ).to_dict()

    res = ingestion_service.ingest_document(
        db=db,
        tenant_id=tenant_id,
        branch_id=branch_id,
        domain="CUSTOMER_EXPERIENCE",
        source_name="Live Waitlist Feedback",
        title="Live Customer Waitlist & Seating Queue Log",
        raw_content="\n".join(lines),
        metadata=meta,
    )
    return 1 if res.get("status") in ("SUCCESS", "UNCHANGED") else 0
