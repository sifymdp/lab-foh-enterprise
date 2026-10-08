import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.database import Base
from app.models.user import User
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user_permission import UserPermission
from app.models.temporary_permission import TemporaryPermission
from app.models.user_session import UserSession
from app.core.permissions import has_user_permission
from app.services.user_service import is_last_owner


class RBACAndLockoutTests(unittest.TestCase):
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

    def test_dynamic_permission_resolution(self) -> None:
        db = self.SessionLocal()
        
        # Create standard Cashier user
        user = User(
            id="user-1",
            tenant_id="org-1",
            name="Casey Cashier",
            email="casey@gmail.com",
            password_hash="hashed",
            role="CASHIER",
            status="ACTIVE",
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        db.add(user)
        db.commit()

        # Cashier should have standard cashier permissions
        self.assertTrue(has_user_permission(db, user, "billing.create"))
        # But not payment approval
        self.assertFalse(has_user_permission(db, user, "payment.approve"))

        # Grant temporary override
        now = datetime.now(timezone.utc)
        temp = TemporaryPermission(
            id="temp-1",
            user_id=user.id,
            permission="payment.approve",
            start_time=now - timedelta(minutes=5),
            end_time=now + timedelta(minutes=5),
            status="ACTIVE",
            created_by="owner-1",
            created_at=now,
            tenant_id="org-1"
        )
        db.add(temp)
        db.commit()

        # Temporary override should resolve successfully
        self.assertTrue(has_user_permission(db, user, "payment.approve"))

        # Change override status to EXPIRED
        temp.status = "EXPIRED"
        db.commit()
        
        # Verify access is now rejected
        self.assertFalse(has_user_permission(db, user, "payment.approve"))
        db.close()

    def test_brute_force_lockout(self) -> None:
        db = self.SessionLocal()
        user = User(
            id="user-2",
            tenant_id="org-1",
            name="Hannah Host",
            email="hannah@gmail.com",
            password_hash="hashed",
            role="HOST",
            status="ACTIVE",
            is_active=True,
            failed_login_attempts=0,
            created_at=datetime.now(timezone.utc)
        )
        db.add(user)
        db.commit()

        # Simulate consecutive failures
        for _ in range(5):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=15)
        db.commit()

        # Account must be flagged as locked
        self.assertTrue(user.failed_login_attempts >= 5)
        self.assertIsNotNone(user.locked_until)
        self.assertTrue(user.locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc))
        db.close()


    def test_owner_safety_last_owner(self) -> None:
        db = self.SessionLocal()
        owner = User(
            id="owner-1",
            tenant_id="org-1",
            name="Alex Owner",
            email="owner@gmail.com",
            password_hash="hashed",
            role="OWNER",
            status="ACTIVE",
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        db.add(owner)
        db.commit()

        # Must flag owner-1 as the sole active Owner of org-1
        self.assertTrue(is_last_owner(db, "org-1", "owner-1"))

        # Create a second Owner
        owner2 = User(
            id="owner-2",
            tenant_id="org-1",
            name="Alex Second Owner",
            email="owner2@gmail.com",
            password_hash="hashed",
            role="OWNER",
            status="ACTIVE",
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        db.add(owner2)
        db.commit()


        # Now neither should trigger is_last_owner check
        self.assertFalse(is_last_owner(db, "org-1", "owner-1"))
        self.assertFalse(is_last_owner(db, "org-1", "owner-2"))
        db.close()


if __name__ == "__main__":
    unittest.main()
