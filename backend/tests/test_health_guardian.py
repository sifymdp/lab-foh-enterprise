"""
Automated Test Suite — System B: Enterprise Backend Health Guardian
───────────────────────────────────────────────────────────────────
Verifies subsystem health probing, error classification, allowlisted
safe self-recovery, incident persistence, and distributed locking.
"""

import unittest
from datetime import datetime, timezone

from app.database import Base, SessionLocal, engine
from app.models.health_guardian import (
    HealthAudit,
    HealthCheckResult,
    RecoveryActionLog,
    SystemIncident,
)
from app.services.health_guardian.error_classifier import ErrorCategory, classify_error
from app.services.health_guardian.guardian_service import (
    get_latest_health_summary,
    list_recent_audits,
    list_system_incidents,
    resolve_system_incident,
    run_comprehensive_audit,
    run_lightweight_probe,
)
from app.services.health_guardian.health_check_registry import (
    check_database,
    check_storage,
    check_websockets,
    run_all_probes,
)
from app.services.health_guardian.recovery_policy_registry import execute_recovery_action


class HealthGuardianTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_subsystem_probes(self):
        """Verifies all registered health checks execute and return structured findings."""
        db_res = check_database(self.db)
        self.assertIn(db_res["status"], ["PASS", "WARN"])
        self.assertEqual(db_res["component"], "DATABASE")
        self.assertGreaterEqual(db_res["latency_ms"], 0)

        ws_res = check_websockets()
        self.assertEqual(ws_res["status"], "PASS")
        self.assertEqual(ws_res["component"], "WEBSOCKETS")

        storage_res = check_storage()
        self.assertIn(storage_res["status"], ["PASS", "WARN"])
        self.assertEqual(storage_res["component"], "STORAGE")

        all_probes = run_all_probes(self.db)
        self.assertGreaterEqual(len(all_probes), 6)

    def test_error_classification_taxonomy(self):
        """Verifies error strings map to correct severity and recovery policies."""
        res_timeout = classify_error("DATABASE", "Connection timed out after 5000ms")
        self.assertEqual(res_timeout["category"], ErrorCategory.TRANSIENT)

        res_locked = classify_error("DATABASE", "sqlite3.OperationalError: database is locked")
        self.assertEqual(res_locked["category"], ErrorCategory.RESOURCE_EXHAUSTION)

        res_cam = classify_error("CCTV_VISION", "RTSP capture stream failed to decode frame")
        self.assertEqual(res_cam["category"], ErrorCategory.DEPENDENCY_UNAVAILABLE)
        self.assertEqual(res_cam["recommended_recovery"], "RESTART_CAMERA_STREAM_WORKER")

    def test_allowlisted_safe_recovery_execution(self):
        """Verifies allowlisted actions execute and verify safely without destructive changes."""
        rec_res = execute_recovery_action(self.db, "REFRESH_CONNECTION_POOL")
        self.assertEqual(rec_res["status"], "SUCCESS")
        self.assertTrue(rec_res["verification_passed"])

        rec_ws = execute_recovery_action(self.db, "PRUNE_DEAD_SOCKET_CONNECTIONS")
        self.assertEqual(rec_ws["status"], "SUCCESS")
        self.assertTrue(rec_ws["verification_passed"])

        rec_invalid = execute_recovery_action(self.db, "DROP_DATABASE_TABLES")
        self.assertEqual(rec_invalid["status"], "ABORTED")
        self.assertFalse(rec_invalid["verification_passed"])

    def test_comprehensive_audit_cycle_and_locking(self):
        """Verifies 12-hour audit execution creates durable audit records and releases lock."""
        audit_res = run_comprehensive_audit(self.db, audit_type="SCHEDULED_12H")
        self.assertIn(audit_res["overall_status"], ["HEALTHY", "DEGRADED", "UNHEALTHY"])
        self.assertIn("audit_id", audit_res)

        # Check durable database records
        audit_db = self.db.get(HealthAudit, audit_res["audit_id"])
        self.assertIsNotNone(audit_db)
        self.assertFalse(audit_db.is_active)  # Lock was released cleanly
        self.assertIsNotNone(audit_db.next_scheduled_run)

        # Check results recorded
        results = self.db.query(HealthCheckResult).filter(
            HealthCheckResult.audit_id == audit_res["audit_id"]
        ).all()
        self.assertGreaterEqual(len(results), 6)

    def test_incident_lifecycle_and_resolution(self):
        """Verifies incident logging and authorized administrator resolution."""
        incident = SystemIncident(
            id="inc-test-unit",
            component="CCTV_VISION",
            severity="MEDIUM",
            error_category="TRANSIENT",
            title="Unit Test Discrepancy",
            description="Simulated test frame timeout",
            status="OPEN",
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        self.db.merge(incident)
        self.db.commit()

        # Resolve incident
        resolved = resolve_system_incident(
            self.db, "inc-test-unit", user_id="admin-1", notes="Verified restored in test"
        )
        self.assertTrue(resolved)

        self.db.expire_all()
        updated = self.db.get(SystemIncident, "inc-test-unit")
        self.assertEqual(updated.status, "RESOLVED")
        self.assertEqual(updated.acknowledged_by, "admin-1")


if __name__ == "__main__":
    unittest.main()
