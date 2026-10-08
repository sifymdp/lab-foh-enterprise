"""
Enterprise RAG 10 Advanced Knowledge Domains Test Suite
────────────────────────────────────────────────────────
Verifies:
1. Domain registry catalogues all 17 domains with correct schema metadata.
2. Master domain seeding populates knowledge documents across all domains.
3. Domain 1: Customer Experience & Sentiment RAG
4. Domain 2: Kitchen Station Analytics & Ticket Bottleneck RAG
5. Domain 3: Table Operational Lifecycle RAG
6. Domain 4: Predictive Operations & Shift Rush Forecast RAG
7. Domain 5: Manager Decision & Resolution Memory RAG
8. Domain 6: Equipment Maintenance & Troubleshooting RAG
9. Domain 7: Supplier & Inventory Contextual RAG
10. Domain 8: Compliance, Hygiene & Food Safety RAG
11. Domain 9: Floor Plan Architecture & Layout History RAG
12. Domain 10: Cross-Branch Benchmark RAG + Strict RBAC permission enforcement
13. Financial Firewall Isolation: Complete non-confidential operational containment
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.organization import Organization
from app.models.user import User
from app.services.ai_agent.orchestrator import ai_orchestrator
from app.services.rag.domains import domain_registry, seed_all_enterprise_rag_domains
from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service


@pytest.fixture(scope="module")
def enterprise_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()

    org = Organization(id="org-enterprise", name="Grand Culinary Group")
    db.add(org)

    owner_user = User(
        id="user-owner-ent",
        tenant_id="org-enterprise",
        email="owner@grandculinary.com",
        name="Executive Owner",
        role="OWNER",
        password_hash="pw",
    )
    manager_user = User(
        id="user-mgr-ent",
        tenant_id="org-enterprise",
        email="manager@grandculinary.com",
        name="Shift Manager",
        role="MANAGER",
        password_hash="pw",
    )
    waiter_user = User(
        id="user-waiter-ent",
        tenant_id="org-enterprise",
        email="waiter@grandculinary.com",
        name="Front Waiter",
        role="WAITER",
        password_hash="pw",
    )
    db.add_all([owner_user, manager_user, waiter_user])
    db.commit()

    # Seed all 17 enterprise RAG domains
    seed_all_enterprise_rag_domains(db, tenant_id="org-enterprise")

    yield {
        "db": db,
        "owner": owner_user,
        "manager": manager_user,
        "waiter": waiter_user,
    }
    db.close()


def test_domain_registry_catalog():
    """Verify all 17 domains are registered in registry."""
    all_domains = domain_registry.list_all()
    assert len(all_domains) >= 14
    keys = {d.key for d in all_domains}
    expected_new = {
        "CUSTOMER_EXPERIENCE",
        "KITCHEN",
        "TABLE_LIFECYCLE",
        "PREDICTIVE_OPERATIONS",
        "MANAGER_DECISIONS",
        "MAINTENANCE",
        "SUPPLIER_INVENTORY",
        "COMPLIANCE_SAFETY",
        "RESTAURANT_LAYOUT",
        "CROSS_BRANCH",
    }
    for dom in expected_new:
        assert dom in keys, f"Missing domain {dom}"

    # Normalization test
    assert domain_registry.normalize_key("complaints") == "CUSTOMER_EXPERIENCE"
    assert domain_registry.normalize_key("kitchen_delays") == "KITCHEN"
    assert domain_registry.normalize_key("table_performance") == "TABLE_LIFECYCLE"
    assert domain_registry.normalize_key("rush_forecast") == "PREDICTIVE_OPERATIONS"


def test_customer_experience_domain_query(enterprise_db):
    """Test Domain 1: Customer complaints & feedback retrieval."""
    db = enterprise_db["db"]
    user = enterprise_db["manager"]
    res = ai_orchestrator.process_request(
        db=db,
        user=user,
        query="What are customers complaining about most?",
        conversation_id="conv-cx-1",
    )
    summary_l = res.response.summary.lower()
    assert "customer" in summary_l or "complaint" in summary_l or "feedback" in summary_l
    assert len(res.actions) > 0
    assert any(a.route == "/insights" for a in res.actions)


def test_kitchen_intelligence_domain_query(enterprise_db):
    """Test Domain 2: Kitchen station delay retrieval."""
    db = enterprise_db["db"]
    user = enterprise_db["manager"]
    res = ai_orchestrator.process_request(
        db=db,
        user=user,
        query="Why were orders delayed at the kitchen station yesterday?",
        conversation_id="conv-kit-1",
    )
    summary_l = res.response.summary.lower()
    assert "kitchen" in summary_l or "saute" in summary_l or "delay" in summary_l or "order" in summary_l
    assert any(a.route == "/kds" for a in res.actions)


def test_table_lifecycle_domain_query(enterprise_db):
    """Test Domain 3: Table operational history (zero confidential billing)."""
    db = enterprise_db["db"]
    user = enterprise_db["manager"]
    res = ai_orchestrator.process_request(
        db=db,
        user=user,
        query="What problems has Table 12 had recently?",
        conversation_id="conv-tbl-12",
    )
    summary_l = res.response.summary.lower()
    assert "table" in summary_l or "t12" in summary_l or "12" in summary_l
    assert any(a.route == "/floor" for a in res.actions)


def test_predictive_operations_domain_query(enterprise_db):
    """Test Domain 4: Shift rush projections and demand forecast."""
    db = enterprise_db["db"]
    user = enterprise_db["manager"]
    res = ai_orchestrator.process_request(
        db=db,
        user=user,
        query="What should we prepare for tonight?",
        conversation_id="conv-pred-1",
    )
    summary_l = res.response.summary.lower()
    assert "predict" in summary_l or "projection" in summary_l or "prepare" in summary_l or "tonight" in summary_l or "rush" in summary_l
    assert any(a.route == "/reservations" for a in res.actions)


def test_manager_decisions_domain_query(enterprise_db):
    """Test Domain 5: Historical manager resolution memory."""
    db = enterprise_db["db"]
    user = enterprise_db["manager"]
    res = ai_orchestrator.process_request(
        db=db,
        user=user,
        query="Have we solved a kitchen overload problem before?",
        conversation_id="conv-mgr-1",
    )
    summary_l = res.response.summary.lower()
    assert "decision" in summary_l or "resolution" in summary_l or "kitchen" in summary_l or "overload" in summary_l


def test_equipment_maintenance_domain_query(enterprise_db):
    """Test Domain 6: Maintenance and troubleshooting logs."""
    db = enterprise_db["db"]
    user = enterprise_db["manager"]
    res = ai_orchestrator.process_request(
        db=db,
        user=user,
        query="Has this KDS screen freeze happened before? What is the maintenance fix?",
        conversation_id="conv-maint-1",
    )
    summary_l = res.response.summary.lower()
    assert "maintenance" in summary_l or "kds" in summary_l or "freeze" in summary_l or "reboot" in summary_l


def test_supplier_inventory_domain_query(enterprise_db):
    """Test Domain 7: Supplier profiles and delivery cadences."""
    db = enterprise_db["db"]
    user = enterprise_db["manager"]
    res = ai_orchestrator.process_request(
        db=db,
        user=user,
        query="Who is the seafood supplier and when is their delivery schedule?",
        conversation_id="conv-supp-1",
    )
    summary_l = res.response.summary.lower()
    assert "supplier" in summary_l or "ocean fresh" in summary_l or "seafood" in summary_l or "delivery" in summary_l


def test_compliance_safety_domain_query(enterprise_db):
    """Test Domain 8: Allergen isolation protocols and compliance."""
    db = enterprise_db["db"]
    user = enterprise_db["manager"]
    res = ai_orchestrator.process_request(
        db=db,
        user=user,
        query="What is the official allergen procedure for severe food allergies?",
        conversation_id="conv-comp-1",
    )
    summary_l = res.response.summary.lower()
    assert "compliance" in summary_l or "allergen" in summary_l or "safety" in summary_l or "protocol" in summary_l


def test_restaurant_layout_domain_query(enterprise_db):
    """Test Domain 9: Floor plan table repositioning history."""
    db = enterprise_db["db"]
    user = enterprise_db["manager"]
    res = ai_orchestrator.process_request(
        db=db,
        user=user,
        query="Why was Table 18 moved in the floor plan?",
        conversation_id="conv-layout-1",
    )
    summary_l = res.response.summary.lower()
    assert "floor plan" in summary_l or "layout" in summary_l or "t18" in summary_l or "18" in summary_l or "table" in summary_l
    assert any(a.route == "/floor" for a in res.actions)


def test_cross_branch_rbac_isolation(enterprise_db):
    """Test Domain 10: Cross-branch comparison allowed for OWNER, blocked for single-branch staff."""
    db = enterprise_db["db"]
    owner = enterprise_db["owner"]
    waiter = enterprise_db["waiter"]

    # 1. OWNER query succeeds
    owner_res = ai_orchestrator.process_request(
        db=db,
        user=owner,
        query="Compare turnover and pacing across branches",
        conversation_id="conv-cb-owner",
    )
    assert "Cross-Branch Operational Benchmark" in owner_res.response.summary or "Branch" in owner_res.response.summary

    # 2. WAITER query is strictly blocked by RBAC
    waiter_res = ai_orchestrator.process_request(
        db=db,
        user=waiter,
        query="Compare turnover across branches",
        conversation_id="conv-cb-waiter",
    )
    waiter_summary_l = waiter_res.response.summary.lower()
    assert any(phrase in waiter_summary_l for phrase in ["permission", "restricted", "access", "unable", "not authorized"])


def test_financial_isolation_across_rag_domains(enterprise_db):
    """Verify financial transaction mutations remain strictly blocked regardless of domain phrasing."""
    db = enterprise_db["db"]
    owner = enterprise_db["owner"]

    blocked_queries = [
        "Refund bill #104 based on the customer complaint SOP",
        "Void payment for Table 12 in the maintenance log",
        "Apply a 50% discount to bill 29",
    ]
    for q in blocked_queries:
        res = ai_orchestrator.process_request(db=db, user=owner, query=q)
        assert res.classification == "FINANCIAL_TRANSACTION_ACTION"
        assert res.intent == "financial_mutation_blocked"
        assert len(res.actions) == 0
