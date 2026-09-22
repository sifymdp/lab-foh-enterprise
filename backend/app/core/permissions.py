"""
Permission system — complete role/permission catalogue for 6-role FOH.

Roles: OWNER | MANAGER | HOST | CASHIER | WAITER | CHEF

OWNER always has every permission.
Every other role gets an explicit set defined in ROLE_PERMISSIONS.

Backward compatible: old helpers (can_edit_floor, can_manage_users,
can_manage_menu, can_manage_reservations, normalize_role) are preserved
so existing routers keep working without modification.
"""

from typing import Any, Literal

Role = Literal[
    "OWNER",
    "MANAGER",
    "HOST",
    "CASHIER",
    "WAITER",
    "CHEF",
    # Kept for backward compat — treated identically to HOST in has_permission()
    "SUPERVISOR",
]


# ---------------------------------------------------------------------------
# Permission catalogue
# ---------------------------------------------------------------------------

# user / role management
PERM_USER_VIEW       = "users.view"
PERM_USER_CREATE     = "users.create"
PERM_USER_UPDATE     = "users.update"
PERM_USER_DEACTIVATE = "users.deactivate"
PERM_USER_DELETE     = "users.delete"   # kept for compat

PERM_ROLES_VIEW   = "roles.view"
PERM_ROLES_CREATE = "roles.create"
PERM_ROLES_UPDATE = "roles.update"

PERM_PERMISSIONS_VIEW   = "permissions.view"
PERM_PERMISSIONS_MANAGE = "permissions.manage"

# table / floor
PERM_TABLE_VIEW   = "tables.view"
PERM_TABLE_MANAGE = "tables.manage"
PERM_TABLE_ASSIGN = "tables.assign"
PERM_FLOOR_EDIT   = "floor.edit"

# booking / reservations
PERM_BOOKING_VIEW   = "booking.view"
PERM_BOOKING_CREATE = "booking.create"
PERM_BOOKING_UPDATE = "booking.update"
PERM_BOOKING_CANCEL = "booking.cancel"
PERM_RESERVATIONS_MANAGE = "reservations.manage"  # legacy alias

# orders
PERM_ORDERS_VIEW    = "orders.view"
PERM_ORDERS_CREATE  = "orders.create"
PERM_ORDERS_UPDATE  = "orders.update"
PERM_ORDERS_CONFIRM = "orders.confirm"
PERM_ORDERS_SERVE   = "orders.serve"

# kitchen
PERM_KITCHEN_VIEW   = "kitchen.view"
PERM_KITCHEN_UPDATE = "kitchen.update"
PERM_KITCHEN_MANAGE = "kitchen.manage"

# KDS (Kitchen Display System)
PERM_KDS_VIEW     = "kds.view"
PERM_KDS_BUMP     = "kds.bump"
PERM_KDS_RECALL   = "kds.recall"
PERM_KDS_PRIORITY = "kds.priority"

# billing
PERM_BILLING_VIEW   = "billing.view"
PERM_BILLING_CREATE = "billing.create"
PERM_BILLING_UPDATE = "billing.update"
PERM_BILLING_CANCEL = "billing.cancel"

# discount
PERM_DISCOUNT_APPLY   = "discount.apply"
PERM_DISCOUNT_APPROVE = "discount.approve"

# payment
PERM_PAYMENT_VIEW    = "payment.view"
PERM_PAYMENT_CREATE  = "payment.create"
PERM_PAYMENT_REFUND  = "payment.refund"
PERM_PAYMENT_APPROVE = "payment.approve"

# revenue / reports
PERM_REVENUE_VIEW_OWN    = "revenue.view_own"
PERM_REVENUE_VIEW_BRANCH = "revenue.view_branch"
PERM_REVENUE_VIEW_ALL    = "revenue.view_all"
PERM_REPORTS_VIEW        = "reports.view"
PERM_REPORTS_EXPORT      = "reports.export"

# audit
PERM_AUDIT_VIEW = "audit.view"

# cashier shift
PERM_SHIFT_START = "cashier.shift.start"
PERM_SHIFT_END   = "cashier.shift.end"
PERM_SHIFT_VIEW  = "cashier.shift.view"

# menu
PERM_MENU_MANAGE = "menu.manage"

# cctv / camera vision
PERM_CAMERA_VIEW          = "camera.view"
PERM_CAMERA_ANALYTICS     = "camera.analytics.view"
PERM_CAMERA_CONFIGURATION = "camera.configuration"
PERM_CAMERA_CALIBRATION   = "camera.calibration"
PERM_CAMERA_OVERRIDE      = "camera.override"

