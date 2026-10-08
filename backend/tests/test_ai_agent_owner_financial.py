"""Comprehensive Test Suite for Owner-Only Read-Only Financial Reporting & Transaction Isolation."""

import sys
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.core.permissions import (
    PERM_AI_ASSISTANT_USE,
    PERM_AI_FINANCIAL_REPORTING,
    is_authorized_for_financial_reporting,
)
from app.database import SessionLocal
from app.models.user import User
from app.models.bill import Bill
from app.models.payment import Payment
from app.services.ai_agent.orchestrator import ai_orchestrator
from app.services.ai_agent.security.financial_firewall import (
    SAFE_FINANCIAL_RESTRICTED_MESSAGE,
    SAFE_TRANSACTION_MUTATION_REFUSAL_MESSAGE,
    is_financial_reporting_query,
    is_financial_transaction_action,
)
from app.services.ai_agent.security.import_guard import assert_financial_import_isolation
from app.services.financial_reporting_service import financial_reporting_service


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def owner_user(db: Session):
    owner = db.query(User).filter(User.role == "OWNER").first()
    if not owner:
        owner = User(
            id="test-owner-fin",
            name="Test Owner",
            email="owner_fin@test.local",
            role="OWNER",
            is_active=True,
            status="ACTIVE",
            tenant_id="org-demo",
            branch_id="branch-demo",
        )
        db.add(owner)
        db.commit()
    return owner


@pytest.fixture(scope="module")
def manager_user(db: Session):
    mgr = db.query(User).filter(User.role == "MANAGER").first()
    if not mgr:
        mgr = User(
            id="test-mgr-fin",
            name="Test Manager",
            email="mgr_fin@test.local",
            role="MANAGER",
            is_active=True,
            status="ACTIVE",
            tenant_id="org-demo",
            branch_id="branch-demo",
        )
        db.add(mgr)
        db.commit()
    return mgr


@pytest.fixture(scope="module")
def cashier_user(db: Session):
    csh = db.query(User).filter(User.role == "CASHIER").first()
    if not csh:
        csh = User(
            id="test-csh-fin",
            name="Test Cashier",
            email="csh_fin@test.local",
            role="CASHIER",
            is_active=True,
            status="ACTIVE",
            tenant_id="org-demo",
            branch_id="branch-demo",
        )
        db.add(csh)
        db.commit()
    return csh


