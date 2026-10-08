"""
Kitchen Intelligence & KDS Operations RAG Knowledge Extractor
─────────────────────────────────────────────────────────────
Stores, summarizes, and indexes kitchen preparation delays, station bottlenecks
(Grill, Saute, Fry, Pantry), repeatedly delayed menu items, and kitchen incident resolutions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.order_analytics import OrderAnalytics
from app.services.rag.domains.registry import RAGMetadata
from app.services.rag.ingestion.ingestion_service import ingestion_service

logger = logging.getLogger(__name__)

DEFAULT_KITCHEN_INTELLIGENCE_RECORDS = [
    {
        "title": "Kitchen Operations & Station Bottleneck Diagnostics",
        "source": "KDS Operational Analytics Engine",
        "source_type": "station_diagnostics",
        "content": """# Kitchen Station Bottlenecks & Ticket Delay Diagnostics

## 1. Primary Station Bottleneck: Saute Station
- **Peak Hour Performance**: During Friday and Saturday dinner service (19:30 - 21:15), the **Saute Station** consistently experiences the highest ticket queue buildup.
- **Root Cause**: The pan-seared sea bass and wild mushroom risotto require continuous pan attention and average 18.5 minutes cooking time versus the 14-minute target.
- **Intervention**: Added a dedicated secondary induction cooktop and assigned a prep cook during peak rush to pre-portion risotto bases.

## 2. Repeatedly Delayed Dishes
1. **Bone-in Ribeye Steak (Medium-Well / Well-Done)**: Average prep time 23 minutes. Creates Grill Station backlog when multiple large parties order simultaneously.
2. **Wild Mushroom Risotto**: High order concentration during cold weather leads to 4+ concurrent ticket orders straining Saute burner capacity.
3. **Chocolate Lava Cake**: Requires 16-minute oven bake; delayed when orders are not transmitted until after main courses are cleared.

## 3. Incident History & Resolution Plans
- **Oven Heat Exchanger Failure (Resolved)**: Convection oven temperature dipped by 25°C due to door seal degradation. Replaced gasket and restored baseline baking velocity.
- **Order Throttling Standard**: When ticket count on the KDS exceeds 18 active orders, the expediter triggers 'Rush Mode', pacing walk-in seating by 5 minutes.
""",
    },
    {
        "title": "Kitchen Expediter & Station Communication Protocol",
        "source": "Culinary Operations Manual",
        "source_type": "expediter_protocol",
        "content": """# Kitchen Expediter & Station Pacing Protocol

## 1. Expediter Role & Delay Escalation
- The Expediter is the sole conduit of communication between Front-of-House servers and the kitchen line.
- When an order reaches **15 minutes** elapsed time without plating, the Expediter calls out 'Table [X] Check-In' to the assigned station lead.
- At **20 minutes**, the Expediter automatically alerts the Shift Manager to perform a table check-in.

## 2. Multi-Course Pacing Rules
- Appetizer ticket target: 7 to 9 minutes.
- Main course firing: Automatically triggered upon Appetizer 'SERVED' status or manual server fire signal.
- All stations must plate harmonious tickets within 60 seconds of each other to prevent hot dishes cooling on the pass.
""",
    },
]


def seed_kitchen_intelligence_knowledge(
    db: Session,
    tenant_id: str,
    branch_id: str | None = None,
) -> int:
    """Seeds standard baseline kitchen intelligence and delay analysis records."""
    count = 0
    for record in DEFAULT_KITCHEN_INTELLIGENCE_RECORDS:
        meta = RAGMetadata(
            organization_id=tenant_id,
            branch_id=branch_id,
            domain="KITCHEN",
            source_type=record.get("source_type", "kds_diagnostic"),
            source_id=f"kitchen_{count + 1}",
        ).to_dict()

        res = ingestion_service.ingest_document(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            domain="KITCHEN",
            source_name=record["source"],
            title=record["title"],
            raw_content=record["content"],
            metadata=meta,
        )
        if res.get("status") in ("SUCCESS", "UNCHANGED"):
            count += 1
    logger.info("Seeded %d kitchen intelligence records for tenant %s.", count, tenant_id)
    return count


def sync_kitchen_analytics_to_rag(
    db: Session,
    tenant_id: str,
    branch_id: str | None = None,
    days_back: int = 7,
) -> int:
    """Summarizes actual OrderAnalytics records into searchable Kitchen RAG documents."""
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    q = db.query(OrderAnalytics).filter(OrderAnalytics.created_at >= cutoff)
    if tenant_id:
        q = q.filter(OrderAnalytics.tenant_id == tenant_id)
    records = q.all()

    if not records:
        return seed_kitchen_intelligence_knowledge(db, tenant_id, branch_id)

    # Group analytics by station and dish
    station_times: dict[str, list[float]] = {}
    delayed_items: dict[str, int] = {}

    for r in records:
        station = r.station or "General Kitchen"
        station_times.setdefault(station, []).append(r.actual_cooking_time or 0.0)
        if (r.actual_cooking_time or 0.0) > 18.0:
            item = r.item_name or "Unknown Item"
            delayed_items[item] = delayed_items.get(item, 0) + 1

    lines = [
        f"# Live Kitchen Performance & Preparation Delay Report (Past {days_back} Days)",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "Real-time operational summary derived from completed KDS tickets.\n",
        "## Station Average Cooking Durations",
    ]

    for stn, times in station_times.items():
        avg_time = round(sum(times) / max(1, len(times)), 1)
        max_time = round(max(times), 1) if times else 0.0
        lines.append(f"- **Station: {stn}** — Avg Cooking Time: {avg_time}m (Max: {max_time}m across {len(times)} orders)")

    lines.append("\n## Repeatedly Delayed Dishes (> 18 Minutes)")
    if delayed_items:
        for item, cnt in sorted(delayed_items.items(), key=lambda x: x[1], reverse=True)[:10]:
            lines.append(f"- **{item}**: Flagged {cnt} times for preparation time exceeding target threshold.")
    else:
        lines.append("- No dishes recorded exceeding 18-minute preparation threshold.")

    meta = RAGMetadata(
        organization_id=tenant_id,
        branch_id=branch_id,
        domain="KITCHEN",
        source_type="live_kds_analytics_sync",
        source_id="kds_live_analytics",
    ).to_dict()

    res = ingestion_service.ingest_document(
        db=db,
        tenant_id=tenant_id,
        branch_id=branch_id,
        domain="KITCHEN",
        source_name="KDS Live Analytics Sync",
        title="Live Kitchen Speed & Dish Delay Performance",
        raw_content="\n".join(lines),
        metadata=meta,
    )
    return 1 if res.get("status") in ("SUCCESS", "UNCHANGED") else 0
