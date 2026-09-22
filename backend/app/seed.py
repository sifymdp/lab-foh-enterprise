"""
Database seeder — ensures the standard 10-table layout, 6 demo staff users,
an active cashier shift, and rich sample dining sessions, orders, bills, and payments.
"""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.core.ids import new_id
from app.core.security import hash_password
from app.models import (
    AuditLog,
    Bill,
    Branch,
    CashierShift,
    DiningSession,
    Floor,
    MenuItem,
    Organization,
    Order,
    OrderItem,
    Payment,
    Reservation,
    StatusHistory,
    Table,
    TableQRCode,
    User,
    Role,
    RolePermission,
)
from app.core.permissions import ROLE_PERMISSIONS
from app.seed_data import DEMO_MENU_ITEMS, DEMO_PASSWORD_BY_ROLE, DEMO_USERS, INITIAL_FLOOR
from app.services.billing_service import calculate_bill


def _password_for_role(role: str) -> str:
    key = DEMO_PASSWORD_BY_ROLE.get(role.upper(), "cashier_password")
    return getattr(settings, key, "Demo@1234")


def seed_database(db: Session) -> None:
    now = datetime.now(timezone.utc)

    # ── 1. Organisation ──────────────────────────────────────────────────────
    organization = db.get(Organization, "org-demo")
    if not organization:
        organization = Organization(
            id="org-demo",
            name="FOH Demo Restaurant",
            email="demo@foh.local",
            timezone="Asia/Kolkata",
            currency="INR",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(organization)
        db.flush()

    # ── 2. Branch ────────────────────────────────────────────────────────────
    branch = db.get(Branch, "branch-demo")
    if not branch:
        branch = Branch(
            id="branch-demo",
            organization_id=organization.id,
            name="Main Branch",
            timezone="Asia/Kolkata",
            currency="INR",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(branch)
        db.flush()

    # ── 3. Seed default roles and permissions in DB ─────────────────────────
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.core.permissions import ROLE_PERMISSIONS, ALL_PERMISSIONS

    static_roles = ["OWNER", "MANAGER", "HOST", "CASHIER", "WAITER", "CHEF"]
    for sr in static_roles:
        existing_role = db.query(Role).filter(
            Role.name == sr, 
            Role.tenant_id == organization.id
        ).first()
        if not existing_role:
            role_id = f"role-seeded-{sr.lower()}"
            db_role = Role(
                id=role_id,
                tenant_id=organization.id,
                name=sr,
                is_custom=False,
                created_at=now
            )
            db.add(db_role)
            db.flush()

            perms = ROLE_PERMISSIONS.get(sr, set())
            if sr == "OWNER":
                perms = ALL_PERMISSIONS
            for p in perms:
                db.add(RolePermission(
                    id=new_id(),
                    role_id=role_id,
                    permission=p,
                    tenant_id=organization.id
                ))
            db.flush()

    # Clean up COOK if present in DB
    from sqlalchemy import func
    cook_role = db.query(Role).filter(func.upper(Role.name) == "COOK").first()
    if cook_role:
        db.query(RolePermission).filter(RolePermission.role_id == cook_role.id).delete()
        db.delete(cook_role)
        db.flush()
    for u in db.query(User).filter(func.upper(User.role) == "COOK").all():
        u.role = "CHEF"
    db.flush()

    # ── 4. Seed the Demo Users ─────────────────────────────────────────────
    for u in DEMO_USERS:
        existing = db.query(User).filter(User.email == u["email"]).first()
        if not existing:
            db.add(
                User(
                    id=u["id"],
                    name=u["name"],
                    email=u["email"],
                    role=u["role"],
                    password_hash=hash_password(_password_for_role(u["role"])),
                    is_active=True,
                    tenant_id=organization.id,
                    branch_id=branch.id,
                    created_at=now,
                )
            )
        else:
            existing.role = u["role"]
            existing.tenant_id = organization.id
            existing.branch_id = branch.id
            existing.password_hash = hash_password(_password_for_role(u["role"]))

    # ── 4b. Seed Roles & Default Permissions ─────────────────────────────────
    standard_roles = ["MANAGER", "HOST", "CASHIER", "WAITER", "CHEF"]
    for r_name in standard_roles:
        db_role = db.query(Role).filter(
            func.upper(Role.name) == r_name,
            Role.tenant_id == organization.id,
        ).first()
        if not db_role:
            db_role = Role(
                id=f"role-seeded-{r_name.lower()}",
                name=r_name,
                is_custom=False,
                tenant_id=organization.id,
                created_at=now,
            )
            db.add(db_role)
            db.flush()

        # Seed role permissions from ROLE_PERMISSIONS catalogue if not already populated
        existing_perms = {
            rp.permission
            for rp in db.query(RolePermission).filter(RolePermission.role_id == db_role.id).all()
        }
        catalog_perms = ROLE_PERMISSIONS.get(r_name, set())
        for perm in catalog_perms:
            if perm not in existing_perms:
                db.add(
                    RolePermission(
                        id=new_id(),
                        role_id=db_role.id,
                        permission=perm,
                        tenant_id=organization.id,
                    )
                )
    db.flush()

    # ── 5. Seed Menu Items ───────────────────────────────────────────────────
    for item in DEMO_MENU_ITEMS:
        existing_item = db.query(MenuItem).filter(MenuItem.name == item["name"]).first()
        if not existing_item:
            db.add(MenuItem(**item, id=new_id()))
        else:
            existing_item.price = item["price"]
            existing_item.description = item["description"]
            existing_item.category = item["category"]
            existing_item.available = item.get("available", True)
    db.flush()

    # ── 6. Seed 10-Table Floor Layout ─────────────────────────────────────────
    floor = db.get(Floor, INITIAL_FLOOR["id"])
    if not floor:
        floor = Floor(
            id=INITIAL_FLOOR["id"],
            name=INITIAL_FLOOR["name"],
            width=INITIAL_FLOOR["width"],
            height=INITIAL_FLOOR["height"],
            sections=INITIAL_FLOOR["sections"],
            labels=INITIAL_FLOOR["labels"],
            tenant_id=organization.id,
            branch_id=branch.id,
        )
        db.add(floor)
        db.flush()

    # Ensure all 10 tables exist and match standard IDs t-1 through t-10
    for t in INITIAL_FLOOR["tables"]:
        table = db.get(Table, t["id"])
        roi = t.get("roiCoords")
        if not table:
            table = Table(
                id=t["id"],
                floor_id=floor.id,
                section_id=t["sectionId"],
                number=t["number"],
                capacity=t["capacity"],
                type=t["type"],
                shape=t["shape"],
                status=t["status"],
                x=t["x"],
                y=t["y"],
                width=t["width"],
                height=t["height"],
                rotation=t["rotation"],
                camera_url=t.get("cameraUrl"),
                roi_coords=json.dumps(roi) if roi else None,
                tenant_id=organization.id,
                branch_id=branch.id,
            )
            db.add(table)
            db.add(TableQRCode(id=new_id(), table_id=t["id"], token=new_id(), is_active=True))
        else:
            table.number = t["number"]
            table.capacity = t["capacity"]
            table.type = t["type"]
            table.shape = t["shape"]
            table.x = t["x"]
            table.y = t["y"]
            table.width = t["width"]
            table.height = t["height"]
            table.tenant_id = organization.id
            table.branch_id = branch.id

    db.flush()

    # ── 7. Seed Active Cashier Shift for cashier@gmail.com ─────────────────────
    cashier_user = db.query(User).filter(User.role == "CASHIER").first()
    if cashier_user:
        active_shift = db.get(CashierShift, "shift-demo-active")
        if not active_shift:
            active_shift = CashierShift(
                id="shift-demo-active",
                cashier_id=cashier_user.id,
                tenant_id=organization.id,
                branch_id=branch.id,
                opening_cash=Decimal("2000.00"),
                cash_sales=Decimal("1450.00"),
                card_sales=Decimal("2850.00"),
                upi_sales=Decimal("1575.00"),
                qr_sales=Decimal("920.00"),
                online_sales=Decimal("400.00"),
                refund_total=Decimal("0.00"),
                discount_total=Decimal("150.00"),
                opened_at=now - timedelta(hours=3),
                status="OPEN",
                notes="Morning active shift (Float Rs. 2,000)",
            )
            db.add(active_shift)
            db.flush()
        else:
            active_shift.status = "OPEN"
            active_shift.closed_at = None
            active_shift.opened_at = now - timedelta(hours=3)
            active_shift.opening_cash = Decimal("2000.00")
            active_shift.cash_sales = Decimal("1450.00")
            active_shift.card_sales = Decimal("2850.00")
            active_shift.upi_sales = Decimal("1575.00")
            active_shift.qr_sales = Decimal("920.00")
            active_shift.online_sales = Decimal("400.00")
            db.flush()


    # ── 8. Seed Sample Dining Sessions, Orders, and Bills ─────────────────────
    menu_map = {m.name: m for m in db.query(MenuItem).all()}

    # Table 1 (t-1): Active dining session with placed order and open bill
    t1 = db.get(Table, "t-1")
    if t1:
        t1.status = "ACTIVE"
        s1 = db.get(DiningSession, "session-demo-t1")
        if not s1:
            s1 = DiningSession(
                id="session-demo-t1",
                table_id="t-1",
                guest_name="Rahul Sharma",
                party_size=2,
                seated_at=now - timedelta(minutes=45),
                status="ACTIVE",
                tenant_id=organization.id,
                branch_id=branch.id,
            )
            db.add(s1)
            db.flush()
        else:
            s1.status = "ACTIVE"

        o1 = db.get(Order, "order-demo-t1")
        if not o1:
            o1 = Order(
                id="order-demo-t1",
                session_id=s1.id,
                table_id="t-1",
                placed_at=now - timedelta(minutes=40),
                status="CONFIRMED",
                tenant_id=organization.id,
                branch_id=branch.id,
            )
            db.add(o1)
            db.flush()
        
        # Clear stale items and re-add authentic menu items
        db.query(OrderItem).filter(OrderItem.order_id == o1.id).delete()
        item_dosa = menu_map.get("Ghee Roast Masala Dosa")
        item_idlis = menu_map.get("Mysore Podi Mini Idlis & Vada")
        if item_dosa:
            db.add(OrderItem(id=new_id(), order_id=o1.id, menu_item_id=item_dosa.id, item_name=item_dosa.name, quantity=2, unit_price=item_dosa.price))
        if item_idlis:
            db.add(OrderItem(id=new_id(), order_id=o1.id, menu_item_id=item_idlis.id, item_name=item_idlis.name, quantity=1, unit_price=item_idlis.price))
        db.flush()

        b1 = db.get(Bill, "bill-demo-t1")
        if not b1:
            b1 = Bill(
                id="bill-demo-t1",
                bill_number="B1001",
                session_id=s1.id,
                subtotal=Decimal("0.00"),
                discount_amount=Decimal("0.00"),
                service_charge_amount=Decimal("0.00"),
                tax_amount=Decimal("0.00"),
                total=Decimal("0.00"),
                status="OPEN",
                bill_status="OPEN",
                generated_at=now - timedelta(minutes=10),
                created_by=cashier_user.id if cashier_user else None,
                tenant_id=organization.id,
                branch_id=branch.id,
            )
            db.add(b1)
            db.flush()
        else:
            b1.status = "OPEN"
            b1.bill_status = "OPEN"
            b1.discount_amount = Decimal("0.00")
            b1.discount_reason = None
        calculate_bill(db, b1)

    # Table 2 (t-2): Session in BILLING state with READY_FOR_PAYMENT bill
    t2 = db.get(Table, "t-2")
    if t2:
        t2.status = "BILLING"
        s2 = db.get(DiningSession, "session-demo-t2")
        if not s2:
            s2 = DiningSession(
                id="session-demo-t2",
                table_id="t-2",
                guest_name="Priya Patel",
                party_size=4,
                seated_at=now - timedelta(hours=1, minutes=20),
                status="BILLING",
                tenant_id=organization.id,
                branch_id=branch.id,
            )
            db.add(s2)
            db.flush()
        else:
            s2.status = "BILLING"

        o2 = db.get(Order, "order-demo-t2")
        if not o2:
            o2 = Order(
                id="order-demo-t2",
                session_id=s2.id,
                table_id="t-2",
                placed_at=now - timedelta(hours=1),
                status="SERVED",
                tenant_id=organization.id,
                branch_id=branch.id,
            )
            db.add(o2)
            db.flush()

        db.query(OrderItem).filter(OrderItem.order_id == o2.id).delete()
        item_biryani = menu_map.get("Awadhi Gosht Dum Biryani")
        item_butter_chicken = menu_map.get("Murgh Makhani (Butter Chicken)")
        item_dal = menu_map.get("Dal Bukhara / 24-Hr Dal Makhani")

        if item_biryani:
            db.add(OrderItem(id=new_id(), order_id=o2.id, menu_item_id=item_biryani.id, item_name=item_biryani.name, quantity=2, unit_price=item_biryani.price))
        if item_butter_chicken:
            db.add(OrderItem(id=new_id(), order_id=o2.id, menu_item_id=item_butter_chicken.id, item_name=item_butter_chicken.name, quantity=1, unit_price=item_butter_chicken.price))
        if item_dal:
            db.add(OrderItem(id=new_id(), order_id=o2.id, menu_item_id=item_dal.id, item_name=item_dal.name, quantity=1, unit_price=item_dal.price))
        db.flush()

        b2 = db.get(Bill, "bill-demo-t2")
        if not b2:
            b2 = Bill(
                id="bill-demo-t2",
                bill_number="B1002",
                session_id=s2.id,
                subtotal=Decimal("0.00"),
                discount_amount=Decimal("116.00"),
                discount_reason="Regular guest discount (5%)",
                total=Decimal("0.00"),
                status="READY_FOR_PAYMENT",
                bill_status="READY_FOR_PAYMENT",
                generated_at=now - timedelta(minutes=5),
                created_by=cashier_user.id if cashier_user else None,
                tenant_id=organization.id,
                branch_id=branch.id,
            )
            db.add(b2)
            db.flush()
        else:
            b2.status = "READY_FOR_PAYMENT"
            b2.bill_status = "READY_FOR_PAYMENT"
            b2.discount_amount = Decimal("116.00")
            b2.discount_reason = "Regular guest discount (5%)"
        calculate_bill(db, b2)

    # Table 5 (t-5): Seated session with food being prepared in kitchen
    t5 = db.get(Table, "t-5")
    if t5:
        t5.status = "SEATED"
        s5 = db.get(DiningSession, "session-demo-t5")
        if not s5:
            s5 = DiningSession(
                id="session-demo-t5",
                table_id="t-5",
                guest_name="Ananya Roy",
                party_size=3,
                seated_at=now - timedelta(minutes=25),
                status="SEATED",
                tenant_id=organization.id,
                branch_id=branch.id,
            )
            db.add(s5)
            db.flush()
        else:
            s5.status = "SEATED"

        o5 = db.get(Order, "order-demo-t5")
        if not o5:
            o5 = Order(
                id="order-demo-t5",
                session_id=s5.id,
                table_id="t-5",
                placed_at=now - timedelta(minutes=20),
                status="PREPARING",
                tenant_id=organization.id,
                branch_id=branch.id,
            )
            db.add(o5)
            db.flush()

        db.query(OrderItem).filter(OrderItem.order_id == o5.id).delete()
        item_dimsum = menu_map.get("Truffle Edamame Dim Sum (4pcs)")
        item_noodles = menu_map.get("Hakka Chilli Garlic Noodles")
        if item_dimsum:
            db.add(OrderItem(id=new_id(), order_id=o5.id, menu_item_id=item_dimsum.id, item_name=item_dimsum.name, quantity=2, unit_price=item_dimsum.price))
        if item_noodles:
            db.add(OrderItem(id=new_id(), order_id=o5.id, menu_item_id=item_noodles.id, item_name=item_noodles.name, quantity=2, unit_price=item_noodles.price))
        db.flush()

    # Table 3 (t-3): Upcoming Reservation
    t3 = db.get(Table, "t-3")
    if t3:
        t3.status = "RESERVED"
        res3 = db.get(Reservation, "res-demo-t3")
        if not res3:
            res3 = Reservation(
                id="res-demo-t3",
                table_id="t-3",
                guest_name="Vikram Malhotra",
                party_size=6,
                reserved_for=now + timedelta(hours=2),
                reserved_until=now + timedelta(hours=3),
                status="PENDING",
                notes="Birthday dinner celebration",
                tenant_id=organization.id,
                branch_id=branch.id,
            )
            db.add(res3)

    # ── 9. Completed Sample Paid Bills & Payments for Today ──────────────────
    today_payments_data = [
        ("pay-today-cash", "bill-today-cash", "CASH", Decimal("1450.00"), "TXN-CASH-TODAY-01", timedelta(hours=2, minutes=30), "Table 7 Guest"),
        ("pay-today-card", "bill-today-card", "CARD", Decimal("2850.00"), "TXN-CARD-TODAY-02", timedelta(hours=2, minutes=10), "Vikram Singhania"),
        ("pay-today-upi",  "bill-today-upi",  "UPI",  Decimal("1575.00"), "UPI/983728192837",    timedelta(hours=1, minutes=45), "Amit Verma (VIP)"),
        ("pay-today-qr",   "bill-today-qr",   "QR",   Decimal("920.00"),  "QR/ICICI-8827162",    timedelta(hours=1, minutes=15), "Rohan Mehra"),
        ("pay-today-online","bill-today-online","ONLINE",Decimal("400.00"), "PG-RAZOR-991823",   timedelta(minutes=30),          "Sneha Rao"),
    ]

    for pid, bid, method, amount, txid, dt, gname in today_payments_data:
        sess_id = f"sess-{bid}"
        s_item = db.get(DiningSession, sess_id)
        if not s_item:
            s_item = DiningSession(
                id=sess_id,
                table_id="t-6",
                guest_name=gname,
                party_size=2,
                seated_at=now - dt - timedelta(hours=1),
                closed_at=now - dt,
                status="PAID",
                tenant_id=organization.id,
                branch_id=branch.id,
            )
            db.add(s_item)
            db.flush()
        else:
            s_item.closed_at = now - dt

        b_item = db.get(Bill, bid)
        subtotal_val = round(float(amount) / 1.15, 2)
        tax_val = round(subtotal_val * 0.05, 2)
        svc_val = round(float(amount) - subtotal_val - tax_val, 2)

        if not b_item:
            b_item = Bill(
                id=bid,
                bill_number=f"B{bid[-4:].upper()}",
                session_id=sess_id,
                subtotal=Decimal(str(subtotal_val)),
                discount_amount=Decimal("0.00"),
                service_charge_amount=Decimal(str(svc_val)),
                tax_amount=Decimal(str(tax_val)),
                total=amount,
                status="PAID",
                bill_status="PAID",
                generated_at=now - dt - timedelta(minutes=10),
                paid_at=now - dt,
                created_by=cashier_user.id if cashier_user else None,
                tenant_id=organization.id,
                branch_id=branch.id,
            )
            db.add(b_item)
            db.flush()
        else:
            b_item.status = "PAID"
            b_item.bill_status = "PAID"
            b_item.paid_at = now - dt
            b_item.generated_at = now - dt - timedelta(minutes=10)

        p_item = db.get(Payment, pid)
        if not p_item:
            p_item = Payment(
                id=pid,
                bill_id=bid,
                method=method,
                amount=amount,
                transaction_id=txid,
                payment_status="SUCCESS",
                created_by=cashier_user.id if cashier_user else None,
                paid_at=now - dt,
                completed_at=now - dt,
                shift_id="shift-demo-active",
                tenant_id=organization.id,
                branch_id=branch.id,
            )
            db.add(p_item)
        else:
            p_item.paid_at = now - dt
            p_item.completed_at = now - dt
            p_item.shift_id = "shift-demo-active"

    # ── 10. Rich Historical Revenue Sample Data ──────────────────────────────
    from random import Random
    rnd = Random(42)

    historical_dates = [
        now - timedelta(days=1, hours=2),
        now - timedelta(days=1, hours=6),
        now - timedelta(days=2, hours=1),
        now - timedelta(days=2, hours=4),
        now - timedelta(days=3, hours=3),
    ]

    c_id = cashier_user.id if cashier_user else "u-cashier"
    m_user = db.query(User).filter(User.role == "MANAGER").first()
    m_id = m_user.id if m_user else "u-manager"

    for i, shift_date in enumerate(historical_dates):
        sh_id = f"shift-hist-{i}"
        if not db.get(CashierShift, sh_id):
            hist_shift = CashierShift(
                id=sh_id,
                cashier_id=c_id if i % 2 == 0 else m_id,
                tenant_id=organization.id,
                branch_id=branch.id,
                opening_cash=Decimal("2000.00"),
                closing_cash=Decimal("2800.00"),
                cash_sales=Decimal("800.00") if i % 2 == 0 else Decimal("400.00"),
                card_sales=Decimal("1200.00"),
                upi_sales=Decimal("1500.00"),
                qr_sales=Decimal("600.00"),
                online_sales=Decimal("300.00"),
                refund_total=Decimal("150.00") if i == 1 else Decimal("0.00"),
                discount_total=Decimal("250.00"),
                expected_cash=Decimal("2800.00") if i % 2 == 0 else Decimal("2400.00"),
                actual_cash=Decimal("2800.00") if i % 2 == 0 else Decimal("2395.00"),
                difference=Decimal("0.00") if i % 2 == 0 else Decimal("-5.00"),
                opened_at=shift_date - timedelta(hours=8),
                closed_at=shift_date,
                status="CLOSED",
                notes=f"Historical shift {i} closed successfully.",
            )
            db.add(hist_shift)
            db.flush()

            methods_list = ["CASH", "CARD", "UPI", "QR", "ONLINE"]
            for j in range(3):
                sess_id = f"sess-hist-{i}-{j}"
                hist_sess = DiningSession(
                    id=sess_id,
                    table_id=f"t-{rnd.randint(1, 10)}",
                    guest_name=f"Guest {i}-{j}",
                    party_size=rnd.randint(2, 6),
                    seated_at=shift_date - timedelta(hours=6 - j),
                    closed_at=shift_date - timedelta(hours=5 - j),
                    status="PAID",
                    tenant_id=organization.id,
                    branch_id=branch.id,
                )
                db.add(hist_sess)
                db.flush()

                bill_val = rnd.randint(500, 2500)
                disc_val = 0.0
                if rnd.random() < 0.3:
                    disc_val = round(bill_val * 0.1, 2)

                bill_id = f"bill-hist-{i}-{j}"
                hist_bill = Bill(
                    id=bill_id,
                    bill_number=f"B{2000 + i*10 + j}",
                    session_id=sess_id,
                    subtotal=Decimal(str(bill_val)),
                    discount_amount=Decimal(str(disc_val)),
                    service_charge_amount=Decimal(str(round(bill_val * 0.05, 2))),
                    tax_amount=Decimal(str(round(bill_val * 0.05, 2))),
                    total=Decimal(str(round(bill_val - disc_val + bill_val * 0.1, 2))),
                    status="PAID" if j != 2 or i != 1 else "REFUNDED",
                    bill_status="PAID" if j != 2 or i != 1 else "REFUNDED",
                    generated_at=shift_date - timedelta(hours=5 - j),
                    paid_at=shift_date - timedelta(hours=5 - j) if (j != 2 or i != 1) else None,
                    created_by=c_id if i % 2 == 0 else m_id,
                    tenant_id=organization.id,
                    branch_id=branch.id,
                )
                db.add(hist_bill)
                db.flush()

                m_used = methods_list[(i + j) % len(methods_list)]
                hist_pay = Payment(
                    id=f"pay-hist-{i}-{j}",
                    bill_id=bill_id,
                    method=m_used,
                    amount=hist_bill.total,
                    transaction_id=f"TXN-{m_used}-{i}{j}9837",
                    payment_status="SUCCESS",
                    created_by=c_id if i % 2 == 0 else m_id,
                    paid_at=shift_date - timedelta(hours=5 - j),
                    completed_at=shift_date - timedelta(hours=5 - j),
                    shift_id=sh_id,
                    tenant_id=organization.id,
                    branch_id=branch.id,
                )
                db.add(hist_pay)

    db.commit()



def empty_floor_layout(floor: Floor) -> None:
    w, h = floor.width, floor.height
    floor.sections = []
    floor.labels = [
        {
            "id": f"lbl-{new_id()}-ent",
            "kind": "ENTRANCE",
            "text": "Entrance",
            "bounds": {"x": w / 2 - 100, "y": h - 56, "width": 200, "height": 44},
        },
        {
            "id": f"lbl-{new_id()}-kit",
            "kind": "KITCHEN",
            "text": "Kitchen",
            "bounds": {"x": w - 140, "y": 12, "width": 120, "height": 44},
        },
    ]


if __name__ == "__main__":
    from app.database import SessionLocal
    with SessionLocal() as db:
        seed_database(db)
        print("Database seeded successfully!")

