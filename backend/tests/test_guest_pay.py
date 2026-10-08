import unittest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Bill, DiningSession, Floor, Order, Table, TableQRCode
from app.models.order_item import OrderItem
from app.routers.guest import GuestPayRequest, get_guest_bill, process_guest_payment


class TestGuestPayAndWalk(unittest.TestCase):
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

        floor = Floor(id="floor-1", tenant_id="org-demo", name="Main Dining", width=1200, height=800, sections=[], labels=[])
        self.db.add(floor)

        table = Table(
            id="t-1",
            tenant_id="org-demo",
            floor_id="floor-1",
            section_id="sec-1",
            number="12",
            capacity=4,
            type="STANDARD",
            shape="RECTANGLE",
            status="BILLING",
            x=100,
            y=100,
            width=80,
            height=80,
            rotation=0,
            walkout_alert_sent=True,
        )
        self.db.add(table)

        qr = TableQRCode(
            id="qr-1",
            table_id="t-1",
            token="valid-test-token-123",
            is_active=True,
        )
        self.db.add(qr)

        now = datetime.now(timezone.utc)
        session = DiningSession(
            id="sess-1",
            tenant_id="org-demo",
            table_id="t-1",
            guest_name="Sarah Connor",
            party_size=2,
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
            id="item-1",
            order_id="ord-1",
            item_name="Truffle Pasta",
            unit_price=24.0,
            quantity=2,
        )
        item2 = OrderItem(
            id="item-2",
            order_id="ord-1",
            item_name="Sparkling Water",
            unit_price=4.5,
            quantity=2,
        )
        self.db.add(item1)
        self.db.add(item2)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_get_guest_bill(self):
        bill_data = get_guest_bill(token="valid-test-token-123", db=self.db)
        self.assertTrue(bill_data["hasActiveSession"])
        self.assertEqual(bill_data["tableNumber"], "12")
        self.assertEqual(bill_data["guestName"], "Sarah Connor")
        self.assertEqual(len(bill_data["items"]), 2)
        self.assertEqual(bill_data["subtotal"], 57.0)  # 24*2 + 4.5*2 = 48 + 9 = 57.0
        self.assertFalse(bill_data["isPaid"])

    def test_process_guest_payment_success(self):
        req = GuestPayRequest(
            token="valid-test-token-123",
            split_count=2,
            amount_paid=57.0,
            tip=5.70,
            payment_method="APPLE_PAY",
        )
        result = process_guest_payment(req, db=self.db)
        self.assertTrue(result["success"])
        self.assertFalse(result["alreadyPaid"])
        self.assertEqual(result["totalCharged"], 62.70)
        self.assertEqual(result["paymentMethod"], "APPLE_PAY")

        # Verify database state after Pay & Walk
        table = self.db.get(Table, "t-1")
        self.assertFalse(table.walkout_alert_sent)
        self.assertEqual(table.status, "CLEANING")

        session = self.db.get(DiningSession, "sess-1")
        self.assertEqual(session.status, "PAID")
        self.assertEqual(session.payment_method, "APPLE_PAY")

        bill = self.db.query(Bill).filter(Bill.session_id == "sess-1").first()
        self.assertIsNotNone(bill)
        self.assertEqual(bill.status, "PAID")

        # Test double-payment idempotency
        second_attempt = process_guest_payment(req, db=self.db)
        self.assertTrue(second_attempt["success"])
        self.assertTrue(second_attempt["alreadyPaid"])


if __name__ == "__main__":
    unittest.main()
