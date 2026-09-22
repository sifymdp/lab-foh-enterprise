import unittest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Floor, Reservation, Table
from app.services import voice_receptionist_service


class TestVoiceReceptionist(unittest.TestCase):
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

        floor = Floor(id="floor-1", tenant_id="org-demo", name="FOH Grand Dining", width=1200, height=800, sections=[], labels=[])
        self.db.add(floor)

        table1 = Table(
            id="t-1",
            tenant_id="org-demo",
            floor_id="floor-1",
            section_id="sec-1",
            number="4",
            capacity=4,
            type="BOOTH",
            shape="RECTANGLE",
            status="AVAILABLE",
            x=100,
            y=100,
            width=80,
            height=80,
            rotation=0,
        )
        table2 = Table(
            id="t-2",
            tenant_id="org-demo",
            floor_id="floor-1",
            section_id="sec-1",
            number="8",
            capacity=2,
            type="STANDARD",
            shape="ROUND",
            status="AVAILABLE",
            x=200,
            y=100,
            width=80,
            height=80,
            rotation=0,
        )
        self.db.add(table1)
        self.db.add(table2)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_parse_voice_booking_transcript(self):
        transcript = "Hi there, I'd like to book a table for four guests tonight at 7:30 pm under the name Alex Morgan. We'd love a booth if possible."
        parsed = voice_receptionist_service.parse_voice_booking_transcript(transcript)
        self.assertEqual(parsed["party_size"], 4)
        self.assertEqual(parsed["guest_name"], "Alex Morgan")
        self.assertEqual(parsed["time"], "19:30")
        self.assertIn("Booth seating preferred", parsed["special_requests"])

    def test_process_voice_reservation_success(self):
        transcript = "Hello, this is David Miller. I need a table for 4 tonight at 8 pm, booth preferred."
        res = voice_receptionist_service.process_voice_reservation(self.db, transcript, caller_phone="+1-555-0199")

        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "CONFIRMED")
        self.assertEqual(res["table_number"], "4")  # Selected booth Table 4
        self.assertIn("David Miller", res["voice_response"])
        self.assertIn("Table 4", res["voice_response"])

        # Check reservation saved in DB
        db_res = self.db.get(Reservation, res["reservation_id"])
        self.assertIsNotNone(db_res)
        self.assertEqual(db_res.guest_name, "David Miller")
        self.assertEqual(db_res.party_size, 4)
        self.assertEqual(db_res.status, "CONFIRMED")


if __name__ == "__main__":
    unittest.main()
