"""
Menu & Culinary Knowledge Extractor for RAG
────────────────────────────────────────────
Converts structured menu items, allergen tags, ingredient notes, and
preparation times into searchable culinary knowledge within the 'MENU' domain.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from sqlalchemy.orm import Session

from app.models.menu_item import MenuItem
from app.services.rag.ingestion.ingestion_service import ingestion_service

logger = logging.getLogger(__name__)


def sync_menu_to_rag(db: Session, tenant_id: str, branch_id: str | None = None) -> int:
    """
    Extracts all active menu items for a tenant and indexes them into the 'MENU' RAG domain.
    Grouped logically by category to provide coherent contextual retrieval.
    """
    items = (
        db.query(MenuItem)
        .filter(
            MenuItem.tenant_id == tenant_id,
            MenuItem.is_active == True,  # noqa: E712
        )
        .all()
    )

    if not items:
        logger.info("No active menu items found for tenant %s to index into RAG.", tenant_id)
        return 0

    # Group by category
    by_category: dict[str, list[MenuItem]] = defaultdict(list)
    for item in items:
        cat = (item.category or "General").strip().title()
        by_category[cat].append(item)

    total_synced = 0

    for category, cat_items in by_category.items():
        doc_title = f"Menu Catalog & Allergen Guide: {category}"
        content_lines = [
            f"# Menu Catalog & Allergen Guide: {category}",
            f"Official culinary reference for all dishes in the '{category}' category.",
            "IMPORTANT: Real-time stock availability and active pricing must be verified via the deterministic database.\n",
        ]

        for it in cat_items:
            veg_label = "Vegetarian" if (it.dietary_type or "").upper() == "VEG" else "Non-Vegetarian"
            prep_str = f"{it.prep_time_minutes} minutes" if getattr(it, "prep_time_minutes", None) else "Standard"
            allergens = getattr(it, "allergens", None) or "None reported"
            desc = (it.description or "No description provided.").strip()

            content_lines.append(f"## {it.name}")
            content_lines.append(f"- Category: {category}")
            content_lines.append(f"- Dietary Classification: {veg_label}")
            content_lines.append(f"- Preparation Time: {prep_str}")
            content_lines.append(f"- Allergen Information: {allergens}")
            content_lines.append(f"- Culinary Description: {desc}")
            content_lines.append("")

        full_text = "\n".join(content_lines)
        res = ingestion_service.ingest_document(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            domain="MENU",
            source_name="FOH Menu Management System",
            title=doc_title,
            raw_content=full_text,
            metadata={
                "domain": "MENU",
                "category": category,
                "item_count": len(cat_items),
            },
        )
        if res.get("status") in ("SUCCESS", "UNCHANGED"):
            total_synced += len(cat_items)

    logger.info("Indexed %d menu items across %d categories for tenant %s.", total_synced, len(by_category), tenant_id)
    return total_synced
