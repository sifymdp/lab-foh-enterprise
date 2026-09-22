import unittest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Bill, DiningSession, Floor, Order, Table
from app.models.order_item import OrderItem
from app.services import loss_prevention_service


class TestLossPrevention(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = Session()

        from app.models.organization import Organization
        org = Organization(id="org-demo", name="Demo Restaurant")
        self.db.add(org)

        # Seed test floor, table, and active session
        floor = Floor(id="floor-1", tenant_id="org-demo", name="Main Dining", width=1200, height=800, sections=[], labels=[])
        self.db.add(floor)

        table = Table(
            id="t-1",
            tenant_id="org-demo",
            floor_id="floor-1",
            section_id="sec-1",
            number="1",
            capacity=4,
            type="STANDARD",
            shape="RECTANGLE",
            status="BILLING",
            x=100,
            y=100,
            width=80,
            height=80,
            rotation=0,
        )
        self.db.add(table)

        now = datetime.now(timezone.utc)
        session = DiningSession(
            id="sess-1",
            tenant_id="org-demo",
            table_id="t-1",
            guest_name="Jane Doe",
            party_size=4,
            seated_at=now,
            status="BILLING",
        )
        self.db.add(session)

        order = Order(
            id="ord-1",
            tenant_id="org-demo",
            session_id="sess-1",
            table_id="t-1",
            placed_at=now,
            status="SERVED",
        )
        self.db.add(order)

        item1 = OrderItem(
            id="oi-1",
            order_id="ord-1",
            item_name="Steak Frites",
            unit_price=36.00,
            quantity=2,
        )
        item2 = OrderItem(
            id="oi-2",
            order_id="ord-1",
            item_name="House Wine",
            unit_price=14.00,
            quantity=1,
        )
        self.db.add(item1)
        self.db.add(item2)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_calculate_table_exposure(self):
        exposure = loss_prevention_service.calculate_table_exposure(self.db, "t-1")
        self.assertIsNotNone(exposure)
        self.assertEqual(exposure["unpaid_total"], 86.00)  # (36*2) + 14
        self.assertEqual(exposure["item_count"], 3)
        self.assertEqual(exposure["guest_name"], "Jane Doe")

    def test_trigger_and_resolve_walkout(self):
        table = self.db.get(Table, "t-1")
        exposure = loss_prevention_service.calculate_table_exposure(self.db, "t-1")

        # 1. Trigger alert
        event = loss_prevention_service.trigger_walkout_alert(self.db, table, exposure)
        self.assertEqual(event.event_type, "WALKOUT_ALERT")
        self.assertTrue(table.walkout_alert_sent)

        # 2. Verify summary
        summary = loss_prevention_service.get_loss_prevention_summary(self.db)
        self.assertGreaterEqual(summary["active_alerts"], 1)
        self.assertGreaterEqual(summary["active_exposure"], 86.00)

        # 3. Resolve incident as PAID_COUNTER
        res = loss_prevention_service.resolve_walkout_incident(
            self.db,
            event_id=event.id,
            resolution_type="PAID_COUNTER",
            user_id="user-manager",
            notes="Guest settled via cash at counter",
        )
        self.assertTrue(res["resolved"])
        self.assertFalse(table.walkout_alert_sent)
        self.assertEqual(table.status, "CLEANING")

        # 4. Verify summary reflects recovered amount
        summary2 = loss_prevention_service.get_loss_prevention_summary(self.db)
        self.assertEqual(summary2["active_alerts"], 0)
        self.assertGreaterEqual(summary2["prevented_amount"], 86.00)


if __name__ == "__main__":
    unittest.main()
