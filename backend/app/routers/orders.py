"""
Orders Router — supports waiter order creation and kitchen status updates.
Chef/Cook use PATCH /orders/{id}/status for kitchen workflow.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import (
    bearer_scheme,
    get_current_user,
    require_any_permission,
    require_kitchen_access,
    require_permission,
)
from app.core.security import decode_token
from app.core.permissions import (
    PERM_KDS_BUMP,
    PERM_KITCHEN_MANAGE,
    PERM_KITCHEN_UPDATE,
    PERM_KITCHEN_VIEW,
    PERM_ORDERS_CREATE,
    PERM_ORDERS_SERVE,
    PERM_ORDERS_UPDATE,
    PERM_ORDERS_VIEW,
    normalize_role,
)
from app.database import get_db
from app.models import Table, TableQRCode
from app.models.user import User
from app.schemas.order import OrderCreate, OrderOut
from app.services import order_service
from app.services.audit_service import log_action
from app.socket_manager import emit_sync

router = APIRouter(prefix="/orders", tags=["orders"])

# Valid kitchen status transitions by role
KITCHEN_STATUSES = {"RECEIVED", "CONFIRMED", "PREPARING", "READY", "SERVED"}

CHEF_TRANSITIONS = {
    "RECEIVED": ["CONFIRMED", "PREPARING"],
    "CONFIRMED": ["PREPARING"],
    "PREPARING": ["READY"],
    "READY": ["SERVED"],
}

WAITER_TRANSITIONS = {
    "READY": ["SERVED"],
}



class OrderStatusIn(BaseModel):
    status: str
    notes: str | None = None


@router.get("", response_model=list[OrderOut])
def list_orders(
    table_id: str | None = Query(None),
    session_id: str | None = Query(None),
    approval_status: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_ORDERS_VIEW)),
) -> list[OrderOut]:
    return order_service.list_orders(
        db,
        table_id=table_id,
        session_id=session_id,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
        approval_status=approval_status,
    )


@router.get("/kitchen", response_model=list[OrderOut])
def kitchen_orders(
    db: Session = Depends(get_db),
    user: User = Depends(require_kitchen_access),
) -> list[OrderOut]:
    """Kitchen view: all active (non-SERVED) orders for the branch."""
    from app.models.order import Order
    q = (
        db.query(Order)
        .filter(
            Order.tenant_id == user.tenant_id,
            Order.status.in_(["RECEIVED", "CONFIRMED", "PREPARING", "READY"]),
            Order.approval_status == "APPROVED",
        )
    )
    if user.branch_id:
        q = q.filter(Order.branch_id == user.branch_id)
    orders = q.order_by(Order.placed_at.asc()).all()

    from app.services import kitchen_alert_service
    kitchen_alert_service.evaluate_kitchen_alerts(db)

    return [order_service._order_to_out(o, db) for o in orders]


@router.patch("/{order_id}/status", response_model=OrderOut)
def update_order_status(
    order_id: str,
    body: OrderStatusIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_any_permission(PERM_KITCHEN_UPDATE, PERM_ORDERS_UPDATE, PERM_ORDERS_SERVE, PERM_KDS_BUMP, PERM_KITCHEN_MANAGE)),
):
    """Chef/Cook/Waiter updates order status through kitchen workflow."""
    from app.models.order import Order
    from app.services import kitchen_alert_service

    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.tenant_id == user.tenant_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if user.branch_id and order.branch_id and order.branch_id != user.branch_id:
        raise HTTPException(status_code=404, detail="Order not found")

    new_status = body.status.upper()
    if new_status not in KITCHEN_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status. Must be one of: {', '.join(KITCHEN_STATUSES)}",
        )

    role = normalize_role(user.role)
    if role in ("CHEF", "OWNER", "MANAGER", "WAITER", "SUPERVISOR", "HOST"):
        allowed_transitions = CHEF_TRANSITIONS
    else:
        raise HTTPException(status_code=403, detail="You are not allowed to update kitchen order status")


    allowed = allowed_transitions.get(order.status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition from {order.status} to {new_status}. Allowed: {allowed}",
        )

    old_status = order.status
    order.status = new_status
    if hasattr(order, "notes") and body.notes:
        order.notes = body.notes

    # Record timing timestamps & trigger alert lifecycle transitions
    kitchen_alert_service.on_order_status_transition(db, order, new_status)

    db.commit()
    db.refresh(order)

    log_action(
        db, user.id, user.tenant_id, user.branch_id,
        "ORDER_STATUS_CHANGED", "order", order_id,
        old_value={"status": old_status},
        new_value={"status": new_status},
    )

    order_out = order_service._order_to_out(order, db)
    payload = order_out.model_dump(by_alias=True)
    table = db.get(Table, order.table_id) if order.table_id else None

    # Broadcast to all floor rooms and connected clients
    emit_sync(
        "order_status_updated",
        payload,
        room="*",
    )
    emit_sync(
        "order.status.changed",
        {"orderId": order_id, "oldStatus": old_status, "newStatus": new_status, "order": payload},
        room="*",
    )
    if new_status == "READY":
        table_num = table.number if table else (order.table_id or "?")
        emit_sync(
            "food_ready",
            {
                "orderId": order_id,
                "tableId": order.table_id,
                "tableNumber": table_num,
                "order": payload,
                "estimatedServeMinutes": 3,
                "readyAt": order.ready_at.isoformat() if hasattr(order, "ready_at") and order.ready_at else None,
                "message": f"Table {table_num}: Food is READY! Please serve within 3 minutes.",
            },
            room="*",
        )
        emit_sync(
            "ai_alert",
            {
                "eventType": "FOOD_READY",
                "tableId": order.table_id,
                "tableNumber": table_num,
                "message": f"🍽️ Table {table_num} food is READY! Estimate serve time: 3 mins.",
                "estimatedServeMinutes": 3,
            },
            room="*",
        )
    elif new_status == "SERVED":
        emit_sync(
            "order_served",
            {"id": order_id, "orderId": order_id, "order": payload},
            room="*",
        )

    return order_out


@router.post("", response_model=OrderOut)
def place_order(
    body: OrderCreate,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    table_token: str | None = Query(None, alias="token"),
) -> OrderOut:
    current_user = None
    tenant_id = None
    branch_id = None
    if credentials and credentials.credentials:
        user_id = decode_token(credentials.credentials)
        current_user = db.get(User, user_id) if user_id else None
        if not current_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        tenant_id = current_user.tenant_id
        branch_id = current_user.branch_id
        body = body.model_copy(update={"source": "waiter", "approval_status": "APPROVED"})
    elif table_token or body.table_id:
        from app.routers.guest import _resolve_qr
        identifier = table_token or body.table_id
        qr = _resolve_qr(db, identifier)
        table = db.query(Table).filter(Table.id == qr.table_id).first()
        if table:
            tenant_id = table.tenant_id
            branch_id = table.branch_id
        body = body.model_copy(update={"table_id": qr.table_id, "source": "guest", "approval_status": "PENDING"})
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return order_service.create_order(db, body, tenant_id=tenant_id, branch_id=branch_id)


class RejectOrderIn(BaseModel):
    reason: str | None = None


@router.post("/{order_id}/approve", response_model=OrderOut)
def approve_order_endpoint(
    order_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderOut:
    return order_service.approve_order(db, order_id, user_id=user.id)


@router.post("/{order_id}/reject", response_model=OrderOut)
def reject_order_endpoint(
    order_id: str,
    body: RejectOrderIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderOut:
    reason = body.reason if body else None
    return order_service.reject_order(db, order_id, reason=reason, user_id=user.id)
