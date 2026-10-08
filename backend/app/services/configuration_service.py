import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.core.ids import new_id
from app.models.system_configuration import SystemConfiguration

DEFAULT_CONFIGS = {
    "billing_settings": {
        "currency": "INR",
        "tax_rate": 5.0,
        "service_charge_rate": 10.0,
        "receipt_header": "Welcome to FOH Restaurant",
        "receipt_footer": "Thank you for dining with us!"
    },
    "payment_methods": {
        "CASH": True,
        "CARD": True,
        "UPI": True,
        "QR": True,
        "ONLINE": True
    },
    "discount_rules": {
        "cashier_max_discount": 5.0,
        "manager_max_discount": 30.0,
        "approval_above_percent": 5.0,
        "approval_above_amount": 500.0,
        "active_festival_id": "diwali",
        "festival_presets": [
            {"id": "diwali", "name": "Diwali Festival", "percent": 15.0, "icon": "🪔", "active": True},
            {"id": "newyear", "name": "New Year Special", "percent": 20.0, "icon": "🎉", "active": True},
            {"id": "eid", "name": "Eid Mubarak", "percent": 15.0, "icon": "🌙", "active": True},
            {"id": "christmas", "name": "Christmas Special", "percent": 20.0, "icon": "🎄", "active": True},
            {"id": "weekend", "name": "Weekend Happy Hours", "percent": 10.0, "icon": "⭐", "active": True},
            {"id": "anniversary", "name": "Anniversary Discount", "percent": 25.0, "icon": "🎂", "active": True}
        ]
    }
}


def get_config(db: Session, tenant_id: str, key: str, branch_id: str | None = None) -> dict:
    """
    Get active configuration for a key. Tries branch-specific first, then falls back to tenant-level.
    """
    # 1. Try branch specific
    if branch_id:
        cfg = (
            db.query(SystemConfiguration)
            .filter(
                SystemConfiguration.tenant_id == tenant_id,
                SystemConfiguration.branch_id == branch_id,
                SystemConfiguration.key == key,
                SystemConfiguration.is_active.is_(True)
            )
            .first()
        )
        if cfg:
            try:
                return json.loads(cfg.value)
            except Exception:
                pass

    # 2. Try tenant default
    cfg = (
        db.query(SystemConfiguration)
        .filter(
            SystemConfiguration.tenant_id == tenant_id,
            SystemConfiguration.branch_id.is_(None),
            SystemConfiguration.key == key,
            SystemConfiguration.is_active.is_(True)
        )
        .first()
    )
    if cfg:
        try:
            return json.loads(cfg.value)
        except Exception:
            pass

    # 3. Fallback to hardcoded defaults
    return DEFAULT_CONFIGS.get(key, {})


def set_config(db: Session, tenant_id: str, key: str, value: dict, branch_id: str | None = None) -> SystemConfiguration:
    """
    Save new configuration value, incrementing version and deactivating the old active version.
    """
    # Find current active version
    q = db.query(SystemConfiguration).filter(
        SystemConfiguration.tenant_id == tenant_id,
        SystemConfiguration.key == key,
        SystemConfiguration.is_active.is_(True)
    )
    if branch_id:
        q = q.filter(SystemConfiguration.branch_id == branch_id)
    else:
        q = q.filter(SystemConfiguration.branch_id.is_(None))
        
    old_active = q.first()
    
    next_version = 1
    if old_active:
        next_version = old_active.version + 1
        old_active.is_active = False
        
    new_cfg = SystemConfiguration(
        id=new_id(),
        tenant_id=tenant_id,
        branch_id=branch_id,
        key=key,
        value=json.dumps(value),
        version=next_version,
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_cfg)
    db.commit()
    db.refresh(new_cfg)
    return new_cfg
