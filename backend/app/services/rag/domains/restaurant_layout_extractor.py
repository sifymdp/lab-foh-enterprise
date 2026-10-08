"""
Restaurant Floor Plan & Layout RAG Knowledge Extractor
───────────────────────────────────────────────────────
Indexes floor-plan versions, table repositioning records, rotation adjustments,
canvas coordinate changes, camera ROI bounding boxes, and layout modifications.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.floor import Floor
from app.models.table import Table
from app.models.vision import Camera
from app.services.rag.domains.registry import RAGMetadata
from app.services.rag.ingestion.ingestion_service import ingestion_service

logger = logging.getLogger(__name__)

DEFAULT_LAYOUT_RECORDS = [
    {
        "title": "Main Dining Room Floor Plan Version 2.4 & Table Repositioning History",
        "source": "Floor Plan Architectural History",
        "content": """# Floor Plan Architecture & Table Position History: Main Floor

## 1. Recent Table Relocations & Geometric Changes
- **Table T18 Repositioning**:
  - **Change**: Table T18 was moved 80 pixels eastward (from X: 640 to X: 720, Y: 310) to create a clear 1.2-meter egress pathway toward the emergency patio exit.
  - **Reason**: Recommended during local fire marshal safety walk-through to prevent bottlenecking near server service stations.
  - **Camera ROI Update**: Overhead Camera 2 ROI bounding box was recalibrated to pixel coordinates `[710, 300, 110, 95]`.

- **Table T12 Rotation Adjustment**:
  - **Change**: Rotated 90 degrees to align booth backrests against the perimeter window frame.
  - **Reason**: Reduced walkway congestion between Section B and Section C; eliminated server bumping into seated guests.

- **Table T14 & T15 Combinability**:
  - Configured with identical heights and modular caster locks to allow rapid combining into an 8-top party layout within 60 seconds.

## 2. CCTV Camera Coverage & ROI Alignment
- **Camera 1 (Main Hallway & Center Deuces)**: Covers Tables T1 through T8.
- **Camera 2 (Window Booths & Patio Doorway)**: Covers Tables T9 through T15.
- Calibration standard: When tables are moved on the interactive digital floor canvas, camera ROI coordinates must be refreshed in `/camera-setup` to maintain accurate YOLO occupancy inference.
""",
    },
]


def seed_restaurant_layout_knowledge(
    db: Session,
    tenant_id: str,
    branch_id: str | None = None,
) -> int:
    """Seeds baseline floor plan layout history records."""
    count = 0
    for record in DEFAULT_LAYOUT_RECORDS:
        meta = RAGMetadata(
            organization_id=tenant_id,
            branch_id=branch_id,
            domain="RESTAURANT_LAYOUT",
            source_type="layout_history",
            source_id=f"layout_{count + 1}",
        ).to_dict()

        res = ingestion_service.ingest_document(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            domain="RESTAURANT_LAYOUT",
            source_name=record["source"],
            title=record["title"],
            raw_content=record["content"],
            metadata=meta,
        )
        if res.get("status") in ("SUCCESS", "UNCHANGED"):
            count += 1
    logger.info("Seeded %d layout history records for tenant %s.", count, tenant_id)
    return count


def sync_restaurant_layout_to_rag(
    db: Session,
    tenant_id: str,
    branch_id: str | None = None,
) -> int:
    """Extracts live floor plans, table coordinates, and camera ROIs into layout RAG records."""
    floors = db.query(Floor).filter(Floor.tenant_id == tenant_id).all()
    if not floors:
        return seed_restaurant_layout_knowledge(db, tenant_id, branch_id)

    lines = [
        "# Live Floor Plan Geometry & Table Configuration Record",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "Current spatial positioning of dining tables and floor dimensions.\n",
    ]

    for fl in floors:
        lines.append(f"## Floor: {fl.name} (Dimensions: {fl.width}px x {fl.height}px)")
        tables = db.query(Table).filter(Table.floor_id == fl.id).order_by(Table.number.asc()).all()
        for t in tables:
            lines.append(
                f"- **Table T{t.number}**: Type: `{t.type}`, Seats: {t.capacity}, "
                f"Position: (X: {t.x}, Y: {t.y}, Rot: {t.rotation}°), ROI: `{t.roi_coords or 'Default'}`"
            )

    meta = RAGMetadata(
        organization_id=tenant_id,
        branch_id=branch_id,
        domain="RESTAURANT_LAYOUT",
        source_type="live_floor_sync",
        source_id="live_floor_plan",
    ).to_dict()

    res = ingestion_service.ingest_document(
        db=db,
        tenant_id=tenant_id,
        branch_id=branch_id,
        domain="RESTAURANT_LAYOUT",
        source_name="FOH Floor Plan Service",
        title="Live Floor Plan & Table Coordinates Record",
        raw_content="\n".join(lines),
        metadata=meta,
    )
    return 1 if res.get("status") in ("SUCCESS", "UNCHANGED") else 0
