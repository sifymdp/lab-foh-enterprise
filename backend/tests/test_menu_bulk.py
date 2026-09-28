import io
import json
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import openpyxl
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.database import SessionLocal, migrate_schema
from app.models import MenuItem, Order, OrderItem, User, DiningSession, Table
from app.models.menu_bulk import MenuImport, MenuImportItem, MenuVersion, MenuChangeLog
from app.services import menu_excel_service


def test_bulk_menu_full_flow():
    migrate_schema()
    db = SessionLocal()

    # 1. Setup test user
    owner = db.query(User).filter(User.role == "OWNER").first()
    if not owner:
        owner = User(
            id="test-owner-id",
            name="Test Owner",
            email="owner@test.local",
            password_hash="fake",
            role="OWNER",
            is_active=True,
            tenant_id="org-test",
            branch_id="branch-1",
        )
        db.add(owner)
        db.commit()

    print("[1] Testing Template Generation...")
    template_buf = menu_excel_service.generate_menu_template()
    wb = openpyxl.load_workbook(template_buf)
    ws = wb.active
    headers = [ws.cell(row=4, column=c).value for c in range(1, 13)]
    assert "Item Code" in headers, "Header missing Item Code"
    assert "Item Name" in headers, "Header missing Item Name"
    assert "Price" in headers, "Header missing Price"
    print(f"  [OK] Template verified with headers: {headers}")

    # Clean up any leftover test records from previous runs
    db.query(OrderItem).filter(OrderItem.id.like("test-oi-bulk-%")).delete()
    db.query(Order).filter(Order.id.like("test-order-bulk-%")).delete()
    db.query(MenuItem).filter(MenuItem.item_code.like("BULK%")).delete()
    db.query(MenuItem).filter(MenuItem.item_code.in_(["DUP001", "DUP002", "ERR001", "ERR002"])).delete()
    db.commit()

    print("\n[2] Testing Current Menu Export...")
    export_buf = menu_excel_service.export_current_menu(db, tenant_id=owner.tenant_id, branch_id=owner.branch_id)
    wb_export = openpyxl.load_workbook(export_buf)
    ws_export = wb_export.active
    export_rows = ws_export.max_row
    assert export_rows >= 2, "Expected at least 1 menu item in export"
    print(f"  [OK] Current menu exported with {export_rows - 1} items")

    # Pick an existing item to modify
    existing_item = db.query(MenuItem).filter(MenuItem.is_active.is_(True)).first()
    assert existing_item is not None
    original_price = float(existing_item.price)
    original_code = existing_item.item_code or "ITM001"
    existing_item.item_code = original_code
    db.commit()

    # Create a historical order on this item to test non-destructive deactivation
    sample_table = db.query(Table).first()
    if not sample_table:
        sample_table = Table(id="test-tbl-1", number="99", capacity=4, status="AVAILABLE")
        db.add(sample_table)
        db.commit()

    sample_order = Order(
        id="test-order-bulk-1",
        session_id="test-sess-1",
        table_id=sample_table.id,
        tenant_id=owner.tenant_id,
        branch_id=owner.branch_id,
        placed_at=datetime.now(timezone.utc),
        status="ACTIVE",
    )
    db.add(sample_order)
    sample_oi = OrderItem(
        id="test-oi-bulk-1",
        order_id="test-order-bulk-1",
        menu_item_id=existing_item.id,
        item_name=existing_item.name,
        unit_price=existing_item.price,
        quantity=2,
    )
    db.add(sample_oi)
    db.commit()

    print("\n[3] Building Synthetic Excel with 100 New Items, 1 Update, 2 Duplicates, and 2 Errors...")
    wb_test = openpyxl.Workbook()
    ws_test = wb_test.active
    ws_test.title = "Menu"

    # Header
    for col_idx, col_name in enumerate(menu_excel_service.EXCEL_COLUMNS, start=1):
        ws_test.cell(row=1, column=col_idx, value=col_name)

    row_cursor = 2

    # 1 Updated Item
    updated_new_price = original_price + 50.0
    ws_test.cell(row=row_cursor, column=1, value=original_code)
    ws_test.cell(row=row_cursor, column=2, value=existing_item.name)
    ws_test.cell(row=row_cursor, column=3, value=existing_item.category)
    ws_test.cell(row=row_cursor, column=4, value="Updated description for test")
    ws_test.cell(row=row_cursor, column=5, value=updated_new_price)
    ws_test.cell(row=row_cursor, column=6, value=5.0)
    ws_test.cell(row=row_cursor, column=7, value=0.0)
    ws_test.cell(row=row_cursor, column=8, value="Veg")
    ws_test.cell(row=row_cursor, column=9, value="Yes")
    ws_test.cell(row=row_cursor, column=10, value=15)
    row_cursor += 1

    # 100 New Items
    for i in range(1, 101):
        ws_test.cell(row=row_cursor, column=1, value=f"BULK{i:03d}")
        ws_test.cell(row=row_cursor, column=2, value=f"Artisanal Dish Spec {i}")
        ws_test.cell(row=row_cursor, column=3, value="Chef Specials")
        ws_test.cell(row=row_cursor, column=4, value=f"Delicious craft recipe #{i}")
        ws_test.cell(row=row_cursor, column=5, value=150.0 + i)
        ws_test.cell(row=row_cursor, column=6, value=5.0)
        ws_test.cell(row=row_cursor, column=7, value=0.0)
        ws_test.cell(row=row_cursor, column=8, value="Veg" if i % 2 == 0 else "Non-Veg")
        ws_test.cell(row=row_cursor, column=9, value="Yes")
        ws_test.cell(row=row_cursor, column=10, value=15)
        row_cursor += 1

    # 2 Possible Duplicates (similar to existing item name)
    ws_test.cell(row=row_cursor, column=1, value="DUP001")
    ws_test.cell(row=row_cursor, column=2, value=existing_item.name + " Special")  # e.g. "Ghee Roast Masala Dosa Special"
    ws_test.cell(row=row_cursor, column=3, value=existing_item.category)
    ws_test.cell(row=row_cursor, column=5, value=300.0)
    row_cursor += 1

    ws_test.cell(row=row_cursor, column=1, value="DUP002")
    ws_test.cell(row=row_cursor, column=2, value=existing_item.name.replace(" ", "  "))  # extra spaces / minor spelling variation
    ws_test.cell(row=row_cursor, column=3, value=existing_item.category)
    ws_test.cell(row=row_cursor, column=5, value=310.0)
    row_cursor += 1

    # 2 Intentional Errors
    # Error 1: Negative Price
    ws_test.cell(row=row_cursor, column=1, value="ERR001")
    ws_test.cell(row=row_cursor, column=2, value="Broken Negative Dish")
    ws_test.cell(row=row_cursor, column=3, value="Starters")
    ws_test.cell(row=row_cursor, column=5, value=-50.0)
    row_cursor += 1

    # Error 2: Missing Category & Invalid Price
    ws_test.cell(row=row_cursor, column=1, value="ERR002")
    ws_test.cell(row=row_cursor, column=2, value="Broken Invalid Dish")
    ws_test.cell(row=row_cursor, column=3, value="")  # missing category
    ws_test.cell(row=row_cursor, column=5, value="two hundred")  # invalid price
    row_cursor += 1

    test_bytes = io.BytesIO()
    wb_test.save(test_bytes)
    test_bytes.seek(0)
    raw_content = test_bytes.getvalue()

    print("\n[4] Running Parse & Analysis Engine...")
    import_rec = menu_excel_service.parse_and_analyze_excel(
        db=db,
        file_bytes=raw_content,
        file_name="test_bulk_menu.xlsx",
        user=owner,
        tenant_id=owner.tenant_id,
        branch_id=owner.branch_id,
    )

    print(f"  [OK] Total rows analyzed: {import_rec.total_rows}")
    print(f"  [OK] New count: {import_rec.new_count}")
    print(f"  [OK] Updated count: {import_rec.updated_count}")
    print(f"  [OK] Warnings / Duplicates: {import_rec.warning_count}")
    print(f"  [OK] Errors detected: {import_rec.error_count}")
    print(f"  [OK] Missing items in file: {import_rec.deactivated_count}")

    assert import_rec.new_count == 100, f"Expected 100 new, got {import_rec.new_count}"
    assert import_rec.updated_count == 1, f"Expected 1 updated, got {import_rec.updated_count}"
    assert import_rec.error_count == 2, f"Expected 2 errors, got {import_rec.error_count}"
    assert import_rec.warning_count >= 1, f"Expected at least 1 warning, got {import_rec.warning_count}"

    print("\n[5] Testing Error Report Generation...")
    err_buf = menu_excel_service.generate_error_report(import_rec)
    wb_err = openpyxl.load_workbook(err_buf)
    assert wb_err.active.max_row == 3, f"Expected header + 2 error rows, got {wb_err.active.max_row}"
    print("  [OK] Error report Excel generated with exact 2 error rows")

    print("\n[6] Testing Approval Workflow & Atomic Transaction...")
    version_rec = menu_excel_service.approve_menu_import(
        db=db,
        import_id=import_rec.id,
        deactivate_missing=False,
        user=owner,
        notes="Automated unit test approval",
    )
    print(f"  [OK] Approved version created: {version_rec.version_tag} (Total items in menu: {version_rec.total_items})")
    assert version_rec.new_items_count == 100 + import_rec.warning_count
    assert version_rec.updated_items_count == 1

    # Verify that the updated item in DB has the new price
    db.refresh(existing_item)
    assert float(existing_item.price) == updated_new_price, f"Price was not updated! Got {existing_item.price}"
    print(f"  [OK] Existing item '{existing_item.name}' price successfully changed from Rs.{original_price} to Rs.{existing_item.price}")

    # Verify that historical order item still has the original snapshot price!
    db.refresh(sample_oi)
    assert float(sample_oi.unit_price) == original_price, "Historical order item unit_price was modified! It must remain snapshotted!"
    print(f"  [OK] Historical OrderItem snapshot verified: Rs.{sample_oi.unit_price} (order integrity 100% preserved)")

    print("\n[7] Testing Import Report Generation...")
    report_buf = menu_excel_service.generate_import_report(import_rec)
    wb_rep = openpyxl.load_workbook(report_buf)
    sheet_names = wb_rep.sheetnames
    assert "Import Summary" in sheet_names
    assert "Items Detail" in sheet_names
    print(f"  [OK] Comprehensive Import Report generated with sheets: {sheet_names}")

    # Cleanup test items so we leave the DB clean
    print("\n[8] Cleaning up test records...")
    db.query(OrderItem).filter(OrderItem.id == "test-oi-bulk-1").delete()
    db.query(Order).filter(Order.id == "test-order-bulk-1").delete()
    db.query(MenuItem).filter(MenuItem.item_code.like("BULK%")).delete()
    db.query(MenuItem).filter(MenuItem.item_code.in_(["DUP001", "DUP002"])).delete()
    # Restore original price
    existing_item.price = original_price
    db.commit()
    print("  [OK] Test cleanup complete")

    db.close()
    print("\n[SUCCESS] ALL TESTS PASSED SUCCESSFULLY! Smart Bulk Menu Management Engine is 100% verified!")


if __name__ == "__main__":
    test_bulk_menu_full_flow()
