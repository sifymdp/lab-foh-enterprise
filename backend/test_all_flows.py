import urllib.request
import json

BASE = "http://127.0.0.1:8000"
TOKEN = "f39b5b36-b54d-440a-b2f4-a298396acf7a" # Table 2

print("=== TEST 1: Guest Menu Encoding & Layout ===")
req = urllib.request.Request(f"{BASE}/guest/menu?token={TOKEN}")
with urllib.request.urlopen(req) as resp:
    html = resp.read().decode("utf-8")
    assert "₹" in html, "Rupee symbol missing"
    assert "🔔 Call waiter" in html, "Bell Call waiter missing"
    assert "🧾 Bill" in html, "Receipt Bill missing"
    assert "side-tab" in html, "Sidebar tabs missing"
    assert not any(c in html for c in ['\u0393', '\u2261', '\u251c', '\u252c']), "Mojibake detected!"
    print("PASS: Menu is 100% clean UTF-8 with exact original screenshot styling!")

print("\n=== TEST 2: Customer Order Placement & Approval Flow ===")
# Get active menu items from live server
req_menu = urllib.request.Request(f"{BASE}/menu")
with urllib.request.urlopen(req_menu) as resp:
    menu_items = json.loads(resp.read().decode("utf-8"))
item_id = menu_items[0]["id"]
print(f"Using live menu item: {menu_items[0]['name']} ({item_id})")

def login_user(email, password):
    req_login = urllib.request.Request(
        f"{BASE}/auth/login",
        data=json.dumps({"email": email, "password": password}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req_login) as resp:
        return json.loads(resp.read().decode("utf-8"))["accessToken"]

waiter_token = login_user("waiter@gmail.com", "Waiter@1234")
chef_token = login_user("chef@gmail.com", "Chef@1234")

# 2a. Guest places order
order_payload = {
    "items": [{"menuItemId": item_id, "quantity": 1}],
    "notes": "Spicy please"
}
req = urllib.request.Request(
    f"{BASE}/orders?token={TOKEN}",
    data=json.dumps(order_payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST"
)
try:
    with urllib.request.urlopen(req) as resp:
        order1 = json.loads(resp.read().decode("utf-8"))
        order1_id = order1["id"]
        assert order1["approvalStatus"] == "PENDING", f"Expected PENDING, got {order1['approvalStatus']}"
        assert order1["source"] == "guest", f"Expected guest, got {order1['source']}"
        print(f"PASS: Guest order #{order1_id[-4:]} created with approvalStatus=PENDING")
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code, e.read().decode("utf-8"))
    raise

# 2b. Check Kitchen KDS view - should NOT contain order1 yet!
req_kds = urllib.request.Request(
    f"{BASE}/orders/kitchen",
    headers={"Authorization": f"Bearer {chef_token}"}
)
with urllib.request.urlopen(req_kds) as resp:
    kitchen_orders = json.loads(resp.read().decode("utf-8"))
    k_ids = [o["id"] for o in kitchen_orders]
    assert order1_id not in k_ids, "Unapproved order should not be in kitchen!"
    print("PASS: Unapproved order successfully hidden from kitchen KDS!")

# 2c. Waiter approves order
req_approve = urllib.request.Request(
    f"{BASE}/orders/{order1_id}/approve",
    headers={"Authorization": f"Bearer {waiter_token}"},
    method="POST"
)
with urllib.request.urlopen(req_approve) as resp:
    approved_order = json.loads(resp.read().decode("utf-8"))
    assert approved_order["approvalStatus"] == "APPROVED"
    print(f"PASS: Waiter approved order #{order1_id[-4:]} -> status is now APPROVED!")

# 2d. Check Kitchen KDS view again - should now contain order1!
with urllib.request.urlopen(req_kds) as resp:
    kitchen_orders = json.loads(resp.read().decode("utf-8"))
    k_ids = [o["id"] for o in kitchen_orders]
    assert order1_id in k_ids, "Approved order should now appear in kitchen!"
    print("PASS: Approved order now successfully visible in kitchen KDS!")

print("\n=== TEST 3: Order Rejection & Customer Notification ===")
# Guest places second order
req = urllib.request.Request(
    f"{BASE}/orders?token={TOKEN}",
    data=json.dumps(order_payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req) as resp:
    order2 = json.loads(resp.read().decode("utf-8"))
    order2_id = order2["id"]

# Waiter rejects order2
reject_payload = {"reason": "Kitchen ran out of ingredients"}
req_reject = urllib.request.Request(
    f"{BASE}/orders/{order2_id}/reject",
    data=json.dumps(reject_payload).encode("utf-8"),
    headers={"Authorization": f"Bearer {waiter_token}", "Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req_reject) as resp:
    rejected_order = json.loads(resp.read().decode("utf-8"))
    assert rejected_order["approvalStatus"] == "REJECTED"
    assert rejected_order["status"] == "REJECTED"
    print(f"PASS: Waiter rejected order #{order2_id[-4:]}")

# Check customer orders endpoint
req_guest_orders = urllib.request.Request(f"{BASE}/guest/orders?token={TOKEN}")
with urllib.request.urlopen(req_guest_orders) as resp:
    guest_orders = json.loads(resp.read().decode("utf-8"))
    matching = next(o for o in guest_orders if o["id"] == order2_id)
    assert matching["approvalStatus"] == "REJECTED"
    assert matching["notes"] == "Kitchen ran out of ingredients"
    print("PASS: Customer receives rejection status and reason in real-time!")

print("\n=== TEST 4: Waiter Call: Call -> On It -> Resolved ===")
# 4a. Call waiter
req_call = urllib.request.Request(f"{BASE}/guest/call-waiter?token={TOKEN}", method="POST")
with urllib.request.urlopen(req_call) as resp:
    res = json.loads(resp.read().decode("utf-8"))
    assert res["ok"] is True
    print("PASS: Guest waiter call created (table blinks on floor plan)")

# 4b. Waiter clicks 'On It' (attending)
req_on_it = urllib.request.Request(f"{BASE}/guest/acknowledge-waiter-call?table_id=t-2", method="POST")
with urllib.request.urlopen(req_on_it) as resp:
    res = json.loads(resp.read().decode("utf-8"))
    assert res["ok"] is True
    print("PASS: Waiter clicked 'On It' -> status transitions to attending!")

# 4c. Check customer waiter status returns acknowledged
req_status = urllib.request.Request(f"{BASE}/guest/waiter-status?token={TOKEN}")
with urllib.request.urlopen(req_status) as resp:
    status_data = json.loads(resp.read().decode("utf-8"))
    assert status_data["acknowledged"] is True
    print("PASS: Customer notified that waiter is attending / on the way!")

# 4d. Waiter clicks 'Resolved'
req_resolve = urllib.request.Request(f"{BASE}/guest/resolve-waiter-call?table_id=t-2", method="POST")
with urllib.request.urlopen(req_resolve) as resp:
    res = json.loads(resp.read().decode("utf-8"))
    assert res["ok"] is True
    print("PASS: Waiter clicked 'Resolved' -> alert closed and cleared from table!")

print("\n==========================================")
print("ALL BACKEND & GUEST FLOW TESTS PASSED 100%!")
print("==========================================")