ALL_PERMISSIONS = {
    PERM_USER_VIEW, PERM_USER_CREATE, PERM_USER_UPDATE, PERM_USER_DEACTIVATE, PERM_USER_DELETE,
    PERM_ROLES_VIEW, PERM_ROLES_CREATE, PERM_ROLES_UPDATE,
    PERM_PERMISSIONS_VIEW, PERM_PERMISSIONS_MANAGE,
    PERM_TABLE_VIEW, PERM_TABLE_MANAGE, PERM_TABLE_ASSIGN, PERM_FLOOR_EDIT,
    PERM_BOOKING_VIEW, PERM_BOOKING_CREATE, PERM_BOOKING_UPDATE, PERM_BOOKING_CANCEL,
    PERM_RESERVATIONS_MANAGE,
    PERM_ORDERS_VIEW, PERM_ORDERS_CREATE, PERM_ORDERS_UPDATE, PERM_ORDERS_CONFIRM, PERM_ORDERS_SERVE,
    PERM_KITCHEN_VIEW, PERM_KITCHEN_UPDATE, PERM_KITCHEN_MANAGE,
    PERM_KDS_VIEW, PERM_KDS_BUMP, PERM_KDS_RECALL, PERM_KDS_PRIORITY,
    PERM_BILLING_VIEW, PERM_BILLING_CREATE, PERM_BILLING_UPDATE, PERM_BILLING_CANCEL,
    PERM_DISCOUNT_APPLY, PERM_DISCOUNT_APPROVE,
    PERM_PAYMENT_VIEW, PERM_PAYMENT_CREATE, PERM_PAYMENT_REFUND, PERM_PAYMENT_APPROVE,
    PERM_REVENUE_VIEW_OWN, PERM_REVENUE_VIEW_BRANCH, PERM_REVENUE_VIEW_ALL,
    PERM_REPORTS_VIEW, PERM_REPORTS_EXPORT,
    PERM_AUDIT_VIEW,
    PERM_SHIFT_START, PERM_SHIFT_END, PERM_SHIFT_VIEW,
    PERM_MENU_MANAGE,
    PERM_CAMERA_VIEW, PERM_CAMERA_ANALYTICS, PERM_CAMERA_CONFIGURATION, PERM_CAMERA_CALIBRATION, PERM_CAMERA_OVERRIDE,
}


# ---------------------------------------------------------------------------
# Role → permission mapping
# ---------------------------------------------------------------------------
# OWNER always has every permission (handled separately in has_permission).
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "MANAGER": {
        # Staff management (own branch)
        PERM_USER_VIEW, PERM_USER_UPDATE, PERM_USER_DEACTIVATE,
        PERM_ROLES_VIEW,
        # Tables & floor
        PERM_TABLE_VIEW, PERM_TABLE_MANAGE, PERM_TABLE_ASSIGN, PERM_FLOOR_EDIT,
        # Bookings
        PERM_BOOKING_VIEW, PERM_BOOKING_UPDATE, PERM_BOOKING_CANCEL,
        PERM_RESERVATIONS_MANAGE,
        # Orders
        PERM_ORDERS_VIEW, PERM_ORDERS_CONFIRM, PERM_ORDERS_SERVE,
        # Kitchen
        PERM_KITCHEN_VIEW, PERM_KITCHEN_MANAGE,
        PERM_KDS_VIEW, PERM_KDS_BUMP, PERM_KDS_RECALL, PERM_KDS_PRIORITY,
        # Billing
        PERM_BILLING_VIEW, PERM_BILLING_CREATE, PERM_BILLING_UPDATE, PERM_BILLING_CANCEL,
        PERM_DISCOUNT_APPLY, PERM_DISCOUNT_APPROVE,
        # Payments
        PERM_PAYMENT_VIEW, PERM_PAYMENT_CREATE, PERM_PAYMENT_REFUND, PERM_PAYMENT_APPROVE,
        # Revenue
        PERM_REVENUE_VIEW_BRANCH,
        PERM_REPORTS_VIEW, PERM_REPORTS_EXPORT,
        # Audit
        PERM_AUDIT_VIEW,
        # Shift
        PERM_SHIFT_START, PERM_SHIFT_END, PERM_SHIFT_VIEW,
        # Menu
        PERM_MENU_MANAGE,
        # Camera & Vision
        PERM_CAMERA_VIEW, PERM_CAMERA_ANALYTICS, PERM_CAMERA_CONFIGURATION, PERM_CAMERA_CALIBRATION, PERM_CAMERA_OVERRIDE,
    },
    "HOST": {
        # Host: front-of-house seating operations ONLY
        PERM_TABLE_VIEW, PERM_TABLE_ASSIGN,
        PERM_BOOKING_VIEW,
        PERM_RESERVATIONS_MANAGE,
        PERM_ORDERS_VIEW,
        # Camera view & overrides for table seating verification
        PERM_CAMERA_VIEW, PERM_CAMERA_OVERRIDE,
    },
    # SUPERVISOR is kept as a backward-compat alias for HOST
    "SUPERVISOR": {
        PERM_TABLE_VIEW, PERM_TABLE_ASSIGN,
        PERM_BILLING_VIEW, PERM_BILLING_CREATE, PERM_BILLING_UPDATE,
        PERM_DISCOUNT_APPLY, PERM_DISCOUNT_APPROVE,
        PERM_PAYMENT_VIEW, PERM_PAYMENT_CREATE,
        PERM_RESERVATIONS_MANAGE,
    },
    "CASHIER": {
        # Billing
        PERM_BILLING_VIEW, PERM_BILLING_CREATE, PERM_BILLING_UPDATE,
        PERM_DISCOUNT_APPLY,
        # Payments
        PERM_PAYMENT_VIEW, PERM_PAYMENT_CREATE, PERM_PAYMENT_REFUND,
        # Tables (view only)
        PERM_TABLE_VIEW,
        # Own revenue
        PERM_REVENUE_VIEW_OWN,
        PERM_REPORTS_VIEW,
        # Shift management
        PERM_SHIFT_START, PERM_SHIFT_END, PERM_SHIFT_VIEW,
    },
    "WAITER": {
        PERM_TABLE_VIEW,
        PERM_ORDERS_VIEW, PERM_ORDERS_CREATE, PERM_ORDERS_UPDATE, PERM_ORDERS_SERVE,
        PERM_BILLING_VIEW,
        PERM_DISCOUNT_APPLY,
    },
    "CHEF": {
        # Kitchen — full visibility and management
        PERM_KITCHEN_VIEW, PERM_KITCHEN_UPDATE, PERM_KITCHEN_MANAGE,
        # KDS
        PERM_KDS_VIEW, PERM_KDS_BUMP, PERM_KDS_RECALL, PERM_KDS_PRIORITY,
        PERM_ORDERS_VIEW, PERM_ORDERS_CONFIRM,
        PERM_TABLE_VIEW,
    },
}

