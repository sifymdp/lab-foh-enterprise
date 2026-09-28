"""Smart Bulk Menu Management Service using Excel.

Provides production-ready:
1. Template generation (.xlsx)
2. Current menu export (.xlsx) with RBAC & multi-tenant scoping
3. High-speed upload parsing & normalization
4. Smart validation & duplicate/similarity detection (fuzzy matching)
5. Comprehensive diff analysis (NEW, UPDATED, UNCHANGED, ERROR, POSSIBLE_DUPLICATE)
6. Transaction-safe approval workflow with menu versioning & audit logs
7. Soft-deactivation (preserving historical orders)
8. Excel Error Reports and Import Reports
"""

from __future__ import annotations

import difflib
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.models import AuditLog, MenuItem
from app.models.menu_bulk import MenuChangeLog, MenuImport, MenuImportItem, MenuVersion
from app.models.user import User
from app.socket_manager import emit_sync

logger = logging.getLogger(__name__)

# Expected canonical Excel headers
EXCEL_COLUMNS = [
    "Item Code",
    "Item Name",
    "Category",
    "Description",
    "Price",
    "Tax Rate",
    "Service Charge",
    "Veg/Non-Veg",
    "Available",
    "Preparation Time",
    "Modifiers",
    "Allergen Information",
]

# Normalization map for headers
HEADER_MAP: dict[str, str] = {
    "item code": "item_code",
    "itemcode": "item_code",
    "code": "item_code",
    "id": "item_code",
    "item name": "name",
    "itemname": "name",
    "name": "name",
    "dish": "name",
    "dish name": "name",
    "category": "category",
    "cuisine": "category",
    "menu category": "category",
    "description": "description",
    "desc": "description",
    "price": "price",
    "unit price": "price",
    "rate": "price",
    "cost": "price",
    "tax rate": "tax_rate",
    "tax": "tax_rate",
    "tax %": "tax_rate",
    "tax rate (%)": "tax_rate",
    "service charge": "service_charge",
    "service charge (%)": "service_charge",
    "sc": "service_charge",
    "veg/non-veg": "dietary_type",
    "veg / non-veg": "dietary_type",
    "veg/non veg": "dietary_type",
    "diet": "dietary_type",
    "dietary type": "dietary_type",
    "type": "dietary_type",
    "available": "available",
    "is available": "available",
    "in stock": "available",
    "status": "available",
    "preparation time": "prep_time_minutes",
    "prep time": "prep_time_minutes",
    "prep time (mins)": "prep_time_minutes",
    "prep time (min)": "prep_time_minutes",
    "cooking time": "prep_time_minutes",
    "modifiers": "modifiers",
    "options": "modifiers",
    "add-ons": "modifiers",
    "addons": "modifiers",
    "allergen information": "allergens",
    "allergens": "allergens",
    "allergy": "allergens",
}


# ─── Excel Styling Helpers ───────────────────────────────────────────────────


def _create_header_style() -> tuple[Font, PatternFill, Alignment, Border]:
    font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    border_side = Side(style="thin", color="CBD5E1")
    border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)
    return font, fill, alignment, border


def _create_row_style() -> tuple[Font, Alignment, Border]:
    font = Font(name="Calibri", size=10)
    alignment = Alignment(vertical="center")
    border_side = Side(style="thin", color="E2E8F0")
    border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)
    return font, alignment, border


# ─── Template Generation ─────────────────────────────────────────────────────