class TestOwnerFinancialIntelligence:

    def test_01_import_boundary_guard_preserved(self):
        """Verifies AI Agent subsystem imports zero forbidden billing models or services."""
        assert_financial_import_isolation()

    def test_02_transaction_mutations_blocked_for_all_users(self, db: Session, owner_user: User, manager_user: User):
        """Financial mutations (refunds, delete bill, change tax) must be BLOCKED even for Owners."""
        mutation_prompts = [
            "Refund yesterday's payment.",
            "Refund bill #1023",
            "Change tax to 10%",
            "Delete today's bills",
            "Modify payment status to paid",
            "Create invoice for Table 4",
            "Cancel bill B1024",
            "Process payment on bill",
            "Alter cashier shift drawer",
        ]

        for prompt in mutation_prompts:
            # 1. Direct firewall check
            decision = is_financial_transaction_action(prompt)
            assert decision.blocked is True, f"Failed to detect mutation on: {prompt}"
            assert decision.refusal_message == SAFE_TRANSACTION_MUTATION_REFUSAL_MESSAGE

            # 2. End-to-End Orchestrator check for OWNER
            res_owner = ai_orchestrator.process_request(db=db, user=owner_user, query=prompt)
            assert res_owner.classification == "FINANCIAL_TRANSACTION_ACTION"
            assert res_owner.response.summary == SAFE_TRANSACTION_MUTATION_REFUSAL_MESSAGE
            assert len(res_owner.actions) == 0, "Mutations must never emit UI actions"

            # 3. End-to-End Orchestrator check for MANAGER
            res_mgr = ai_orchestrator.process_request(db=db, user=manager_user, query=prompt)
            assert res_mgr.classification == "FINANCIAL_TRANSACTION_ACTION"
            assert res_mgr.response.summary == SAFE_TRANSACTION_MUTATION_REFUSAL_MESSAGE

    def test_03_non_owner_roles_blocked_from_financial_reporting(self, db: Session, manager_user: User, cashier_user: User):
        """Managers, Cashiers, Waiters must receive permission-safe block on financial queries."""
        financial_queries = [
            "What was the revenue for today?",
            "What was the revenue yesterday?",
            "Show me the financial summary for September.",
            "Compare September revenue with August.",
            "Show me the payment-method summary.",
        ]

        for q in financial_queries:
            # Manager has AI assistant use permission, but is NOT Owner -> gets financial restriction
            res_mgr = ai_orchestrator.process_request(db=db, user=manager_user, query=q)
            assert res_mgr.classification == "FINANCIAL_REPORT"
            assert res_mgr.response.summary == SAFE_FINANCIAL_RESTRICTED_MESSAGE
            assert len(res_mgr.actions) == 0

            # Cashier without assistant permission is blocked at RBAC
            res_csh = ai_orchestrator.process_request(db=db, user=cashier_user, query=q)
            assert res_csh.classification in ("FINANCIAL_REPORT", "SECURITY_ACTION")
            assert len(res_csh.actions) == 0

    def test_04_owner_authorized_for_daily_revenue_queries(self, db: Session, owner_user: User):
        """Owner receives formatted revenue and NAVIGATE to /revenue with date filter."""
        queries = [
            "What was the revenue for today?",
            "What was the revenue yesterday?",
            "Show me the revenue for 15 September.",
            "Show me the daily revenue summary.",
        ]

        for q in queries:
            res = ai_orchestrator.process_request(db=db, user=owner_user, query=q)
            assert res.classification == "FINANCIAL_REPORT"
            assert "Revenue Summary" in res.response.summary or "Financial Report" in res.response.summary
            assert len(res.actions) > 0
            nav_action = next((a for a in res.actions if a.type == "NAVIGATE"), None)
            assert nav_action is not None
            assert nav_action.route == "/revenue"
            assert nav_action.filter is not None
            assert "date" in nav_action.filter

    def test_05_owner_authorized_for_period_comparisons(self, db: Session, owner_user: User):
        """Owner receives comparative period breakdown and navigation."""
        q = "Compare September revenue with August."
        res = ai_orchestrator.process_request(db=db, user=owner_user, query=q)
        assert res.classification == "FINANCIAL_REPORT"
        assert "Revenue Comparison" in res.response.summary
        assert "September" in res.response.summary
        assert "August" in res.response.summary
        nav_action = next((a for a in res.actions if a.type == "NAVIGATE"), None)
        assert nav_action is not None
        assert nav_action.route == "/revenue"
        assert nav_action.filter.get("comparison") == "true"

    def test_06_owner_authorized_for_payment_method_breakdown(self, db: Session, owner_user: User):
        """Owner receives payment method breakdown (Cash, Card, UPI, QR, Online)."""
        q = "Show me the payment-method summary."
        res = ai_orchestrator.process_request(db=db, user=owner_user, query=q)
        assert res.classification == "FINANCIAL_REPORT"
        assert "Payment Method Breakdown" in res.response.summary
        assert "Cash" in res.response.summary
        assert "UPI" in res.response.summary
        nav_action = next((a for a in res.actions if a.type == "NAVIGATE"), None)
        assert nav_action is not None
        assert nav_action.route == "/revenue"
        assert nav_action.filter.get("tab") == "payment_methods"

    def test_07_operational_queries_unaffected(self, db: Session, manager_user: User):
        """Operational queries continue to work for Managers and emit floor actions."""
        q = "Show me the busy tables."
        res = ai_orchestrator.process_request(db=db, user=manager_user, query=q)
        assert res.classification == "OPERATIONAL_ANALYTICS"
        assert len(res.actions) > 0
        nav_action = next((a for a in res.actions if a.type == "NAVIGATE"), None)
        assert nav_action is not None
        assert nav_action.route == "/floor"