# ---------------------------------------------------------------------------
# Discount limits per role — enforced server-side
# ---------------------------------------------------------------------------
MAX_DISCOUNT_PERCENT_BY_ROLE: dict[str, float] = {
    "OWNER":      100.0,
    "MANAGER":     30.0,
    "SUPERVISOR":  15.0,
    "CASHIER":      5.0,
    "WAITER":       5.0,
    "HOST":         0.0,
    "CHEF":         0.0,
}



from sqlalchemy.orm import Session

def normalize_role(role: str) -> str:
    return role.strip().upper()


def has_permission(role: str, permission: str) -> bool:
    r = normalize_role(role)
    if r == "OWNER":
        return True
    return permission in ROLE_PERMISSIONS.get(r, set())


def has_user_permission(db: Session, user, permission: str) -> bool:
    """
    Dynamic effective permission calculator. Checks:
    1. Owner override (always True)
    2. Temporary permissions (valid end_time >= now)
    3. Direct user permission override
    4. Database role permission mapping (custom or customized default roles)
    5. Fallback to static ROLE_PERMISSIONS mapping
    """
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.user_permission import UserPermission
    from app.models.temporary_permission import TemporaryPermission
    from datetime import datetime, timezone

    # 1. OWNER always has all permissions
    r = normalize_role(user.role)
    if r == "OWNER":
        return True

    # 2. Check active temporary permissions
    now = datetime.now(timezone.utc)
    temp_exists = (
        db.query(TemporaryPermission)
        .filter(
            TemporaryPermission.user_id == user.id,
            TemporaryPermission.permission == permission,
            TemporaryPermission.start_time <= now,
            TemporaryPermission.end_time >= now,
            TemporaryPermission.status == "ACTIVE",
        )
        .first()
    )
    if temp_exists:
        return True

    # 3. Check direct user permissions
    direct_exists = (
        db.query(UserPermission)
        .filter(
            UserPermission.user_id == user.id,
            UserPermission.permission == permission,
        )
        .first()
    )
    if direct_exists:
        return True

    # 4. Check DB role permissions
    from sqlalchemy import func
    db_role = (
        db.query(Role)
        .filter(
            func.upper(Role.name) == r,
        )
        .first()
    )
    if db_role:
        role_perm_exists = (
            db.query(RolePermission)
            .filter(
                RolePermission.role_id == db_role.id,
                RolePermission.permission == permission,
            )
            .first()
        )
        return role_perm_exists is not None

    # 5. Fallback to static mapping ONLY if role is completely missing from DB
    return permission in ROLE_PERMISSIONS.get(r, set())


def get_max_discount_percent(role: str) -> float:
    """Server-side ceiling for a role's self-applied discount."""
    return MAX_DISCOUNT_PERCENT_BY_ROLE.get(normalize_role(role), 0.0)


def discount_requires_approval(role: str, requested_percent: float) -> bool:
    return requested_percent > get_max_discount_percent(role)



# ---------------------------------------------------------------------------
# Backward-compatible helpers
# ---------------------------------------------------------------------------
def can_edit_floor(role: str) -> bool:
    return has_permission(role, PERM_FLOOR_EDIT) or normalize_role(role) in ("OWNER", "MANAGER")


def can_manage_users(role: str) -> bool:
    return normalize_role(role) == "OWNER"


def can_manage_menu(role: str) -> bool:
    return has_permission(role, PERM_MENU_MANAGE) or normalize_role(role) in ("OWNER", "MANAGER")


def can_manage_reservations(role: str) -> bool:
    return has_permission(role, PERM_RESERVATIONS_MANAGE) or normalize_role(role) in (
        "OWNER", "MANAGER", "HOST", "SUPERVISOR",
    )


def require_permission(permission: str, user: Any, db: Session) -> None:
    from fastapi import HTTPException
    if not has_user_permission(db, user, permission):
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied. Required: '{permission}'",
        )

