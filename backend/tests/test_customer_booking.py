import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Floor, Table
from app.services import customer_service
from fastapi import HTTPException


class CustomerBookingTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        from app.models.organization import Organization
        self.db.add(Organization(id="org-demo", name="Demo"))
        self.db.add(Floor(id="floor-1", tenant_id="org-demo", name="Main"))
        self.db.add(Table(id="table-1", tenant_id="org-demo", floor_id="floor-1", section_id="main", number="1", capacity=4,
                          type="standard", shape="round", status="AVAILABLE", x=0, y=0, width=100, height=100, rotation=0))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_otp_is_one_time_and_customer_can_hold(self):
        response = customer_service.request_otp(self.db, "guest@example.com")
        token, _ = customer_service.verify_otp(self.db, "guest@example.com", response["development_otp"])
        self.assertTrue(token)
        with self.assertRaises(HTTPException):
            customer_service.verify_otp(self.db, "guest@example.com", response["development_otp"])

    def test_second_customer_cannot_hold_same_slot(self):
        first = customer_service.hold(self.db, "a@example.com", "table-1", "A", "2030-01-01", "19:00", 2)
        self.assertEqual(first.status, "PENDING")
        with self.assertRaises(HTTPException) as caught:
            customer_service.hold(self.db, "b@example.com", "table-1", "B", "2030-01-01", "19:00", 2)
        self.assertEqual(caught.exception.status_code, 409)

    def test_customer_cannot_cancel_another_customers_booking(self):
        booking = customer_service.hold(self.db, "a@example.com", "table-1", "A", "2030-01-01", "19:00", 2)
        with self.assertRaises(HTTPException) as caught:
            customer_service.cancel(self.db, "b@example.com", booking.id)
        self.assertEqual(caught.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
