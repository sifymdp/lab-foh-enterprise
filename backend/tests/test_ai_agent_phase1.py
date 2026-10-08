"""Comprehensive Phase 1 Tests for Production-Grade AI Agent & Financial Firewall."""

import unittest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User
from app.models.organization import Organization
from app.models.branch import Branch
from app.models.table import Table
from app.models.session import DiningSession
from app.models.ai_audit import AIAuditEvent
from app.services.ai_agent.security import (
    SAFE_FINANCIAL_REFUSAL_MESSAGE,
    SAFE_FINANCIAL_RESTRICTED_MESSAGE,
    SAFE_TRANSACTION_MUTATION_REFUSAL_MESSAGE,
    assert_financial_import_isolation,
    is_financial_query,
    is_financial_transaction_action,
    scan_payload_for_financial_leak,
    EgressLeakDetected,
    redact_dictionary,
)
from app.services.ai_agent.tools.registry import RegisteredTool, ToolRegistry
from app.services.ai_agent.policy.policy_engine import PolicyClassification
from app.services.ai_agent.orchestrator import ai_orchestrator


class AIAgentPhase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.Session()
        # Seed test org, branch, user, and table
        self.org = Organization(id="org_test", name="Test Org")
        self.branch = Branch(id="branch_test", organization_id="org_test", name="Downtown")
        self.owner_user = User(
            id="user_owner",
            tenant_id="org_test",
            branch_id="branch_test",
            name="Alice Owner",
            email="owner@test.com",
            password_hash="fakehash",
            role="OWNER",
            is_active=True,
            status="ACTIVE",
        )
        self.manager_user = User(
            id="user_manager",
            tenant_id="org_test",
            branch_id="branch_test",
            name="Bob Manager",
            email="manager@test.com",
            password_hash="fakehash",
            role="MANAGER",
            is_active=True,
            status="ACTIVE",
        )
        self.table = Table(
            id="t1_id",
            tenant_id="org_test",
            branch_id="branch_test",
            floor_id="f1",
            section_id="sec1",
            number="1",
            capacity=4,
            type="DINING",
            shape="SQUARE",
            status="AVAILABLE",
            x=10.0,
            y=10.0,
            width=50.0,
            height=50.0,
        )
        self.db.add_all([self.org, self.branch, self.owner_user, self.manager_user, self.table])
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        for tbl in reversed(Base.metadata.sorted_tables):
            try:
                self.db.execute(tbl.delete())
            except Exception:
                pass
        self.db.commit()
        self.db.close()

    def test_01_import_isolation(self):
        """Assures ai_agent subsystem has ZERO imports of confidential billing models/services."""
        assert_financial_import_isolation()

    def test_02_financial_firewall_blocks_spec_prompts(self):
        """Verifies transaction mutations are strictly BLOCKED by the Financial Firewall."""
        mutation_prompts = [
            "Change bill #1023.",
            "Refund this customer.",
            "Change tax to 5%.",
            "Delete today's bills.",
            "Modify payment status.",
            "Create invoice for table.",
            "Refund yesterday's payment.",
            "Cancel bill B1024",
        ]

        for query in mutation_prompts:
            with self.subTest(query=query):
                decision = is_financial_transaction_action(query)
                self.assertTrue(
                    decision.blocked,
                    f"Mutation prompt '{query}' was NOT blocked by Transaction Firewall!"
                )
                self.assertEqual(decision.refusal_message, SAFE_TRANSACTION_MUTATION_REFUSAL_MESSAGE)

    def test_03_non_owner_blocked_from_financial_and_owner_blocked_from_mutations(self):
        """Manager querying revenue is blocked, and Owner querying mutation is blocked."""
        from app.services.ai_agent.security import SAFE_FINANCIAL_RESTRICTED_MESSAGE, SAFE_TRANSACTION_MUTATION_REFUSAL_MESSAGE
        # 1. Manager querying revenue -> blocked
        res_mgr = ai_orchestrator.process_request(
            db=self.db,
            user=self.manager_user,
            query="What's today's revenue?",
        )
        self.assertEqual(res_mgr.classification, "FINANCIAL_REPORT")
        self.assertEqual(res_mgr.response.summary, SAFE_FINANCIAL_RESTRICTED_MESSAGE)
        self.assertEqual(len(res_mgr.actions), 0)

        # 2. Owner querying refund -> blocked
        res_owner_mut = ai_orchestrator.process_request(
            db=self.db,
            user=self.owner_user,
            query="Refund yesterday's payment.",
        )
        self.assertEqual(res_owner_mut.classification, "FINANCIAL_TRANSACTION_ACTION")
        self.assertEqual(res_owner_mut.response.summary, SAFE_TRANSACTION_MUTATION_REFUSAL_MESSAGE)
        self.assertEqual(len(res_owner_mut.actions), 0)

        # Verify audit log was recorded
        audit = self.db.query(AIAuditEvent).filter(AIAuditEvent.classification == "FINANCIAL_TRANSACTION_ACTION").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.policy_result, "BLOCKED")

    def test_04_operational_queries_are_allowed(self):
        """Legitimate operational requests must pass through freely."""
        operational_queries = [
            "Show me the busy tables.",
            "Which tables are free right now?",
            "Show today's reservations.",
            "Which menu items are performing best?",
            "Show CCTV vision mismatches.",
        ]

        for query in operational_queries:
            with self.subTest(query=query):
                decision = is_financial_query(query)
                self.assertFalse(decision.blocked, f"Operational query '{query}' was incorrectly blocked!")
                res = ai_orchestrator.process_request(
                    db=self.db,
                    user=self.manager_user,
                    query=query,
                )
                self.assertNotEqual(res.classification, "FINANCIAL_READ")
                self.assertNotEqual(res.response.summary, SAFE_FINANCIAL_REFUSAL_MESSAGE)

    def test_05_egress_scanner_detects_leaks(self):
        """L4 Egress scanner must raise EgressLeakDetected on forbidden financial keys or currency."""
        leaky_payload = {
            "table_id": "1",
            "guest": "Smith",
            "revenue": 500.0,
        }
        with self.assertRaises(EgressLeakDetected):
            scan_payload_for_financial_leak(leaky_payload)

        leaky_currency = {
            "summary": "Guest spent $125.00 at table 1",
        }
        with self.assertRaises(EgressLeakDetected):
            scan_payload_for_financial_leak(leaky_currency)

    def test_06_redactor_masks_sensitive_tokens(self):
        """L6 Redactor must mask passwords, cards, and auth tokens to [REDACTED]."""
        sample = {
            "username": "alice",
            "password": "secretPassword123",
            "customer_email": "guest@gmail.com",
            "details": {"card": "4111222233334444", "status": "ACTIVE"},
        }
        redacted = redact_dictionary(sample)
        self.assertEqual(redacted["password"], "[REDACTED]")
        self.assertEqual(redacted["customer_email"], "[REDACTED]")
        self.assertEqual(redacted["details"]["card"], "[REDACTED]")
        self.assertEqual(redacted["username"], "alice")

    def test_07_tool_registry_rejects_financial_tools(self):
        """ToolRegistry must reject registration of tools containing financial metadata."""
        custom_registry = ToolRegistry()
        illegal_tool = RegisteredTool(
            name="get_revenue_report",
            description="Returns revenue and tax",
            parameters_schema={},
            permission_required="revenue.view",
            risk_level="HIGH",
            policy_class=PolicyClassification.FINANCIAL_READ,
            handler=lambda db, u, a: {},
        )
        with self.assertRaises(ValueError):
            custom_registry.register_tool(illegal_tool)

    def test_08_table_status_billing_forbidden(self):
        """AI tool set_table_status must reject transition to BILLING or PAID."""
        from app.services.ai_agent.tools.operational_tools import _handle_set_table_status
        with self.assertRaises(ValueError):
            _handle_set_table_status(self.db, self.manager_user, {"table_number": "1", "status": "BILLING"})
        with self.assertRaises(ValueError):
            _handle_set_table_status(self.db, self.manager_user, {"table_number": "1", "status": "PAID"})


if __name__ == "__main__":
    unittest.main()
