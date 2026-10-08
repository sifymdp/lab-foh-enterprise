"""
Supplier & Inventory Contextual RAG Knowledge Extractor
────────────────────────────────────────────────────────
Indexes contextual knowledge regarding suppliers, vendor delivery cadences,
ingredient specifications, procurement policies, and stockout mitigation strategies.

CRITICAL OPERATIONAL CONSTRAINT:
Live numerical inventory quantities and dish prices are derived from structured DB tables.
This RAG domain provides contextual vendor relationships and operational procedures.
"""

from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.services.rag.domains.registry import RAGMetadata
from app.services.rag.ingestion.ingestion_service import ingestion_service

logger = logging.getLogger(__name__)

DEFAULT_SUPPLIER_INVENTORY_RECORDS = [
    {
        "title": "Fresh Seafood & Shellfish Supplier Directory & Delivery Schedule",
        "source": "Procurement & Vendor Directory",
        "supplier_id": "SUPP-OCEAN-01",
        "content": """# Supplier Profile: Ocean Fresh Seafood Distributors

## 1. Vendor Details & Primary Ingredients Provided
- **Vendor Name**: Ocean Fresh Seafood Ltd.
- **Key Ingredients Supplied**: Wild Atlantic Salmon, Chilean Sea Bass, Tiger Prawns, Diver Scallops.
- **Delivery Windows**: Tuesday and Friday mornings (07:00 - 09:00).
- **Quality Standard**: Cold chain temperature log mandatory upon delivery (must verify core temperature ≤ 3°C).

## 2. Historical Stock Issues & Seasonal Substitution Rules
- **Winter Weather Delays**: Winter storms in coastal regions frequently delay Friday deliveries by 2 to 4 hours.
- **Chilean Sea Bass Shortage Protocol**: If fresh sea bass is unavailable from Ocean Fresh, the Head Chef approves substitution with Wild Halibut with updated server line-up notes.
- **Quality Non-Conformance Log**: In August, one batch of oysters was rejected due to ice pack failure in transit; vendor credited the delivery immediately.
""",
    },
    {
        "title": "Prime Meat, Poultry & Specialty Produce Suppliers",
        "source": "Procurement & Vendor Directory",
        "supplier_id": "SUPP-VALLEY-02",
        "content": """# Supplier Profile: Valley Prime Meats & Organic Farms

## 1. Vendor Details & Key Ingredients
- **Vendor Name**: Valley Prime Purveyors.
- **Key Ingredients Supplied**: USDA Prime Ribeye, Beef Tenderloin, Free-Range Chicken Breasts, Artisanal Pancetta.
- **Delivery Windows**: Monday, Wednesday, and Saturday mornings (06:30 - 08:30).

## 2. Out-of-Stock Escalation & 86 Item Policy
- **Minimum Stock Buffer**: Kitchen must maintain a 48-hour buffer on prime cuts.
- **Immediate 86 Trigger**: When prime steak counts reach 3 portions, the expediter must notify the Shift Manager to prepare servers for verbal '86' updates or alternative recommendations.
""",
    },
    {
        "title": "Emergency Procurement & Local Market Purchase Policy",
        "source": "Culinary Management Manual",
        "supplier_id": "PROC-POLICY-01",
        "content": """# Emergency Ingredient Procurement & Stockout Procedure

## 1. When a Core Ingredient Runs Out During Service
1. **Assessment**: Sous Chef confirms that no backup stock is stored in walk-in coolers or dry storage.
2. **Authorized Emergency Sourcing**:
   - For fresh herbs, citrus, or dairy: Shift Manager may dispatch an expeditor or runner to the local organic market (Metropolitan Market, 2 blocks away).
   - Core proteins or alcohol: Must NOT be sourced from unauthorized retail; dish must be set to unavailable (86'd) in POS and FOH management.
3. **Immediate Menu System Update**:
   - Use the FOH 86 item tool (`_handle_86_menu_item`) to immediately mark the item unavailable across digital ordering and waitstaff handhelds.
""",
    },
]


def seed_supplier_inventory_knowledge(
    db: Session,
    tenant_id: str,
    branch_id: str | None = None,
) -> int:
    """Seeds baseline supplier profiles and procurement policies."""
    count = 0
    for record in DEFAULT_SUPPLIER_INVENTORY_RECORDS:
        meta = RAGMetadata(
            organization_id=tenant_id,
            branch_id=branch_id,
            domain="SUPPLIER_INVENTORY",
            source_type="supplier_profile",
            source_id=record.get("supplier_id", f"supp_{count + 1}"),
            supplier_id=record.get("supplier_id"),
        ).to_dict()

        res = ingestion_service.ingest_document(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            domain="SUPPLIER_INVENTORY",
            source_name=record["source"],
            title=record["title"],
            raw_content=record["content"],
            metadata=meta,
        )
        if res.get("status") in ("SUCCESS", "UNCHANGED"):
            count += 1
    logger.info("Seeded %d supplier and inventory records for tenant %s.", count, tenant_id)
    return count
