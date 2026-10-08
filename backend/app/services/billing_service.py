from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.ids import new_id
from app.models import Bill, Discount, User, RefundRequest

def _bill(db: Session, bill_id: str, user: User) -> Bill:
    bill = db.query(Bill).filter(Bill.id == bill_id, Bill.tenant_id == user.tenant_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if user.branch_id and bill.branch_id != user.branch_id:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill

def calculate_bill(db: Session, bill: Bill) -> Bill:
    from decimal import Decimal
    from app.models import Order, OrderItem, Discount
    from app.services.configuration_service import get_config

    # 1. Dynamically calculate subtotal from actual order items if session exists
    if bill.session_id:
        orders = db.query(Order).filter(Order.session_id == bill.session_id).all()
        order_items_total = Decimal("0")
        has_items = False
        for order in orders:
            for oi in order.items:
                has_items = True
                order_items_total += Decimal(str(oi.quantity)) * Decimal(str(oi.unit_price))
        if has_items:
            bill.subtotal = order_items_total
    elif bill.order_id:
        order = db.get(Order, bill.order_id)
        if order and order.items:
            bill.subtotal = sum(Decimal(str(oi.quantity)) * Decimal(str(oi.unit_price)) for oi in order.items)

    subtotal_val = Decimal(str(bill.subtotal or 0))

    # 2. Check for active approved percentage discount to scale discount amount dynamically
    approved_disc = (
        db.query(Discount)
        .filter(Discount.bill_id == bill.id, Discount.status == "APPROVED")
        .order_by(Discount.created_at.desc())
        .first()
    )
    if approved_disc and approved_disc.percent and approved_disc.percent > 0:
        bill.discount_amount = round(subtotal_val * Decimal(str(approved_disc.percent)) / Decimal("100"), 2)
        if not bill.discount_reason:
            bill.discount_reason = approved_disc.reason

    discount_val = Decimal(str(bill.discount_amount or 0))
    # Discount cannot exceed subtotal
    if discount_val > subtotal_val:
        discount_val = subtotal_val
        bill.discount_amount = discount_val

    cfg = get_config(db, bill.tenant_id, "billing_settings", bill.branch_id)
    tax_rate = Decimal(str(cfg.get("tax_rate", 5.0)))
    service_charge_rate = Decimal(str(cfg.get("service_charge_rate", 10.0)))

    taxable = max(subtotal_val - discount_val, Decimal("0"))

    svc_charge = round(taxable * service_charge_rate / Decimal("100"), 2)
    tax = round((taxable + svc_charge) * tax_rate / Decimal("100"), 2)
    grand_total = round(taxable + svc_charge + tax, 2)

    bill.service_charge_amount = svc_charge
    bill.tax_amount = tax
    bill.total = grand_total
    return bill


def apply_discount(db: Session, bill_id: str, payload, user: User) -> Discount:
    bill = _bill(db, bill_id, user)
    bill_status = (bill.status or bill.bill_status or "OPEN").upper()
    if bill_status in ("PAID", "CANCELLED", "REFUNDED"):
        raise HTTPException(status_code=409, detail=f"Cannot apply discount to a {bill_status.lower()} bill")
    if payload.percent < 0 or payload.percent > 100:
        raise HTTPException(status_code=422, detail="Discount must be between 0 and 100 percent")
    
    # Fetch discount limits for user's role from config service
    from app.services.configuration_service import get_config
    disc_cfg = get_config(db, user.tenant_id, "discount_rules", user.branch_id)
    
    role_upper = user.role.upper()
    max_auto_discount = 0.0
    if role_upper == "OWNER":
        max_auto_discount = 100.0
    elif role_upper == "MANAGER":
        max_auto_discount = float(disc_cfg.get("manager_max_discount", 30.0))
    elif role_upper in ("CASHIER", "WAITER"):
        max_auto_discount = float(disc_cfg.get("cashier_max_discount", 5.0))
        
    reason_str = str(payload.reason or "").lower()
    festival_presets = disc_cfg.get("festival_presets", [])
    is_festival_offer = (
        "festival:" in reason_str or 
        "festival" in reason_str or 
        "happy hour" in reason_str or
        "anniversary" in reason_str or
        "special" in reason_str or
        any(
            p.get("name", "").lower() in reason_str or p.get("id", "").lower() in reason_str
            for p in festival_presets
        )
    )
    
    # Pre-approved festival offers, clearing discount (0%), or discounts within manager limit (up to 30%) are approved directly
    if payload.percent == 0 or is_festival_offer or payload.percent <= float(disc_cfg.get("manager_max_discount", 30.0)):
        approval = False
    else:
        approval = payload.percent > max_auto_discount
        
    now = datetime.now(timezone.utc)
    
    discount = Discount(
        id=new_id(),
        bill_id=bill.id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
        user_id=user.id,
        percent=payload.percent,
        reason=payload.reason,
        status="PENDING" if approval else "APPROVED",
        created_at=now
    )
    
    if not approval:
        bill.discount_amount = round(float(bill.subtotal) * payload.percent / 100, 2)
        bill.discount_reason = payload.reason if payload.percent > 0 else None
        calculate_bill(db, bill)
    else:
        # Create a pending RefundRequest to surface in the approvals queue
        refund_req = RefundRequest(
            id=new_id(),
            bill_id=bill.id,
            tenant_id=user.tenant_id,
            branch_id=user.branch_id,
            requested_by=user.id,
            request_type="DISCOUNT",
            amount=payload.percent,
            reason=payload.reason,
            status="PENDING",
            created_at=now
        )
        db.add(refund_req)
        
    db.add(discount)
    db.commit()
    db.refresh(discount)
    return discount

def list_bills(db: Session, user: User) -> list[Bill]:
    from app.core.deps import get_user_branches
    q = db.query(Bill).filter(Bill.tenant_id == user.tenant_id)
    allowed_branches = get_user_branches(db, user)
    if allowed_branches is not None:
        q = q.filter(Bill.branch_id.in_(allowed_branches))
    return q.order_by(Bill.generated_at.desc()).all()

