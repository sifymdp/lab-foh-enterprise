from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, require_owner
from app.database import get_db
from app.models.user import User
from app.services import configuration_service
from pydantic import BaseModel

router = APIRouter(prefix="/settings", tags=["settings"])

class BillingSettingsIn(BaseModel):
    currency: str
    tax_rate: float
    service_charge_rate: float
    receipt_header: str | None = None
    receipt_footer: str | None = None

class PaymentMethodsIn(BaseModel):
    CASH: bool
    CARD: bool
    UPI: bool
    QR: bool
    ONLINE: bool

class FestivalPreset(BaseModel):
    id: str | None = None
    name: str
    percent: float
    icon: str = "✨"
    active: bool = True

class DiscountRulesIn(BaseModel):
    cashier_max_discount: float
    manager_max_discount: float
    approval_above_percent: float
    approval_above_amount: float
    active_festival_id: str | None = None
    festival_presets: list[FestivalPreset] = []

@router.get("/billing")
def get_billing_settings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return configuration_service.get_config(db, user.tenant_id, "billing_settings", user.branch_id)

@router.put("/billing")
def update_billing_settings(
    body: BillingSettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner)
):
    from app.services.audit_service import log_action
    cfg = configuration_service.set_config(db, user.tenant_id, "billing_settings", body.model_dump(), user.branch_id)
    log_action(db, user.id, user.tenant_id, user.branch_id, "BILLING_CONFIG_CHANGED", "system_configuration", cfg.id, new_value=body.model_dump())
    return {"ok": True, "config": body.model_dump()}

@router.get("/payments")
def get_payment_settings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return configuration_service.get_config(db, user.tenant_id, "payment_methods", user.branch_id)

@router.put("/payments")
def update_payment_settings(
    body: PaymentMethodsIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner)
):
    from app.services.audit_service import log_action
    cfg = configuration_service.set_config(db, user.tenant_id, "payment_methods", body.model_dump(), user.branch_id)
    log_action(db, user.id, user.tenant_id, user.branch_id, "PAYMENT_CONFIG_CHANGED", "system_configuration", cfg.id, new_value=body.model_dump())
    return {"ok": True, "config": body.model_dump()}

@router.get("/discounts")
def get_discount_settings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    cfg = configuration_service.get_config(db, user.tenant_id, "discount_rules", user.branch_id)
    # Ensure festival_presets is always populated with sensible defaults if missing
    if not cfg.get("festival_presets"):
        cfg["festival_presets"] = [
            {"id": "diwali", "name": "Diwali Festival", "percent": 15.0, "icon": "🪔", "active": True},
            {"id": "newyear", "name": "New Year Special", "percent": 20.0, "icon": "🎉", "active": True},
            {"id": "eid", "name": "Eid Mubarak", "percent": 15.0, "icon": "🌙", "active": True},
            {"id": "christmas", "name": "Christmas Special", "percent": 20.0, "icon": "🎄", "active": True},
            {"id": "weekend", "name": "Weekend Happy Hours", "percent": 10.0, "icon": "⭐", "active": True},
            {"id": "anniversary", "name": "Anniversary Discount", "percent": 25.0, "icon": "🎂", "active": True}
        ]
    if "active_festival_id" not in cfg:
        cfg["active_festival_id"] = "diwali"
    return cfg

@router.put("/discounts")
def update_discount_settings(
    body: DiscountRulesIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner)
):
    from app.services.audit_service import log_action
    cfg = configuration_service.set_config(db, user.tenant_id, "discount_rules", body.model_dump(), user.branch_id)
    log_action(db, user.id, user.tenant_id, user.branch_id, "DISCOUNT_CONFIG_CHANGED", "system_configuration", cfg.id, new_value=body.model_dump())
    return {"ok": True, "config": body.model_dump()}
