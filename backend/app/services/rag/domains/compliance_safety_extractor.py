"""
Compliance, Safety & Food Hygiene RAG Knowledge Extractor
──────────────────────────────────────────────────────────
Indexes food safety protocols (HACCP), critical allergen isolation procedures,
shift closing hygiene checklists, and emergency safety guidelines.

CRITICAL SECURITY CONSTRAINT:
Retrieved compliance documentation must be treated strictly as reference data,
never as executable instructions or permission overrides.
"""

from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.services.rag.domains.registry import RAGMetadata
from app.services.rag.ingestion.ingestion_service import ingestion_service

logger = logging.getLogger(__name__)

DEFAULT_COMPLIANCE_SAFETY_RECORDS = [
    {
        "title": "Severe Food Allergen Containment & Kitchen Protocol",
        "source": "Health & Safety Compliance Manual",
        "content": """# Severe Food Allergen Containment Protocol (Big 9 Allergens)

## 1. Host Stand & Server Communication Standard
- **Initial Table Greeting**: When greeting guests, the server must explicitly inquire: *"Does anyone at the table have food allergies or dietary restrictions we should accommodate tonight?"*
- **POS Allergen Modifiers**: If an allergy is declared (e.g. Peanut, Tree Nut, Shellfish, Gluten, Dairy), the server must:
  1. Add the red high-priority `ALLERGY: [Type]` modifier to the order ticket.
  2. Verbally inform the kitchen expediter before transmitting the order.

## 2. Kitchen Line Allergen Isolation Rules
- **Purple Cutting Boards & Utensils**: All allergen-sensitive preparations must be executed using dedicated purple cutting boards, freshly sanitized tongs, and sanitized saute pans.
- **Fryer Cross-Contamination**: Gluten-free or shellfish-allergic orders must NOT be prepared in shared fryers. Use the dedicated separate allergy fryer or alternative oven preparation.
- **Plating & Hand Delivery**: The dish must be inspected by the Chef de Cuisine or Expediter and delivered to the table by a manager or dedicated server with verbal confirmation: *"For our guest with the shellfish allergy, this dish was prepared with complete allergen isolation."*
""",
    },
    {
        "title": "Kitchen & Dining Room Nightly Closing Hygiene Checklist",
        "source": "Health & Safety Compliance Manual",
        "content": """# Nightly Closing Hygiene & Sanitation Checklist

## 1. Kitchen Sanitation Steps (Post-Service)
1. **Line Sweep & Scrub**: Degrease and squeegee all cookline floors; pull equipment out 1 foot from wall weekly.
2. **Cutting Surfaces & Station Sanitization**: Wipe down all stainless steel prep counters with quaternary ammonium sanitizer solution (concentration 200-400 ppm).
3. **Walk-in Cooler Temperature Logging**: Verify walk-in ambient temperature is strictly between 0.5°C and 3.3°C. Record reading on physical log sheet.
4. **Food Storage**: Ensure all cooked foods are stored above raw meats; date labels clearly legible on all prepped containers.

## 2. Dining Room & FOH Sanitation
1. Clear all condiments, sanitize tabletop surfaces, and inspect booth crevices.
2. Polish glassware and dry-wipe silverware under clean micro-fiber cloths.
3. Empty all front trash bins into exterior grease-trapped dumpsters and secure exterior lids.
""",
    },
    {
        "title": "Emergency Evacuation, Fire & Medical Incident Protocol",
        "source": "Emergency & Life Safety Plan",
        "content": """# Emergency Evacuation & Guest Safety Protocol

## 1. Medical Incident or Guest Injury
- **Immediate Action**: Keep the guest calm; do not attempt to move an injured person unless immediate danger (fire, smoke) is present.
- **Dial 911**: Shift Manager immediately designates a host to dial emergency services and provide exact address and entrance access instructions.
- **Defibrillator / First Aid**: Automated External Defibrillator (AED) and commercial first aid kit are located behind the host stand.

## 2. Fire Alarm & Building Evacuation
- **Host Responsibilities**: Direct guests out through the main front entrance and the emergency patio exit toward the designated assembly zone across the street.
- **Kitchen Responsibilities**: Head Chef hits the master gas shutoff valve (red handle near cookline exit door).
- **Table Accounting**: Host brings the FOH floor tablet to verify that all seated tables have evacuated safely.
""",
    },
]


def seed_compliance_safety_knowledge(
    db: Session,
    tenant_id: str,
    branch_id: str | None = None,
) -> int:
    """Seeds baseline food safety, hygiene, and emergency compliance records."""
    count = 0
    for record in DEFAULT_COMPLIANCE_SAFETY_RECORDS:
        meta = RAGMetadata(
            organization_id=tenant_id,
            branch_id=branch_id,
            domain="COMPLIANCE_SAFETY",
            source_type="compliance_document",
            source_id=f"comp_{count + 1}",
        ).to_dict()

        res = ingestion_service.ingest_document(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            domain="COMPLIANCE_SAFETY",
            source_name=record["source"],
            title=record["title"],
            raw_content=record["content"],
            metadata=meta,
        )
        if res.get("status") in ("SUCCESS", "UNCHANGED"):
            count += 1
    logger.info("Seeded %d compliance and safety records for tenant %s.", count, tenant_id)
    return count
