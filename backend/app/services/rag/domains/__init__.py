"""RAG Knowledge Domains Package."""

from app.services.rag.domains.compliance_safety_extractor import seed_compliance_safety_knowledge
from app.services.rag.domains.cross_branch_extractor import (
    seed_cross_branch_knowledge,
    sync_cross_branch_to_rag,
)
from app.services.rag.domains.customer_experience_extractor import (
    seed_customer_experience_knowledge,
    sync_customer_experience_to_rag,
)
from app.services.rag.domains.kitchen_intelligence_extractor import (
    seed_kitchen_intelligence_knowledge,
    sync_kitchen_analytics_to_rag,
)
from app.services.rag.domains.maintenance_extractor import seed_maintenance_knowledge
from app.services.rag.domains.manager_decision_extractor import seed_manager_decisions_knowledge
from app.services.rag.domains.menu_extractor import sync_menu_to_rag
from app.services.rag.domains.operational_extractor import sync_operational_history_to_rag
from app.services.rag.domains.predictive_operations_extractor import (
    seed_predictive_operations_knowledge,
    sync_predictive_operations_to_rag,
)
from app.services.rag.domains.registry import domain_registry, RAGMetadata
from app.services.rag.domains.restaurant_layout_extractor import (
    seed_restaurant_layout_knowledge,
    sync_restaurant_layout_to_rag,
)
from app.services.rag.domains.sop_extractor import seed_default_sops
from app.services.rag.domains.supplier_inventory_extractor import seed_supplier_inventory_knowledge
from app.services.rag.domains.table_lifecycle_extractor import (
    seed_table_lifecycle_knowledge,
    sync_table_lifecycle_to_rag,
)
from app.services.rag.domains.vision_extractor import sync_vision_events_to_rag


def seed_all_enterprise_rag_domains(
    db,
    tenant_id: str,
    branch_id: str | None = None,
) -> dict[str, int]:
    """
    Seeds baseline operational knowledge across all 17 Enterprise RAG domains
    for a given tenant/organization.
    """
    counts: dict[str, int] = {}
    counts["RESTAURANT_SOP"] = seed_default_sops(db, tenant_id, branch_id)
    counts["CUSTOMER_EXPERIENCE"] = seed_customer_experience_knowledge(db, tenant_id, branch_id)
    counts["KITCHEN"] = seed_kitchen_intelligence_knowledge(db, tenant_id, branch_id)
    counts["TABLE_LIFECYCLE"] = seed_table_lifecycle_knowledge(db, tenant_id, branch_id)
    counts["PREDICTIVE_OPERATIONS"] = seed_predictive_operations_knowledge(db, tenant_id, branch_id)
    counts["MANAGER_DECISIONS"] = seed_manager_decisions_knowledge(db, tenant_id, branch_id)
    counts["MAINTENANCE"] = seed_maintenance_knowledge(db, tenant_id, branch_id)
    counts["SUPPLIER_INVENTORY"] = seed_supplier_inventory_knowledge(db, tenant_id, branch_id)
    counts["COMPLIANCE_SAFETY"] = seed_compliance_safety_knowledge(db, tenant_id, branch_id)
    counts["RESTAURANT_LAYOUT"] = seed_restaurant_layout_knowledge(db, tenant_id, branch_id)
    counts["CROSS_BRANCH"] = seed_cross_branch_knowledge(db, tenant_id, branch_id)

    # Sync live DB extractors if active
    counts["OPERATIONAL_HISTORY"] = sync_operational_history_to_rag(db, tenant_id, branch_id)
    counts["VISION"] = sync_vision_events_to_rag(db, tenant_id, branch_id)
    counts["MENU"] = sync_menu_to_rag(db, tenant_id)
    return counts


__all__ = [
    "domain_registry",
    "RAGMetadata",
    "seed_default_sops",
    "sync_menu_to_rag",
    "sync_operational_history_to_rag",
    "sync_vision_events_to_rag",
    "seed_customer_experience_knowledge",
    "sync_customer_experience_to_rag",
    "seed_kitchen_intelligence_knowledge",
    "sync_kitchen_analytics_to_rag",
    "seed_table_lifecycle_knowledge",
    "sync_table_lifecycle_to_rag",
    "seed_predictive_operations_knowledge",
    "sync_predictive_operations_to_rag",
    "seed_manager_decisions_knowledge",
    "seed_maintenance_knowledge",
    "seed_supplier_inventory_knowledge",
    "seed_compliance_safety_knowledge",
    "seed_restaurant_layout_knowledge",
    "sync_restaurant_layout_to_rag",
    "seed_cross_branch_knowledge",
    "sync_cross_branch_to_rag",
    "seed_all_enterprise_rag_domains",
]
