"""
Restaurant Standard Operating Procedures (SOP) Knowledge Ingestion
────────────────────────────────────────────────────────────────────
Seeds and manages core restaurant operating procedures, policies, and
training guidelines within the 'RESTAURANT_SOP' knowledge domain.
"""

from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.services.rag.ingestion.ingestion_service import ingestion_service

logger = logging.getLogger(__name__)

DEFAULT_SOPS: list[dict[str, str]] = [
    {
        "title": "Table Turnover & Cleaning Standard Operating Procedure (SOP-01)",
        "source": "Restaurant Operations Manual",
        "content": """# Table Turnover & Cleaning Standard Operating Procedure (SOP-01)

## 1. Objective & Target Performance
The primary operational target for table turnover turnaround is 3 to 5 minutes between guest departure and table ready status. Ensuring rapid, sanitized turnovers maintains dining room momentum and minimizes guest wait times.

## 2. Step-by-Step Turnover Protocol
1. Departure Recognition: When guests stand to depart or settle their bill, the busser or assigned server must be notified immediately.
2. Table Clearance: Remove all glassware, plates, cutlery, napkins, and condiment caddies within 90 seconds.
3. Sanitization & Surface Prep: Wipe the entire tabletop with designated food-safe sanitizer. Allow 30 seconds wet contact time before drying with a clean microfiber cloth.
4. Floor Inspection: Check beneath the table for dropped food or napkins; sweep promptly if necessary.
5. Table Reset: Place new sanitized cutlery, rolled napkins, and fresh water carafes according to the current meal service layout.
6. Status Confirmation: Mark the table status as AVAILABLE in the FOH terminal or verify that the CCTV camera detects the cleared state.

## 3. Delays & Escalation
- If a table remains in 'CLEANING' status for longer than 8 minutes, the FOH system triggers an amber caution alert.
- At 12 minutes, an alert is escalated to the Shift Manager. The host must not seat incoming guests at an un-reset table.
- When turning VIP or high-capacity banquet tables (6+ seats), assign two staff members simultaneously.
""",
    },
    {
        "title": "Host Stand, Seating Allocation & Full Capacity Protocol (SOP-02)",
        "source": "Front-of-House Host Training Manual",
        "content": """# Host Stand, Seating Allocation & Full Capacity Protocol (SOP-02)

## 1. Operating Rules When All Tables Are Occupied
When dining room occupancy reaches 100%:
1. Greet guests warmly within 15 seconds of entry.
2. Politely explain that all tables are currently occupied and in active service.
3. Offer immediate placement on the digital Waitlist. Record guest name, party size, phone number, and any special seating preferences (high-chair, booth, outdoor).
4. Calculate and quote estimated wait time using the FOH Wait Time service (baseline: average remaining session duration for parties of comparable size).
5. Guide waiting guests to the lounge or designated waiting area. Inform them that an SMS notification will be sent when their table is being prepared.

## 2. Table Allocation & Seating Efficiency Rules
- Never seat a 2-person party at a 6-seat table during peak rush unless explicitly authorized by the Shift Manager.
- Balance server section loads by rotating seating evenly among open stations.
- For parties with accessibility needs, prioritize ground-level tables nearest the main entrance.
""",
    },
    {
        "title": "Reservation Grace Period & No-Show Policy (SOP-03)",
        "source": "Guest Relations Guidelines",
        "content": """# Reservation Grace Period & No-Show Policy (SOP-03)

## 1. Hold Time & Grace Window
- Tables reserved for incoming guests are held for exactly 15 minutes past the scheduled booking time.
- The table status remains RESERVED and cannot be allocated to walk-in guests during this window.

## 2. Procedure for Late Arrivals
1. At 10 minutes past reservation time: Host initiates a courtesy phone call or SMS check-in to confirm the party's arrival ETA.
2. At 15 minutes past reservation time with no response: The reservation is flagged as NO_SHOW.
3. The host clicks 'Release Reservation' in the FOH reservation stand, immediately transitioning the table to AVAILABLE for waitlisted walk-in guests.
4. If the late party arrives after release: Offer the next available table or priority placement at the top of the walk-in waitlist.
""",
    },
    {
        "title": "Kitchen Delay & Order Escalation Procedure (SOP-04)",
        "source": "Kitchen Expediter Operations",
        "content": """# Kitchen Delay & Order Escalation Procedure (SOP-04)

## 1. Standard Preparation Targets
- Starters & Beverages: 5 to 8 minutes from order transmission.
- Main Courses: 12 to 18 minutes from order transmission.
- Desserts: 5 to 7 minutes.

## 2. Delay Thresholds & Escalation
- Amber Threshold (15 minutes): KDS highlights order in yellow; expediter checks station station status (Grill, Saute, Fry).
- Red Threshold (20 minutes): KDS triggers audible chime and red border. Expediter escalates directly to Head Chef.
- Floor Notification: Server is notified via mobile terminal to visit the guest table, offer beverage refills or complimentary bread, and apologize for the brief delay.
- Manager Action: If an entire section experiences kitchen delays due to volume spikes, the Shift Manager may temporarily pause online ordering or throttle walk-in seating.
""",
    },
    {
        "title": "Emergency Walkout & Loss Prevention Protocol (SOP-05)",
        "source": "Loss Prevention Standard",
        "content": """# Emergency Walkout & Loss Prevention Protocol (SOP-05)

## 1. Identification of Unpaid Departure
An unpaid walkout is suspected when guests vacate a table while their bill remains in 'PENDING' or 'UNPAID' status.
The CCTV vision system triggers an 'UNPAID_WALKOUT_SUSPECT' anomaly when zero persons are detected at a table with an active unsettled bill for more than 45 seconds.

## 2. Staff Action Protocol
1. Verify Table State: Server or host immediately inspects the table to confirm whether guests have fully departed or merely stepped outside briefly.
2. Safety First: Staff members must NEVER physically confront, chase, or touch a departing patron outside the restaurant premises.
3. Manager Notification: Notify the Shift Manager immediately.
4. Incident Logging: Record the incident in the FOH Loss Prevention log, noting table number, unsettled amount, guest name (if reservation), and CCTV timestamp.
""",
    },
]


def seed_default_sops(db: Session, tenant_id: str, branch_id: str | None = None) -> int:
    """Idempotently seed the standard FOH SOP documents for a tenant."""
    count = 0
    for sop in DEFAULT_SOPS:
        res = ingestion_service.ingest_document(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            domain="RESTAURANT_SOP",
            source_name=sop["source"],
            title=sop["title"],
            raw_content=sop["content"],
            metadata={"domain": "RESTAURANT_SOP", "category": "operational_procedure"},
        )
        if res.get("status") in ("SUCCESS", "UNCHANGED"):
            count += 1
    logger.info("Seeded %d standard SOPs for tenant %s.", count, tenant_id)
    return count
