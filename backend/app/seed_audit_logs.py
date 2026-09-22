import json
import random
from datetime import datetime, timedelta, timezone
from app.database import SessionLocal
from app.models import User, AuditLog
from app.core.ids import new_id

# IST = UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))


def seed_30_days_audit_logs():
    db = SessionLocal()

    # Delete only seeded sample records (keep real operational records)
    db.query(AuditLog).filter(
        AuditLog.resource_id.like("shift-%")
        | AuditLog.resource_id.like("sess-%")
        | AuditLog.resource_id.like("bill-%")
        | AuditLog.resource_id.like("alert-%")
        | AuditLog.resource_id.like("role-seeded-%")
    ).delete(synchronize_session=False)
    db.commit()

    users = db.query(User).all()
    if not users:
        print("No users found in database!")
        return

    user_by_role = {u.role.upper(): u for u in users}
    owner = user_by_role.get("OWNER") or users[0]
    manager = user_by_role.get("MANAGER") or users[0]
    cashier = user_by_role.get("CASHIER") or users[0]
    waiter = user_by_role.get("WAITER") or users[0]
    host = user_by_role.get("HOST") or users[0]
    chef = user_by_role.get("CHEF") or users[0]

    # Use naive local time (IST) — stored as-is in SQLite
    now_local = datetime.now()
    sample_events = []

    for day_offset in range(30, -1, -1):
        day_date = now_local - timedelta(days=day_offset)

        # 1. Morning Shift Start (8:30 AM - 9:30 AM)
        t_open = day_date.replace(hour=random.randint(8, 9), minute=random.randint(0, 59), second=random.randint(0, 59), microsecond=0)
        sample_events.append(AuditLog(
            id=new_id(),
            user_id=cashier.id,
            tenant_id=cashier.tenant_id,
            branch_id=cashier.branch_id,
            action="CASHIER_SHIFT_OPENED",
            resource_type="cashier_shift",
            resource_id=f"shift-{day_date.strftime('%Y%m%d')}-1",
            old_value=None,
            new_value=json.dumps({"opening_float": 500.0, "cashier": cashier.name, "shift": "Morning"}),
            created_at=t_open,
        ))

        # 2. Staff Logins (9:00 AM - 11:00 AM)
        for u in [owner, manager, host, waiter, chef]:
            t_login = day_date.replace(hour=random.randint(9, 11), minute=random.randint(0, 59), second=random.randint(0, 59), microsecond=0)
            sample_events.append(AuditLog(
                id=new_id(),
                user_id=u.id,
                tenant_id=u.tenant_id,
                branch_id=u.branch_id,
                action="LOGIN_SUCCESS",
                resource_type="user_session",
                resource_id=f"sess-{new_id()[:8]}",
                old_value=None,
                new_value=json.dumps({"ip": f"192.168.1.{random.randint(10, 80)}", "device": "Chrome / FOH POS Terminal"}),
                created_at=t_login,
            ))

        # 3. Lunch & Dinner Table Activity (12:00 PM - 3:00 PM)
        tables_today = random.sample(["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10"], k=random.randint(4, 7))
        for table_num in tables_today:
            t_seat = day_date.replace(hour=random.randint(12, 14), minute=random.randint(0, 59), second=random.randint(0, 59), microsecond=0)
            party_sz = random.randint(2, 6)
            sample_events.append(AuditLog(
                id=new_id(),
                user_id=host.id,
                tenant_id=host.tenant_id,
                branch_id=host.branch_id,
                action="STATUS_CHANGE",
                resource_type="table",
                resource_id=table_num,
                old_value=json.dumps({"status": "AVAILABLE", "table": table_num}),
                new_value=json.dumps({"status": "SEATED", "table": table_num, "party_size": party_sz, "waiter": waiter.name}),
                created_at=t_seat,
            ))

            t_bill = t_seat + timedelta(minutes=random.randint(35, 60))
            amt = round(random.uniform(45.0, 180.0), 2)
            method = random.choice(["CARD", "UPI", "CASH", "ONLINE"])
            sample_events.append(AuditLog(
                id=new_id(),
                user_id=cashier.id,
                tenant_id=cashier.tenant_id,
                branch_id=cashier.branch_id,
                action="BILL_PAID",
                resource_type="bill",
                resource_id=f"bill-{day_date.strftime('%m%d')}-{table_num}",
                old_value=json.dumps({"status": "OPEN", "amount_due": amt, "table": table_num}),
                new_value=json.dumps({"status": "PAID", "amount_paid": amt, "method": method, "cashier": cashier.name}),
                created_at=t_bill,
            ))

        # 4. Evening Table Activity (6:00 PM - 9:00 PM)
        for table_num in random.sample(["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"], k=random.randint(3, 5)):
            t_seat2 = day_date.replace(hour=random.randint(18, 20), minute=random.randint(0, 59), second=random.randint(0, 59), microsecond=0)
            sample_events.append(AuditLog(
                id=new_id(),
                user_id=host.id,
                tenant_id=host.tenant_id,
                branch_id=host.branch_id,
                action="STATUS_CHANGE",
                resource_type="table",
                resource_id=table_num,
                old_value=json.dumps({"status": "AVAILABLE", "table": table_num}),
                new_value=json.dumps({"status": "SEATED", "table": table_num, "party_size": random.randint(2, 8)}),
                created_at=t_seat2,
            ))

            t_bill2 = t_seat2 + timedelta(minutes=random.randint(40, 75))
            amt2 = round(random.uniform(85.0, 320.0), 2)
            sample_events.append(AuditLog(
                id=new_id(),
                user_id=cashier.id,
                tenant_id=cashier.tenant_id,
                branch_id=cashier.branch_id,
                action="BILL_PAID",
                resource_type="bill",
                resource_id=f"bill-{day_date.strftime('%m%d')}-{table_num}-eve",
                old_value=json.dumps({"status": "OPEN", "amount_due": amt2, "table": table_num}),
                new_value=json.dumps({"status": "PAID", "amount_paid": amt2, "method": random.choice(["CARD", "UPI", "CASH"]), "cashier": cashier.name}),
                created_at=t_bill2,
            ))

        # 5. Management & RBAC Operations
        if day_offset % 2 == 0:
            t_rbac = day_date.replace(hour=random.randint(15, 17), minute=random.randint(0, 59), second=random.randint(0, 59), microsecond=0)
            target_role = random.choice(["MANAGER", "HOST", "WAITER", "CASHIER"])
            perm_code = random.choice(["orders.create", "billing.update", "tables.assign", "revenue.view_branch", "camera.override", "menu.manage"])
            sample_events.append(AuditLog(
                id=new_id(),
                user_id=owner.id,
                tenant_id=owner.tenant_id,
                branch_id=owner.branch_id,
                action="GRANT_ROLE_PERMISSION",
                resource_type="role_permission",
                resource_id=f"role-seeded-{target_role.lower()}",
                old_value=json.dumps({"role": target_role, "permission": perm_code, "enabled": False}),
                new_value=json.dumps({"role": target_role, "permission": perm_code, "enabled": True}),
                created_at=t_rbac,
            ))

        if day_offset % 4 == 0:
            t_disc = day_date.replace(hour=random.randint(19, 21), minute=random.randint(0, 59), second=random.randint(0, 59), microsecond=0)
            sample_events.append(AuditLog(
                id=new_id(),
                user_id=manager.id,
                tenant_id=manager.tenant_id,
                branch_id=manager.branch_id,
                action="DISCOUNT_APPLIED",
                resource_type="bill",
                resource_id=f"bill-{day_date.strftime('%m%d')}-VIP",
                old_value=json.dumps({"discount_percent": 0, "original_amount": 220.0}),
                new_value=json.dumps({"discount_percent": 15, "discount_amount": 33.0, "reason": "VIP Customer Loyalty Override", "approved_by": manager.name}),
                created_at=t_disc,
            ))

        if day_offset % 6 == 0:
            t_cv = day_date.replace(hour=random.randint(18, 20), minute=random.randint(0, 59), second=random.randint(0, 59), microsecond=0)
            tbl = random.choice(["T1", "T2", "T3", "T4"])
            sample_events.append(AuditLog(
                id=new_id(),
                user_id=host.id,
                tenant_id=host.tenant_id,
                branch_id=host.branch_id,
                action="CAMERA_MISMATCH_VERIFIED",
                resource_type="camera_alert",
                resource_id=f"alert-cv-{day_date.strftime('%m%d')}",
                old_value=json.dumps({"cctv_state": "OCCUPIED", "pos_state": "AVAILABLE", "table": tbl}),
                new_value=json.dumps({"resolution": "CONFIRMED_SEATED", "verified_by": host.name, "physical_guests": 3}),
                created_at=t_cv,
            ))

        # 6. Evening Shift Close
        t_close = day_date.replace(hour=23, minute=random.randint(15, 55), second=random.randint(0, 59), microsecond=0)
        rev = round(random.uniform(2800.0, 6500.0), 2)
        sample_events.append(AuditLog(
            id=new_id(),
            user_id=cashier.id,
            tenant_id=cashier.tenant_id,
            branch_id=cashier.branch_id,
            action="CASHIER_SHIFT_CLOSED",
            resource_type="cashier_shift",
            resource_id=f"shift-{day_date.strftime('%Y%m%d')}-1",
            old_value=json.dumps({"status": "OPEN", "opening_float": 500.0}),
            new_value=json.dumps({"status": "CLOSED", "total_collected": rev, "card_total": round(rev * 0.55, 2), "cash_total": round(rev * 0.45, 2), "discrepancy": 0.0}),
            created_at=t_close,
        ))

    db.bulk_save_objects(sample_events)
    db.commit()
    db.close()

    # Verify date distribution
    db2 = SessionLocal()
    from sqlalchemy import func, cast, String
    counts = db2.query(
        func.substr(cast(AuditLog.created_at, String), 1, 10), func.count()
    ).group_by(
        func.substr(cast(AuditLog.created_at, String), 1, 10)
    ).order_by(
        func.substr(cast(AuditLog.created_at, String), 1, 10).desc()
    ).limit(5).all()

    print(f"\nSuccessfully seeded {len(sample_events)} audit log records across 30 days!")
    print("\nTop 5 days by record count:")
    for day, cnt in counts:
        print(f"  {day}: {cnt} records")
    db2.close()


if __name__ == "__main__":
    seed_30_days_audit_logs()
