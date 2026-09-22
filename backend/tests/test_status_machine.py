import os
import sys
import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.database import Base
from app.models.table import Table
from app.models.organization import Organization
from app.models.floor import Floor
from app.core.status_machine import (
    is_valid_transition,
    can_cctv_transition,
    transition_table,
    InvalidTransitionError,
    ProtectedStateError,
    VALID_TRANSITIONS,
)


class StatusMachineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

        # Seed minimal org, floor, and table
        now = datetime.now(timezone.utc)
        org = Organization(id="org-test", name="Test Org", timezone="UTC", currency="INR", is_active=True, created_at=now, updated_at=now)
        self.db.add(org)
        floor = Floor(id="floor-test", name="Ground", width=800, height=600, tenant_id=org.id)
        self.db.add(floor)
        self.table = Table(
            id="t-test-1",
            floor_id=floor.id,
            tenant_id=org.id,
            section_id="sec-1",
            number="T1",
            capacity=4,
            type="STANDARD",
            shape="RECTANGLE",
            status="AVAILABLE",
            x=10,
            y=10,
            width=100,
            height=100,
        )
        self.db.add(self.table)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_valid_transitions(self) -> None:
        # AVAILABLE -> SEATED
        self.assertTrue(is_valid_transition("AVAILABLE", "SEATED"))
        # SEATED -> ACTIVE
        self.assertTrue(is_valid_transition("SEATED", "ACTIVE"))
        # ACTIVE -> BILLING
        self.assertTrue(is_valid_transition("ACTIVE", "BILLING"))
        # BILLING -> CLEANING
        self.assertTrue(is_valid_transition("BILLING", "CLEANING"))
        # CLEANING -> AVAILABLE
        self.assertTrue(is_valid_transition("CLEANING", "AVAILABLE"))

    def test_invalid_transitions(self) -> None:
        # AVAILABLE cannot jump straight to BILLING
        self.assertFalse(is_valid_transition("AVAILABLE", "BILLING"))
        # BILLING cannot jump back to SEATED directly
        self.assertFalse(is_valid_transition("BILLING", "SEATED"))

    def test_cctv_billing_protection(self) -> None:
        # CCTV cannot touch table in BILLING status
        allowed, msg = can_cctv_transition("BILLING", "AVAILABLE")
        self.assertFalse(allowed)
        self.assertIn("BILLING state", msg)

        allowed, msg = can_cctv_transition("BILLING", "CLEANING")
        self.assertFalse(allowed)

    def test_cctv_allowed_transitions(self) -> None:
        allowed, _ = can_cctv_transition("AVAILABLE", "SEATED")
        self.assertTrue(allowed)

        allowed, _ = can_cctv_transition("CLEANING", "AVAILABLE")
        self.assertTrue(allowed)

    def test_transition_table_execution(self) -> None:
        # Move AVAILABLE -> SEATED
        transition_table(self.db, self.table, "SEATED", source="MANUAL", user_id="u-waiter")
        self.assertEqual(self.table.status, "SEATED")

        # Attempt illegal transition SEATED -> BILLING should raise InvalidTransitionError
        with self.assertRaises(InvalidTransitionError):
            transition_table(self.db, self.table, "BILLING", source="MANUAL")

        # CCTV trying to clear table from BILLING raises ProtectedStateError
        self.table.status = "BILLING"
        self.db.commit()
        with self.assertRaises(ProtectedStateError):
            transition_table(self.db, self.table, "AVAILABLE", source="CCTV")


if __name__ == "__main__":
    unittest.main()
