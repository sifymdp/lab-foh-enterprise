"""
Automated Test Suite — System A: Restaurant Digital Twin
────────────────────────────────────────────────────────
Verifies snapshot accuracy, operational overlays, historical replay,
and what-if simulation engine isolation.
"""

import unittest
from datetime import datetime, timedelta, timezone

from app.database import Base, SessionLocal, engine
from app.models.floor import Floor
from app.models.organization import Organization
from app.models.session import DiningSession
from app.models.table import Table
from app.services.digital_twin.simulation_service import run_what_if_simulation
from app.services.digital_twin.twin_service import (
    get_digital_twin_snapshot,
    get_historical_replay,
)


class DigitalTwinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        self.db = SessionLocal()
        now = datetime.now(timezone.utc)

        # Create isolated tenant, floor, and tables
        self.tenant = Organization(id="org-twin-test", name="Twin Test Org")
        self.db.merge(self.tenant)

        self.floor = Floor(
            id="fl-twin-test",
            tenant_id="org-twin-test",
            name="Main Dining Room",
            width=1200,
            height=800,
            sections="[]",
            labels="[]",
        )
        self.db.merge(self.floor)

        self.t1 = Table(
            id="tbl-twin-1",
            floor_id="fl-twin-test",
            tenant_id="org-twin-test",
            section_id="sec-twin",
            number="T1",
            capacity=4,
            type="DINING",
            shape="RECTANGLE",
            status="SEATED",
            x=100,
            y=100,
            width=80,
            height=80,
            rotation=0,
        )
        self.t2 = Table(
            id="tbl-twin-2",
            floor_id="fl-twin-test",
            tenant_id="org-twin-test",
            section_id="sec-twin",
            number="T2",
            capacity=6,
            type="DINING",
            shape="RECTANGLE",
            status="AVAILABLE",
            x=250,
            y=100,
            width=100,
            height=80,
            rotation=0,
        )
        self.db.merge(self.t1)
        self.db.merge(self.t2)

        # Active dining session on T1
        self.session = DiningSession(
            id="sess-twin-1",
            tenant_id="org-twin-test",
            table_id="tbl-twin-1",
            party_size=4,
            status="SEATED",
            guest_name="Sarah Connor",
            seated_at=now - timedelta(minutes=45),
        )
        self.db.merge(self.session)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_digital_twin_snapshot_and_overlays(self):
        """Verifies snapshot reflects authoritative tables, active durations, and KPIs."""
        snap = get_digital_twin_snapshot(self.db, "fl-twin-test", "org-twin-test")
        self.assertIn("floor", snap)
        self.assertIn("tables", snap)
        self.assertEqual(len(snap["tables"]), 2)

        # Find T1
        t1_snap = next(t for t in snap["tables"] if t["id"] == "tbl-twin-1")
        self.assertEqual(t1_snap["status"], "SEATED")
        self.assertTrue(t1_snap["occupancy"]["is_occupied"])
        self.assertGreaterEqual(t1_snap["occupancy"]["duration_minutes"], 40)
        self.assertEqual(t1_snap["occupancy"]["guest_name"], "Sarah Connor")

        # KPIs
        self.assertEqual(snap["kpis"]["total_tables"], 2)
        self.assertEqual(snap["kpis"]["occupied_tables"], 1)
        self.assertEqual(snap["kpis"]["available_tables"], 1)
        self.assertIsNotNone(snap["sync"]["reconciliation_hash"])

    def test_what_if_simulation_isolation(self):
        """Verifies simulations compute deterministic outcomes without mutating production tables."""
        assumptions = {
            "disabled_table_ids": ["tbl-twin-2"],
            "arrival_surge_pct": 30.0,
            "staff_count": 1,
        }
        res = run_what_if_simulation(
            self.db,
            floor_id="fl-twin-test",
            name="Weekend Surge Simulation",
            scenario_type="SECTION_CLOSURE",
            assumptions=assumptions,
        )

        sim_out = res["results"]["simulation"]
        self.assertEqual(sim_out["active_table_count"], 1)
        self.assertGreater(sim_out["capacity_loss_percent"], 0)
        self.assertGreater(sim_out["workload_pressure_score"], 0)

        # Assert production records were untouched
        self.db.expire_all()
        tbl2 = self.db.get(Table, "tbl-twin-2")
        self.assertEqual(tbl2.status, "AVAILABLE")

    def test_historical_replay_query(self):
        """Verifies historical replay returns formatted timeline structure."""
        start = datetime.now(timezone.utc) - timedelta(hours=2)
        end = datetime.now(timezone.utc) + timedelta(hours=1)
        replay = get_historical_replay(self.db, "fl-twin-test", start, end)
        self.assertIn("timeline", replay)
        self.assertIsInstance(replay["timeline"], list)


if __name__ == "__main__":
    unittest.main()
