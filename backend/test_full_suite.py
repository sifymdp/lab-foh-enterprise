"""
Comprehensive test script for FOH Multi-Tenant RBAC, 7 Roles, Billing, Payments,
Shifts, Approvals, Revenue, and Audit Logs.
"""
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine, migrate_schema
from app.main import app
from app.models import Bill, CashierShift, DiningSession, Order, Payment, RefundRequest, Table, User
from app.seed import seed_database
from app.config import settings

def run_tests():
    print("=== STEP 1: INITIALIZE DB & RUN MIGRATIONS ===")
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    db = SessionLocal()
    seed_database(db)

    
    # Clean transactional tables for test independence
    from app.models import OrderItem
    db.query(Payment).delete()
    db.query(Bill).delete()
    db.query(OrderItem).delete()
    db.query(Order).delete()
    db.query(DiningSession).delete()
    db.query(CashierShift).delete()
    db.query(Table).update({Table.status: "AVAILABLE"})
    
    db.commit()
    db.close()
    print("[OK] Schema migrated and database seeded successfully.")



    client = TestClient(app)

    print("\n=== STEP 2: TEST ALL 6 DEMO USER LOGINS ===")
    roles_and_users = [
        ("OWNER",   "owner@gmail.com",   settings.owner_password),
        ("MANAGER", "manager@gmail.com", settings.manager_password),
        ("HOST",    "host@gmail.com",    settings.host_password),
        ("CASHIER", "cashier@gmail.com", settings.cashier_password),
        ("WAITER",  "waiter@gmail.com",  settings.waiter_password),
        ("CHEF",    "chef@gmail.com",    settings.chef_password),
    ]


    tokens = {}
    for role, email, password in roles_and_users:
        res = client.post("/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, f"Login failed for {email}: {res.text}"
        data = res.json()
        token = data.get("accessToken") or data.get("access_token")
        assert token is not None, f"No access token in response: {data}"
        assert data["user"]["role"] == role
        tokens[role] = token
        print(f"[OK] {role} login verified ({email})")


    # Helper headers
    def auth_header(role):
        return {"Authorization": f"Bearer {tokens[role]}"}

    print("\n=== STEP 3: TEST PERMISSION & ACCESS RESTRICTIONS ===")
    # 3.1 Host CANNOT access billing
    res = client.get("/billing/bills", headers=auth_header("HOST"))
    assert res.status_code == 403, f"Expected 403 for HOST on /billing/bills, got {res.status_code}"
    print("[OK] Host forbidden from billing endpoints (403 verified).")

    # 3.2 Waiter CANNOT access revenue
    res = client.get("/revenue/daily", headers=auth_header("WAITER"))
    assert res.status_code == 403, f"Expected 403 for WAITER on /revenue/daily, got {res.status_code}"
    print("[OK] Waiter forbidden from revenue reporting (403 verified).")

    # 3.3 Chef CANNOT access billing
    res = client.get("/billing/bills", headers=auth_header("CHEF"))
    assert res.status_code == 403, f"Expected 403 for CHEF on /billing/bills, got {res.status_code}"
    print("[OK] Chef forbidden from billing (403 verified).")


    print("\n=== STEP 4: TEST CASHIER SHIFT LIFECYCLE ===")
    # 4.1 Cashier starts shift
    shift_res = client.post("/cashier-shifts/start", json={"opening_cash": 1000.0, "notes": "Shift 1 float"}, headers=auth_header("CASHIER"))
    # Handle if shift already open
    if shift_res.status_code == 409:
        cur_res = client.get("/cashier-shifts/current", headers=auth_header("CASHIER"))
        shift_id = cur_res.json()["id"]
    else:
        assert shift_res.status_code == 200
        shift_id = shift_res.json()["id"]
    print(f"[OK] Cashier shift started (Shift ID: {shift_id}).")

    print("\n=== STEP 5: TEST DINING SESSION -> BILLING -> PAYMENT FLOW ===")
    # 5.1 Host seats a guest at an available table
    active_table_ids = [s.table_id for s in db.query(DiningSession).filter(DiningSession.status.in_(["ACTIVE", "SEATED", "BILLING", "ORDERING"])).all()]
    table = db.query(Table).filter(Table.status == "AVAILABLE", ~Table.id.in_(active_table_ids)).first()
    assert table is not None, "No available unseated table found in DB"
    test_table_id = table.id


    seat_res = client.post("/sessions/seat", json={"table_id": test_table_id, "party_size": 2, "guest_name": "Sharma"}, headers=auth_header("HOST"))
    assert seat_res.status_code in (200, 201), f"Seat failed: {seat_res.text}"
    session_id = seat_res.json()["id"]
    print(f"[OK] Host seated table {table.number} (Session ID: {session_id}).")

    # 5.2 Waiter places an order
    from app.models import MenuItem
    menu_items = db.query(MenuItem).limit(3).all()
    assert len(menu_items) >= 3, "Not enough menu items in DB"

    order_res = client.post("/orders", json={
        "session_id": session_id,
        "table_id": test_table_id,
        "items": [
            {"menu_item_id": menu_items[0].id, "quantity": 2},
            {"menu_item_id": menu_items[1].id, "quantity": 1},
            {"menu_item_id": menu_items[2].id, "quantity": 2},
        ]
    }, headers=auth_header("WAITER"))
    assert order_res.status_code == 200, f"Place order failed: {order_res.text}"
    order_id = order_res.json()["id"]
    print(f"[OK] Waiter placed order with 3 items (Order ID: {order_id}).")


    # 5.3 Chef transitions order: RECEIVED -> CONFIRMED -> PREPARING -> READY -> SERVED
    res = client.patch(f"/orders/{order_id}/status", json={"status": "CONFIRMED"}, headers=auth_header("CHEF"))
    assert res.status_code == 200 and res.json()["status"] == "CONFIRMED"
    res = client.patch(f"/orders/{order_id}/status", json={"status": "PREPARING"}, headers=auth_header("CHEF"))
    assert res.status_code == 200 and res.json()["status"] == "PREPARING"
    res = client.patch(f"/orders/{order_id}/status", json={"status": "READY"}, headers=auth_header("CHEF"))
    assert res.status_code == 200 and res.json()["status"] == "READY"
    res = client.patch(f"/orders/{order_id}/status", json={"status": "SERVED"}, headers=auth_header("CHEF"))
    assert res.status_code == 200 and res.json()["status"] == "SERVED"
    print("[OK] Chef updated kitchen order lifecycle to SERVED.")

    # 5.4 Cashier generates itemized bill
    bill_res = client.post("/billing/bills", json={"session_id": session_id}, headers=auth_header("CASHIER"))
    assert bill_res.status_code == 201, f"Create bill failed: {bill_res.text}"
    bill_data = bill_res.json()
    bill_id = bill_data["id"]
    bill_num = bill_data.get("billNumber") or bill_data.get("bill_number") or bill_id[:6]
    print(f"[OK] Cashier created itemized Bill #{bill_num} for Subtotal Rs {bill_data['subtotal']}.")


    # 5.5 Cashier applies 5% discount
    disc_res = client.post(f"/billing/bills/{bill_id}/discount", json={"percent": 5.0, "reason": "Happy hour"}, headers=auth_header("CASHIER"))
    assert disc_res.status_code == 200, f"Discount failed: {disc_res.text}"
    print(f"[OK] Cashier applied 5% discount (Approved directly within role limit).")

    # 5.6 Cashier gets bill details with computed grand total
    detail_res = client.get(f"/billing/bills/{bill_id}", headers=auth_header("CASHIER"))
    assert detail_res.status_code == 200
    grand_total = detail_res.json()["total"]
    print(f"[OK] Bill grand total computed: Rs {grand_total}")

    # 5.7 Cashier processes payment via UPI
    pay_res = client.post(f"/billing/bills/{bill_id}/pay", json={
        "method": "UPI",
        "amount": grand_total,
        "transaction_id": "TXN123456789",
        "shift_id": shift_id
    }, headers=auth_header("CASHIER"))
    assert pay_res.status_code == 200, f"Payment failed: {pay_res.text}"
    pay_data = pay_res.json()
    payment_id = pay_data["payment_id"]
    assert pay_data["payment_status"] == "SUCCESS"
    print(f"[OK] Cashier processed Rs {grand_total} via UPI with Safe Ref {pay_data['transaction_id']}.")

    # 5.8 Prevent duplicate payment
    dup_res = client.post(f"/billing/bills/{bill_id}/pay", json={
        "method": "UPI",
        "amount": grand_total,
        "transaction_id": "TXN999999999",
        "shift_id": shift_id
    }, headers=auth_header("CASHIER"))
    assert dup_res.status_code == 409, f"Expected duplicate payment rejection (409), got {dup_res.status_code}"
    print("[OK] Duplicate payment prevented (409 Conflict).")

    print("\n=== STEP 6: TEST REFUND & APPROVAL WORKFLOW ===")
    # 6.1 Cashier requests refund
    ref_req_res = client.post("/refunds", json={
        "bill_id": bill_id,
        "payment_id": payment_id,
        "request_type": "REFUND",
        "amount": grand_total,
        "reason": "Customer dissatisfied with dessert"
    }, headers=auth_header("CASHIER"))
    assert ref_req_res.status_code == 201, f"Refund request failed: {ref_req_res.text}"
    req_id = ref_req_res.json()["id"]
    print(f"[OK] Cashier submitted refund request (Request ID: {req_id}).")

    # 6.2 Cashier CANNOT approve own refund
    own_app_res = client.patch(f"/refunds/{req_id}/approve", json={"resolution_notes": "Self approval"}, headers=auth_header("CASHIER"))
    assert own_app_res.status_code == 403, f"Expected 403 on self-approval, got {own_app_res.status_code}"
    print("[OK] Cashier prevented from approving own refund (403 Forbidden).")

    # 6.3 Manager approves refund
    mgr_app_res = client.patch(f"/refunds/{req_id}/approve", json={"resolution_notes": "Approved by branch manager"}, headers=auth_header("MANAGER"))
    assert mgr_app_res.status_code == 200, f"Manager approval failed: {mgr_app_res.text}"
    assert mgr_app_res.json()["status"] == "APPROVED"
    print("[OK] Manager approved refund request.")

    print("\n=== STEP 7: TEST CASHIER SHIFT RECONCILIATION ===")
    # 7.1 Cashier ends shift with declared cash
    end_res = client.patch(f"/cashier-shifts/{shift_id}/end", json={
        "closing_cash": 1000.0,
        "actual_cash": 1000.0,
        "notes": "Day shift closed smoothly"
    }, headers=auth_header("CASHIER"))
    assert end_res.status_code == 200, f"End shift failed: {end_res.text}"
    shift_data = end_res.json()
    assert shift_data["status"] == "CLOSED"
    print(f"[OK] Cashier shift closed and reconciled (Difference: Rs {shift_data['difference']}).")

    print("\n=== STEP 8: TEST REVENUE SUMMARIES & AUDIT LOGS ===")
    # 8.1 Daily Revenue
    rev_res = client.get("/revenue/daily", headers=auth_header("OWNER"))
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["total_bills"] >= 1
    print(f"[OK] Owner Daily Revenue Summary verified (Total Bills: {rev_data['total_bills']}).")

    # 8.2 Payment Methods summary
    pm_res = client.get("/revenue/payment-methods", headers=auth_header("OWNER"))
    assert pm_res.status_code == 200
    pm_data = pm_res.json()
    assert "upi" in pm_data and "cash" in pm_data
    print(f"[OK] Payment Methods Summary verified: UPI Rs {pm_data['upi']}, Cash Rs {pm_data['cash']}.")

    # 8.3 Audit Logs
    audit_res = client.get("/audit-logs", headers=auth_header("OWNER"))
    assert audit_res.status_code == 200
    audit_logs = audit_res.json()
    assert len(audit_logs) >= 5
    print(f"[OK] Audit Trail verified ({len(audit_logs)} log records recorded).")


    # Re-seed database so demo environment is preserved with fresh data
    db = SessionLocal()
    try:
        seed_database(db)
        print("[OK] Demo database successfully re-seeded with live data.")
    finally:
        db.close()

    print("\n========================================================")
    print("ALL TEST SUITES PASSED WITH ZERO ERRORS!")
    print("========================================================")

if __name__ == "__main__":
    run_tests()
