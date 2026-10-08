"""E2E Test for AI Assistant HTTP Endpoints, Owner-Only Financial Reporting, and Mutation Firewall."""

import os
import sys

backend_dir = r"d:\lab-foh-enterprise-dev\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from app.main import app
from app.core.deps import get_current_user
from app.models.user import User
from app.services.ai_agent.security import (
    SAFE_FINANCIAL_RESTRICTED_MESSAGE,
    SAFE_TRANSACTION_MUTATION_REFUSAL_MESSAGE,
)

# Mock authenticated users
mock_owner = User(
    id="test_owner_e2e",
    name="Test Owner",
    email="owner@e2e.test",
    password_hash="fake",
    role="OWNER",
    is_active=True,
    status="ACTIVE",
    tenant_id="org-demo",
    branch_id="branch-demo",
)

mock_manager = User(
    id="test_manager_e2e",
    name="Test Manager",
    email="manager@e2e.test",
    password_hash="fake",
    role="MANAGER",
    is_active=True,
    status="ACTIVE",
    tenant_id="org-demo",
    branch_id="branch-demo",
)


def log(msg, status="INFO"):
    print(f"[{status}] {msg}")


def run_e2e_tests():
    with TestClient(app) as client:
        log("=== Commencing AI Intelligence & Owner Financial Reporting E2E HTTP Test ===")

        # ── TEST 1: Authenticated Owner Allowed to Read Daily Revenue ──
        app.dependency_overrides[get_current_user] = lambda: mock_owner
        revenue_payload = {"message": "What's today's revenue?"}
        r = client.post("/ai/chat", json=revenue_payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        log(f"Owner revenue reply: {data.get('reply')[:80]}...")
        assert data.get("classification") == "FINANCIAL_REPORT", f"Expected FINANCIAL_REPORT, got {data.get('classification')}"
        actions = data.get("actions", [])
        assert len(actions) > 0, "Owner financial report should emit navigation action"
        nav_action = next((a for a in actions if a.get("type") == "NAVIGATE"), None)
        assert nav_action is not None, "Expected NAVIGATE action"
        assert nav_action.get("route") == "/revenue", f"Expected /revenue, got {nav_action.get('route')}"
        log("PASS: Owner successfully received daily revenue report and navigation to /revenue.")

        # ── TEST 2: Authenticated Owner Allowed to Compare Periods ──
        compare_payload = {"message": "Compare September revenue with August."}
        r = client.post("/ai/chat", json=compare_payload)
        assert r.status_code == 200
        data = r.json()
        assert data.get("classification") == "FINANCIAL_REPORT"
        assert "Revenue Comparison" in data.get("reply")
        log("PASS: Owner successfully received comparative revenue analysis.")

        # ── TEST 3: Transaction Mutation STRICTLY BLOCKED Even for Owner ──
        mutation_payload = {"message": "Refund yesterday's payment."}
        r = client.post("/ai/chat", json=mutation_payload)
        assert r.status_code == 200
        data = r.json()
        assert data.get("classification") == "FINANCIAL_TRANSACTION_ACTION"
        assert data.get("reply") == SAFE_TRANSACTION_MUTATION_REFUSAL_MESSAGE
        assert len(data.get("actions", [])) == 0, "Blocked mutation must not emit actions"
        log("PASS: Transaction mutation (refund) strictly blocked even for Owner.")

        # ── TEST 4: Non-Owner (Manager) Blocked from Financial Reporting ──
        app.dependency_overrides[get_current_user] = lambda: mock_manager
        r = client.post("/ai/chat", json=revenue_payload)
        assert r.status_code == 200
        data = r.json()
        assert data.get("classification") == "FINANCIAL_REPORT"
        assert data.get("reply") == SAFE_FINANCIAL_RESTRICTED_MESSAGE
        assert len(data.get("actions", [])) == 0
        log("PASS: Manager received permission-safe restriction message on revenue query.")

        # ── TEST 5: Operational Query: Busy Tables (Allowed for Manager) ──
        busy_payload = {"message": "Show me the busy tables."}
        r = client.post("/ai/chat", json=busy_payload)
        assert r.status_code == 200
        data = r.json()
        assert data.get("classification") == "OPERATIONAL_ANALYTICS"
        actions = data.get("actions", [])
        nav_action = next((a for a in actions if a.get("type") == "NAVIGATE"), None)
        assert nav_action is not None
        assert nav_action.get("route") == "/floor"
        log("PASS: Operational query successfully emitted NAVIGATE to /floor.")

        # ── TEST 6: Vision Inquiry: Vision Mismatches ──
        vision_payload = {"message": "Show CCTV vision mismatches."}
        r = client.post("/ai/chat", json=vision_payload)
        assert r.status_code == 200
        data = r.json()
        actions = data.get("actions", [])
        nav_action = next((a for a in actions if a.get("type") == "NAVIGATE"), None)
        assert nav_action is not None
        assert nav_action.get("route") == "/camera-setup"
        log("PASS: Vision query successfully emitted NAVIGATE to /camera-setup.")

        # ── TEST 7: Provider Status Endpoint ──
        r = client.get("/ai/provider")
        assert r.status_code == 200
        p_status = r.json()
        log(f"Provider status: Connected={p_status.get('connected')}, Provider={p_status.get('provider')}")
        log("PASS: /ai/provider returned healthy status.")

        # ── TEST 8: Verify Existing FOH Endpoints Untouched ──
        r = client.get("/floors/current")
        assert r.status_code == 200
        log(f"FOH /floors/current endpoint verified healthy (Returned floor: {r.json().get('id')}).")

        r = client.get("/menu")
        assert r.status_code == 200
        log(f"FOH /menu endpoint verified healthy (Returned {len(r.json())} items).")

        log("🎉 ALL E2E OWNER FINANCIAL INTELLIGENCE & TRANSACTION ISOLATION TESTS PASSED!", "SUCCESS")


if __name__ == "__main__":
    run_e2e_tests()
