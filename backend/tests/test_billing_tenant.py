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

import json
from app.database import Base
from app.models import Bill, Branch, Floor, Organization, ServiceCharge, TaxRule
from app.models.system_configuration import SystemConfiguration
from app.services.billing_service import calculate_bill
from app.services.floor_service import get_current_floor



class BackendSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_calculate_bill_uses_branch_rule_first(self) -> None:
        db = self.SessionLocal()
        org = Organization(
            id="org-1",
            name="Org 1",
            email="org1@example.com",
            timezone="UTC",
            currency="USD",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        branch = Branch(
            id="branch-1",
            organization_id=org.id,
            name="Branch 1",
            timezone="UTC",
            currency="USD",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        bill = Bill(
            id="bill-1",
            session_id="session-1",
            tenant_id=org.id,
            branch_id=branch.id,
            subtotal=100,
            total=100,
            generated_at=datetime.now(timezone.utc),
            status="OPEN",
        )
        db.add_all(
            [
                org,
                branch,
                Floor(
                    id="floor-1",
                    name="Floor 1",
                    width=1000,
                    height=800,
                    tenant_id=org.id,
                    branch_id=branch.id,
                ),
                bill,
                ServiceCharge(
                    id="svc-global",
                    tenant_id=org.id,
                    branch_id=None,
                    name="Global Service",
                    rate=10,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                ),
                ServiceCharge(
                    id="svc-branch",
                    tenant_id=org.id,
                    branch_id=branch.id,
                    name="Branch Service",
                    rate=12,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                ),
                TaxRule(
                    id="tax-global",
                    tenant_id=org.id,
                    branch_id=None,
                    name="Global Tax",
                    rate=5,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                ),
                TaxRule(
                    id="tax-branch",
                    tenant_id=org.id,
                    branch_id=branch.id,
                    name="Branch Tax",
                    rate=8,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                ),
                SystemConfiguration(
                    id="cfg-1",
                    tenant_id=org.id,
                    branch_id=branch.id,
                    key="billing_settings",
                    value=json.dumps({
                        "currency": "USD",
                        "tax_rate": 8.0,
                        "service_charge_rate": 12.0
                    }),
                    version=1,
                    is_active=True,
                    created_at=datetime.now(timezone.utc)
                )
            ]
        )
        db.commit()


        calculate_bill(db, bill)
        self.assertAlmostEqual(float(bill.service_charge_amount), 12.0, places=2)
        self.assertAlmostEqual(float(bill.tax_amount), 8.96, places=2)
        self.assertAlmostEqual(float(bill.total), 120.96, places=2)
        db.close()

    def test_get_current_floor_scopes_by_tenant_and_branch(self) -> None:
        db = self.SessionLocal()
        org_1 = Organization(
            id="org-1",
            name="Org 1",
            email="org1@example.com",
            timezone="UTC",
            currency="USD",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        org_2 = Organization(
            id="org-2",
            name="Org 2",
            email="org2@example.com",
            timezone="UTC",
            currency="USD",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        branch_1 = Branch(
            id="branch-1",
            organization_id=org_1.id,
            name="Branch 1",
            timezone="UTC",
            currency="USD",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        branch_2 = Branch(
            id="branch-2",
            organization_id=org_2.id,
            name="Branch 2",
            timezone="UTC",
            currency="USD",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add_all(
            [
                org_1,
                org_2,
                branch_1,
                branch_2,
                Floor(
                    id="floor-1",
                    name="Floor 1",
                    width=1000,
                    height=800,
                    tenant_id=org_1.id,
                    branch_id=branch_1.id,
                ),
                Floor(
                    id="floor-2",
                    name="Floor 2",
                    width=1000,
                    height=800,
                    tenant_id=org_2.id,
                    branch_id=branch_2.id,
                ),
            ]
        )
        db.commit()

        floor = get_current_floor(db, tenant_id=org_2.id, branch_id=branch_2.id)
        self.assertEqual(floor.id, "floor-2")
        db.close()


if __name__ == "__main__":
    unittest.main()