def generate_menu_template() -> io.BytesIO:
    """Generate a clean, professionally formatted blank menu Excel template with instructions."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Menu Template"

    font, fill, alignment, border = _create_header_style()
    row_font, row_align, row_border = _create_row_style()

    # Title row
    ws.merge_cells("A1:L1")
    title_cell = ws["A1"]
    title_cell.value = "RESTAURANT MASTER MENU TEMPLATE — BULK IMPORT"
    title_cell.font = Font(name="Calibri", size=14, bold=True, color="1E293B")
    title_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    # Subtitle / instructions
    ws.merge_cells("A2:L2")
    sub_cell = ws["A2"]
    sub_cell.value = "Fill in your menu items below. 'Item Code', 'Item Name', 'Category', and 'Price' are required. Existing items with matching Item Code will be updated."
    sub_cell.font = Font(name="Calibri", size=10, italic=True, color="64748B")
    sub_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = 20

    # Header row on Row 4
    header_row_idx = 4
    ws.row_dimensions[header_row_idx].height = 26
    for col_idx, col_name in enumerate(EXCEL_COLUMNS, start=1):
        cell = ws.cell(row=header_row_idx, column=col_idx, value=col_name)
        cell.font = font
        cell.fill = fill
        cell.alignment = alignment
        cell.border = border

    # Sample data rows
    samples = [
        ("ITM001", "Ghee Roast Masala Dosa", "South Indian", "Crisp golden crepe roasted in A2 desi ghee with spiced potato masala", 280.0, 5.0, 0.0, "Veg", "Yes", 15, "Extra Sambar, Gunpowder", "Dairy"),
        ("ITM002", "Murgh Makhani (Butter Chicken)", "North Indian", "Tandoor-smoked chicken tikka in velvety San Marzano tomato butter gravy", 540.0, 5.0, 0.0, "Non-Veg", "Yes", 20, "Boneless, Extra Gravy", "Dairy, Nuts"),
        ("ITM003", "Truffle Edamame Dim Sum (4pcs)", "Chinese & Pan-Asian", "Translucent steamed dumplings filled with water chestnut & truffle oil", 480.0, 5.0, 0.0, "Veg", "Yes", 18, "Chilli Oil Dip", "Gluten"),
        ("ITM004", "Wood-Fired Burrata Margherita", "Italian & Continental", "48-hr fermented sourdough crust, San Marzano D.O.P., fresh burrata & sweet basil", 540.0, 5.0, 0.0, "Veg", "Yes", 20, "Extra Burrata", "Gluten, Dairy"),
        ("ITM005", "Smoked Rosemary Old Fashioned", "Liquor & Cocktails", "Bourbon whiskey, Angostura bitters, torched organic rosemary smoke", 650.0, 10.0, 5.0, "Liquor", "Yes", 10, "Large Ice Cube", "None"),
    ]

    for row_offset, row_data in enumerate(samples, start=5):
        ws.row_dimensions[row_offset].height = 22
        for col_idx, val in enumerate(row_data, start=1):
            cell = ws.cell(row=row_offset, column=col_idx, value=val)
            cell.font = row_font
            cell.alignment = row_align
            cell.border = row_border
            if col_idx in (5, 6, 7, 10):  # Numeric columns
                cell.alignment = Alignment(horizontal="right", vertical="center")

    # Auto-fit column widths with padding
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or "")) for cell in col if cell.row >= 4)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ─── Current Menu Export ─────────────────────────────────────────────────────


def export_current_menu(
    db: Session,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> io.BytesIO:
    """Export the current active menu for the authorized tenant/branch."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Current Menu"

    font, fill, alignment, border = _create_header_style()
    row_font, row_align, row_border = _create_row_style()

    # Header on row 1
    ws.row_dimensions[1].height = 26
    for col_idx, col_name in enumerate(EXCEL_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = font
        cell.fill = fill
        cell.alignment = alignment
        cell.border = border

    # Query items scoped to tenant / branch
    q = db.query(MenuItem).filter(MenuItem.is_active.is_(True))
    if tenant_id:
        q = q.filter((MenuItem.tenant_id == tenant_id) | (MenuItem.tenant_id.is_(None)))
    if branch_id:
        q = q.filter((MenuItem.branch_id == branch_id) | (MenuItem.branch_id.is_(None)))

    items = q.order_by(MenuItem.category, MenuItem.display_order, MenuItem.name).all()

    for row_idx, item in enumerate(items, start=2):
        ws.row_dimensions[row_idx].height = 22
        code = item.item_code or f"ITM{row_idx-1:03d}"
        diet = item.dietary_type or "VEG"
        avail = "Yes" if item.available else "No"
        prep = item.prep_time_minutes or 15
        tax = float(item.tax_rate) if item.tax_rate is not None else 5.0
        sc = float(item.service_charge) if item.service_charge is not None else 0.0

        row_vals = [
            code,
            item.name,
            item.category,
            item.description or "",
            float(item.price),
            tax,
            sc,
            diet.title(),
            avail,
            prep,
            item.modifiers or "",
            item.allergens or "",
        ]

        for col_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = row_font
            cell.alignment = row_align
            cell.border = row_border
            if col_idx in (5, 6, 7, 10):
                cell.alignment = Alignment(horizontal="right", vertical="center")

    # Column widths
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ─── Normalization & Parsing ─────────────────────────────────────────────────


def _normalize_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _normalize_category(val: str) -> str:
    s = val.strip()
    if not s:
        return "General"
    # Title-case standard categories, preserving specific casing like Pan-Asian
    lower = s.lower()
    if "pan-asian" in lower or "chinese" in lower:
        return "Chinese & Pan-Asian"
    if "south indian" in lower:
        return "South Indian"
    if "north indian" in lower:
        return "North Indian"
    if "italian" in lower or "continental" in lower:
        return "Italian & Continental"
    if "liquor" in lower or "cocktail" in lower or "beverage" in lower or "bar" in lower:
        return "Liquor & Cocktails"
    if "dessert" in lower:
        return "Desserts"
    if "starter" in lower or "appetizer" in lower:
        return "Starters"
    return s.title()


def _normalize_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in ("yes", "y", "true", "1", "available", "live", "active", "in stock")


def _normalize_diet(val: Any) -> str:
    s = str(val or "").strip().lower()
    if "non" in s:
        return "NON_VEG"
    if "liquor" in s or "bar" in s or "drink" in s or "wine" in s or "beer" in s:
        return "LIQUOR"
    return "VEG"


# ─── Fuzzy Duplicate Detection ───────────────────────────────────────────────


def find_similar_existing_item(
    name: str,
    existing_names: list[str],
    threshold: float = 0.82,
) -> tuple[str, float] | None:
    """Detect if an uploaded name is very similar to an existing menu item (e.g.

    'Chicken Biriyani' vs 'Chicken Biryani').
    """
    clean_target = name.strip().lower()
    best_match = None
    best_score = 0.0

    for existing in existing_names:
        clean_existing = existing.strip().lower()
        if clean_target == clean_existing:
            continue  # Exact match handled separately
        score = difflib.SequenceMatcher(None, clean_target, clean_existing).ratio()
        if score > best_score:
            best_score = score
            best_match = existing

    if best_match and best_score >= threshold:
        return best_match, round(best_score, 2)
    return None


# ─── Analysis Engine ─────────────────────────────────────────────────────────


def parse_and_analyze_excel(
    db: Session,
    file_bytes: bytes,
    file_name: str,
    user: User,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> MenuImport:
    """Parse uploaded Excel file, validate all rows, detect duplicates, diff against DB,

    and create a PENDING_REVIEW MenuImport record.
    """
    # Load workbook from memory
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as exc:
        raise ValueError(f"Invalid or corrupted Excel file (.xlsx required): {exc}") from exc

    ws = wb.active
    if ws is None:
        raise ValueError("Excel file contains no active worksheet")

    # Find header row (look through first 10 rows for columns matching 'item' or 'name')
    header_row_idx = None
    header_indices: dict[str, int] = {}

    for r_idx in range(1, min(15, ws.max_row + 1)):
        row_vals = [str(ws.cell(row=r_idx, column=c).value or "").strip().lower() for c in range(1, ws.max_column + 1)]
        matched = 0
        current_map: dict[str, int] = {}
        for c_idx, val in enumerate(row_vals, start=1):
            if val in HEADER_MAP:
                field = HEADER_MAP[val]
                if field not in current_map:
                    current_map[field] = c_idx
                    matched += 1
        if matched >= 3 and ("name" in current_map or "item_code" in current_map):
            header_row_idx = r_idx
            header_indices = current_map
            break

    if header_row_idx is None:
        raise ValueError("Could not find valid menu headers in Excel. Expected columns: 'Item Code', 'Item Name', 'Category', 'Price'.")

    # Load existing items from DB for tenant / branch
    q = db.query(MenuItem).filter(MenuItem.is_active.is_(True))
    if tenant_id:
        q = q.filter((MenuItem.tenant_id == tenant_id) | (MenuItem.tenant_id.is_(None)))
    if branch_id:
        q = q.filter((MenuItem.branch_id == branch_id) | (MenuItem.branch_id.is_(None)))
    existing_items = q.all()

    existing_by_code: dict[str, MenuItem] = {
        i.item_code.strip().upper(): i for i in existing_items if i.item_code
    }
    existing_by_name: dict[str, MenuItem] = {
        i.name.strip().lower(): i for i in existing_items
    }
    existing_names_list: list[str] = [i.name for i in existing_items]

    # Create MenuImport container
    import_rec = MenuImport(
        id=new_id(),
        tenant_id=tenant_id or user.tenant_id,
        branch_id=branch_id or user.branch_id,
        uploaded_by=user.id,
        file_name=file_name,
        status="PENDING_REVIEW",
        created_at=datetime.now(timezone.utc),
    )
    db.add(import_rec)
    db.flush()

    seen_sheet_codes: set[str] = set()
    matched_db_item_ids: set[str] = set()

    new_count = 0
    updated_count = 0
    unchanged_count = 0
    error_count = 0
    warning_count = 0
    total_valid_rows = 0

    # Process rows
    for row_idx in range(header_row_idx + 1, ws.max_row + 1):
        # Extract raw cells
        raw_code = _normalize_str(ws.cell(row=row_idx, column=header_indices.get("item_code", 0)).value) if "item_code" in header_indices else ""
        raw_name = _normalize_str(ws.cell(row=row_idx, column=header_indices.get("name", 0)).value) if "name" in header_indices else ""
        raw_cat = _normalize_str(ws.cell(row=row_idx, column=header_indices.get("category", 0)).value) if "category" in header_indices else ""
        raw_desc = _normalize_str(ws.cell(row=row_idx, column=header_indices.get("description", 0)).value) if "description" in header_indices else ""
        raw_price = ws.cell(row=row_idx, column=header_indices.get("price", 0)).value if "price" in header_indices else None
        raw_tax = ws.cell(row=row_idx, column=header_indices.get("tax_rate", 0)).value if "tax_rate" in header_indices else None
        raw_sc = ws.cell(row=row_idx, column=header_indices.get("service_charge", 0)).value if "service_charge" in header_indices else None
        raw_diet = _normalize_str(ws.cell(row=row_idx, column=header_indices.get("dietary_type", 0)).value) if "dietary_type" in header_indices else ""
        raw_avail = ws.cell(row=row_idx, column=header_indices.get("available", 0)).value if "available" in header_indices else True
        raw_prep = ws.cell(row=row_idx, column=header_indices.get("prep_time_minutes", 0)).value if "prep_time_minutes" in header_indices else None
        raw_mod = _normalize_str(ws.cell(row=row_idx, column=header_indices.get("modifiers", 0)).value) if "modifiers" in header_indices else ""
        raw_allergens = _normalize_str(ws.cell(row=row_idx, column=header_indices.get("allergens", 0)).value) if "allergens" in header_indices else ""

        # Skip completely blank rows
        if not raw_code and not raw_name and raw_price is None and not raw_cat:
            continue

        total_valid_rows += 1
        errors: list[str] = []
        warnings: list[str] = []

        # ── 1. Validation ──
        # Check required Name
        if not raw_name:
            errors.append("Item Name is required")

        # Check required Category
        if not raw_cat:
            errors.append("Category is required")

        # Check required Price
        parsed_price = 0.0
        if raw_price is None or str(raw_price).strip() == "":
            errors.append("Price is required")
        else:
            try:
                parsed_price = float(str(raw_price).replace("$", "").replace("₹", "").replace(",", "").strip())
                if parsed_price < 0:
                    errors.append(f"Price cannot be negative (got: {raw_price})")
            except ValueError:
                errors.append(f"Invalid numeric price: \"{raw_price}\"")

        # Check Tax Rate
        parsed_tax = 5.0
        if raw_tax is not None and str(raw_tax).strip() != "":
            try:
                parsed_tax = float(str(raw_tax).replace("%", "").strip())
                if parsed_tax < 0 or parsed_tax > 100:
                    errors.append(f"Tax Rate must be between 0% and 100% (got: {raw_tax})")
            except ValueError:
                errors.append(f"Invalid numeric tax rate: \"{raw_tax}\"")

        # Check Service Charge
        parsed_sc = 0.0
        if raw_sc is not None and str(raw_sc).strip() != "":
            try:
                parsed_sc = float(str(raw_sc).replace("%", "").strip())
                if parsed_sc < 0 or parsed_sc > 100:
                    errors.append(f"Service charge must be between 0% and 100% (got: {raw_sc})")
            except ValueError:
                errors.append(f"Invalid numeric service charge: \"{raw_sc}\"")

        # Check Prep Time
        parsed_prep = 15
        if raw_prep is not None and str(raw_prep).strip() != "":
            try:
                parsed_prep = int(float(str(raw_prep).strip()))
                if parsed_prep < 0:
                    errors.append("Preparation time cannot be negative")
            except ValueError:
                errors.append(f"Invalid preparation time: \"{raw_prep}\"")

        # Check duplicate code within the sheet
        clean_code = raw_code.strip().upper() if raw_code else ""
        if clean_code:
            if clean_code in seen_sheet_codes:
                errors.append(f"Duplicate Item Code '{clean_code}' inside uploaded Excel sheet")
            seen_sheet_codes.add(clean_code)

        # Normalized values dict
        norm_values: dict[str, Any] = {
            "item_code": clean_code or None,
            "name": raw_name.strip(),
            "category": _normalize_category(raw_cat),
            "description": raw_desc.strip() or None,
            "price": round(parsed_price, 2),
            "tax_rate": round(parsed_tax, 2),
            "service_charge": round(parsed_sc, 2),
            "dietary_type": _normalize_diet(raw_diet),
            "available": _normalize_bool(raw_avail),
            "prep_time_minutes": parsed_prep,
            "modifiers": raw_mod.strip() or None,
            "allergens": raw_allergens.strip() or None,
        }

        # ── 2. Identification & Matching ──
        existing: MenuItem | None = None
        if clean_code and clean_code in existing_by_code:
            existing = existing_by_code[clean_code]
        elif raw_name.strip().lower() in existing_by_name:
            existing = existing_by_name[raw_name.strip().lower()]

        action = "NEW"
        status = "VALID"
        similarity_match = None
        similarity_score = None
        old_values: dict[str, Any] | None = None

        if errors:
            action = "ERROR"
            status = "ERROR"
            error_count += 1
        elif existing is not None:
            matched_db_item_ids.add(existing.id)
            old_values = {
                "id": existing.id,
                "item_code": existing.item_code,
                "name": existing.name,
                "category": existing.category,
                "description": existing.description,
                "price": float(existing.price),
                "tax_rate": float(existing.tax_rate or 5.0),
                "service_charge": float(existing.service_charge or 0.0),
                "dietary_type": existing.dietary_type or "VEG",
                "available": bool(existing.available),
                "prep_time_minutes": existing.prep_time_minutes or 15,
                "modifiers": existing.modifiers,
                "allergens": existing.allergens,
            }

            # Diff detection
            diff_fields = []
            if norm_values["name"] != existing.name:
                diff_fields.append("name")
            if abs(norm_values["price"] - float(existing.price)) > 0.001:
                diff_fields.append("price")
            if norm_values["category"] != existing.category:
                diff_fields.append("category")
            if norm_values["available"] != bool(existing.available):
                diff_fields.append("available")
            if abs(norm_values["tax_rate"] - float(existing.tax_rate or 5.0)) > 0.001:
                diff_fields.append("tax_rate")
            if abs(norm_values["service_charge"] - float(existing.service_charge or 0.0)) > 0.001:
                diff_fields.append("service_charge")
            if (norm_values["description"] or "") != (existing.description or ""):
                diff_fields.append("description")
            if norm_values["dietary_type"] != (existing.dietary_type or "VEG"):
                diff_fields.append("dietary_type")

            if diff_fields:
                action = "UPDATED"
                updated_count += 1
            else:
                action = "UNCHANGED"
                unchanged_count += 1
        else:
            # New item — run smart duplicate detection
            sim = find_similar_existing_item(norm_values["name"], existing_names_list)
            if sim:
                sim_name, sim_score = sim
                similarity_match = sim_name
                similarity_score = sim_score
                action = "POSSIBLE_DUPLICATE"
                status = "WARNING"
                warnings.append(f"Possible duplicate / similar item to existing: '{sim_name}' ({int(sim_score*100)}% match)")
                warning_count += 1
            else:
                action = "NEW"
                new_count += 1

        # Create import item record
        import_item = MenuImportItem(
            id=new_id(),
            import_id=import_rec.id,
            row_number=row_idx,
            item_code=norm_values["item_code"],
            item_name=norm_values["name"],
            category=norm_values["category"],
            action=action,
            status=status,
            error_message="; ".join(errors) if errors else None,
            warning_message="; ".join(warnings) if warnings else None,
            similarity_match=similarity_match,
            similarity_score=similarity_score,
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(norm_values),
        )
        db.add(import_item)

    # Calculate missing items from existing menu
    missing_items = [i for i in existing_items if i.id not in matched_db_item_ids]
    deactivated_count = len(missing_items)

    import_rec.total_rows = total_valid_rows
    import_rec.new_count = new_count
    import_rec.updated_count = updated_count
    import_rec.unchanged_count = unchanged_count
    import_rec.error_count = error_count
    import_rec.warning_count = warning_count
    import_rec.deactivated_count = deactivated_count
    import_rec.raw_data_json = json.dumps([i.id for i in missing_items])

    db.commit()
    db.refresh(import_rec)
    return import_rec


# ─── Approval Workflow ───────────────────────────────────────────────────────


def approve_menu_import(
    db: Session,
    import_id: str,
    deactivate_missing: bool,
    user: User,
    notes: str | None = None,
) -> MenuVersion:
    """Safely apply an analyzed import inside an atomic database transaction.

    Creates new items, updates changed items, optionally soft-deactivates
    missing items, generates an immutable MenuVersion snapshot, and creates
    audit log entries.
    """
    import_rec = db.get(MenuImport, import_id)
    if not import_rec:
        raise ValueError(f"Menu import '{import_id}' not found")

    if import_rec.status != "PENDING_REVIEW":
        raise ValueError(f"Import cannot be approved in '{import_rec.status}' status")

    # Multi-tenant security check
    if user.role.upper() != "OWNER":
        if import_rec.tenant_id and user.tenant_id and import_rec.tenant_id != user.tenant_id:
            raise PermissionError("Cannot approve menu import from another organization")
        if import_rec.branch_id and user.branch_id and import_rec.branch_id != user.branch_id:
            raise PermissionError("Cannot approve menu import from another branch")

    items = db.query(MenuImportItem).filter(MenuImportItem.import_id == import_id).all()

    # Determine next version number for this tenant/branch
    q_ver = db.query(func.max(MenuVersion.version_number))
    if import_rec.tenant_id:
        q_ver = q_ver.filter(MenuVersion.tenant_id == import_rec.tenant_id)
    if import_rec.branch_id:
        q_ver = q_ver.filter(MenuVersion.branch_id == import_rec.branch_id)
    current_max_ver = q_ver.scalar() or 0
    next_ver_num = current_max_ver + 1
    version_tag = f"v{next_ver_num}"

    # Atomic transaction
    try:
        new_created_count = 0
        updated_applied_count = 0
        deactivated_applied_count = 0

        # Create Version record
        version_rec = MenuVersion(
            id=new_id(),
            version_number=next_ver_num,
            version_tag=version_tag,
            tenant_id=import_rec.tenant_id,
            branch_id=import_rec.branch_id,
            import_id=import_rec.id,
            created_by=user.id,
            created_at=datetime.now(timezone.utc),
            notes=notes or f"Bulk Excel import from {import_rec.file_name}",
        )
        db.add(version_rec)
        db.flush()

        # 1. Process items from the import
        for row in items:
            if row.action in ("ERROR", "UNCHANGED"):
                continue

            new_val: dict[str, Any] = json.loads(row.new_values) if row.new_values else {}
            old_val: dict[str, Any] = json.loads(row.old_values) if row.old_values else {}

            if row.action in ("NEW", "POSSIBLE_DUPLICATE"):
                # Create brand new item
                item_id = new_id()
                new_item = MenuItem(
                    id=item_id,
                    tenant_id=import_rec.tenant_id,
                    branch_id=import_rec.branch_id,
                    item_code=new_val.get("item_code"),
                    name=new_val["name"],
                    category=new_val["category"],
                    description=new_val.get("description"),
                    price=new_val["price"],
                    tax_rate=new_val.get("tax_rate", 5.0),
                    service_charge=new_val.get("service_charge", 0.0),
                    dietary_type=new_val.get("dietary_type", "VEG"),
                    available=new_val.get("available", True),
                    prep_time_minutes=new_val.get("prep_time_minutes", 15),
                    modifiers=new_val.get("modifiers"),
                    allergens=new_val.get("allergens"),
                    is_active=True,
                )
                db.add(new_item)
                new_created_count += 1

                # Log creation
                log = MenuChangeLog(
                    id=new_id(),
                    version_id=version_rec.id,
                    item_id=item_id,
                    item_code=new_val.get("item_code"),
                    item_name=new_val["name"],
                    field_name="CREATED",
                    old_value=None,
                    new_value=json.dumps(new_val),
                    changed_by=user.id,
                )
                db.add(log)

            elif row.action == "UPDATED":
                item_id = old_val.get("id")
                if not item_id:
                    continue
                db_item = db.get(MenuItem, item_id)
                if not db_item:
                    continue

                # Apply updates and log each field change
                for field in (
                    "item_code", "name", "category", "description", "price",
                    "tax_rate", "service_charge", "dietary_type", "available",
                    "prep_time_minutes", "modifiers", "allergens"
                ):
                    old_f = old_val.get(field)
                    new_f = new_val.get(field)
                    if old_f != new_f:
                        setattr(db_item, field, new_f)
                        db.add(MenuChangeLog(
                            id=new_id(),
                            version_id=version_rec.id,
                            item_id=db_item.id,
                            item_code=db_item.item_code,
                            item_name=db_item.name,
                            field_name=field,
                            old_value=str(old_f),
                            new_value=str(new_f),
                            changed_by=user.id,
                        ))
                db_item.is_active = True
                updated_applied_count += 1

        # 2. Process missing items (soft-deactivation if requested)
        if deactivate_missing and import_rec.raw_data_json:
            missing_ids: list[str] = json.loads(import_rec.raw_data_json)
            for m_id in missing_ids:
                m_item = db.get(MenuItem, m_id)
                if m_item and m_item.is_active:
                    m_item.is_active = False
                    m_item.available = False
                    deactivated_applied_count += 1
                    db.add(MenuChangeLog(
                        id=new_id(),
                        version_id=version_rec.id,
                        item_id=m_item.id,
                        item_code=m_item.item_code,
                        item_name=m_item.name,
                        field_name="DEACTIVATED",
                        old_value="ACTIVE",
                        new_value="INACTIVE",
                        changed_by=user.id,
                    ))

        # 3. Create full snapshot for this version
        active_items = db.query(MenuItem).filter(MenuItem.is_active.is_(True)).all()
        snapshot = [
            {
                "id": i.id,
                "item_code": i.item_code,
                "name": i.name,
                "category": i.category,
                "price": float(i.price),
                "available": i.available,
                "tax_rate": float(i.tax_rate or 5.0),
                "dietary_type": i.dietary_type or "VEG",
            }
            for i in active_items
        ]

        version_rec.total_items = len(active_items)
        version_rec.new_items_count = new_created_count
        version_rec.updated_items_count = updated_applied_count
        version_rec.deactivated_items_count = deactivated_applied_count
        version_rec.snapshot_data = json.dumps(snapshot)

        # 4. Mark import approved
        import_rec.status = "APPROVED"
        import_rec.approved_at = datetime.now(timezone.utc)
        import_rec.approved_by = user.id

        # 5. Global Audit Log
        audit = AuditLog(
            id=new_id(),
            user_id=user.id,
            tenant_id=import_rec.tenant_id,
            branch_id=import_rec.branch_id,
            action="MENU_BULK_IMPORT_APPROVED",
            resource_type="menu_version",
            resource_id=version_rec.id,
            old_value=None,
            new_value=json.dumps({
                "version": version_tag,
                "file": import_rec.file_name,
                "new": new_created_count,
                "updated": updated_applied_count,
                "deactivated": deactivated_applied_count,
            }),
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit)

        db.commit()
        db.refresh(version_rec)

        # Emit real-time WebSocket event so floor, KDS, POS, and QR menus refresh automatically
        emit_sync(
            "menu:updated",
            {
                "version": version_tag,
                "totalItems": len(active_items),
                "approvedBy": user.name,
            },
            room=f"floor-{import_rec.branch_id or '1'}",
        )
        return version_rec

    except Exception as exc:
        db.rollback()
        logger.exception("Failed to approve menu import: %s", exc)
        raise exc


def reject_menu_import(db: Session, import_id: str, user: User) -> None:
    import_rec = db.get(MenuImport, import_id)
    if not import_rec:
        raise ValueError(f"Menu import '{import_id}' not found")
    if import_rec.status != "PENDING_REVIEW":
        raise ValueError(f"Cannot reject import in '{import_rec.status}' status")

    import_rec.status = "REJECTED"
    db.commit()


# ─── Reports Generation ──────────────────────────────────────────────────────


def generate_error_report(import_rec: MenuImport) -> io.BytesIO:
    """Generate Excel error report for manager to correct invalid rows."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Import Errors"

    font, fill, alignment, border = _create_header_style()
    row_font, row_align, row_border = _create_row_style()

    cols = ["Row Number", "Item Code", "Item Name", "Problem / Error Description", "Suggested Correction"]
    ws.row_dimensions[1].height = 26
    for idx, c in enumerate(cols, start=1):
        cell = ws.cell(row=1, column=idx, value=c)
        cell.font = font
        cell.fill = fill
        cell.alignment = alignment
        cell.border = border

    error_items = [i for i in import_rec.items if i.status == "ERROR"]

    for r_idx, item in enumerate(error_items, start=2):
        ws.row_dimensions[r_idx].height = 22
        vals = [
            item.row_number,
            item.item_code or "",
            item.item_name,
            item.error_message or "Unknown error",
            "Please check required fields (Name, Category, numeric Price > 0)",
        ]
        for c_idx, val in enumerate(vals, start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            cell.font = row_font
            cell.alignment = row_align
            cell.border = row_border

    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 15)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def generate_import_report(import_rec: MenuImport) -> io.BytesIO:
    """Generate full multi-sheet operational report for approved/analyzed import."""
    wb = openpyxl.Workbook()

    font, fill, alignment, border = _create_header_style()
    row_font, row_align, row_border = _create_row_style()

    # 1. Summary Sheet
    ws_sum = wb.active
    ws_sum.title = "Import Summary"
    ws_sum.row_dimensions[1].height = 28
    ws_sum["A1"] = f"MENU IMPORT REPORT — {import_rec.file_name}"
    ws_sum["A1"].font = Font(name="Calibri", size=14, bold=True)

    summary_rows = [
        ("Import ID", import_rec.id),
        ("File Name", import_rec.file_name),
        ("Status", import_rec.status),
        ("Uploaded At", import_rec.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")),
        ("Approved At", import_rec.approved_at.strftime("%Y-%m-%d %H:%M:%S UTC") if import_rec.approved_at else "N/A"),
        ("Total Rows in File", import_rec.total_rows),
        ("New Items", import_rec.new_count),
        ("Updated Items", import_rec.updated_count),
        ("Unchanged Items", import_rec.unchanged_count),
        ("Warnings / Duplicates", import_rec.warning_count),
        ("Errors", import_rec.error_count),
        ("Missing / Deactivated Items", import_rec.deactivated_count),
    ]

    for idx, (label, val) in enumerate(summary_rows, start=3):
        ws_sum.row_dimensions[idx].height = 20
        c1 = ws_sum.cell(row=idx, column=1, value=label)
        c2 = ws_sum.cell(row=idx, column=2, value=val)
        c1.font = Font(name="Calibri", size=10, bold=True)
        c2.font = row_font

    ws_sum.column_dimensions["A"].width = 28
    ws_sum.column_dimensions["B"].width = 40

    # 2. Detailed Items Sheet
    ws_det = wb.create_sheet(title="Items Detail")
    det_cols = ["Row", "Item Code", "Item Name", "Category", "Action", "Status", "Notes / Changes"]
    ws_det.row_dimensions[1].height = 26
    for idx, c in enumerate(det_cols, start=1):
        cell = ws_det.cell(row=1, column=idx, value=c)
        cell.font = font
        cell.fill = fill
        cell.alignment = alignment
        cell.border = border

    for r_idx, item in enumerate(import_rec.items, start=2):
        ws_det.row_dimensions[r_idx].height = 20
        notes = item.error_message or item.warning_message or ""
        if item.action == "UPDATED" and item.old_values and item.new_values:
            old_d = json.loads(item.old_values)
            new_d = json.loads(item.new_values)
            diffs = [f"{k}: {old_d.get(k)} -> {new_d.get(k)}" for k in ("price", "category", "available", "name") if old_d.get(k) != new_d.get(k)]
            notes = ", ".join(diffs)

        vals = [item.row_number, item.item_code or "", item.item_name, item.category, item.action, item.status, notes]
        for c_idx, val in enumerate(vals, start=1):
            cell = ws_det.cell(row=r_idx, column=c_idx, value=val)
            cell.font = row_font
            cell.alignment = row_align
            cell.border = row_border

    for col in ws_det.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws_det.column_dimensions[col_letter].width = max(max_len + 4, 14)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
