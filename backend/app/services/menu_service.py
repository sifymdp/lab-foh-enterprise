from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.models import MenuItem
from app.schemas.menu import MenuItemCreate, MenuItemOut, MenuItemUpdate


def _to_out(item: MenuItem) -> MenuItemOut:
    return MenuItemOut(
        id=item.id,
        name=item.name,
        description=item.description,
        price=float(item.price),
        category=item.category,
        available=bool(item.available),
        display_order=item.display_order,
        station=item.station,
        item_code=getattr(item, "item_code", None),
        tax_rate=float(getattr(item, "tax_rate", 5.0) or 5.0),
        service_charge=float(getattr(item, "service_charge", 0.0) or 0.0),
        dietary_type=getattr(item, "dietary_type", "VEG") or "VEG",
        prep_time_minutes=int(getattr(item, "prep_time_minutes", 15) or 15),
        modifiers=getattr(item, "modifiers", None),
        allergens=getattr(item, "allergens", None),
        is_active=bool(getattr(item, "is_active", True)),
    )


def list_available_models(db: Session, branch_id: str | None = None) -> list[MenuItem]:
    q = db.query(MenuItem).filter(
        MenuItem.available.is_(True),
        MenuItem.is_active.is_(True),
    )
    if branch_id:
        q = q.filter((MenuItem.branch_id == branch_id) | (MenuItem.branch_id.is_(None)))
    return q.order_by(MenuItem.category, MenuItem.display_order).all()


def list_available(db: Session, branch_id: str | None = None) -> list[MenuItemOut]:
    return [_to_out(r) for r in list_available_models(db, branch_id=branch_id)]


def list_all(db: Session, branch_id: str | None = None, include_inactive: bool = False) -> list[MenuItemOut]:
    q = db.query(MenuItem)
    if not include_inactive:
        q = q.filter(MenuItem.is_active.is_(True))
    if branch_id:
        q = q.filter((MenuItem.branch_id == branch_id) | (MenuItem.branch_id.is_(None)))
    rows = q.order_by(MenuItem.category, MenuItem.display_order).all()
    return [_to_out(r) for r in rows]


def create_item(db: Session, payload: MenuItemCreate, tenant_id: str | None = None, branch_id: str | None = None) -> MenuItemOut:
    data = payload.model_dump(exclude_unset=True, by_alias=False)
    item = MenuItem(
        id=new_id(),
        name=payload.name,
        description=payload.description,
        price=payload.price,
        category=payload.category,
        available=payload.available,
        display_order=payload.display_order,
        station=payload.station,
        item_code=payload.item_code,
        tax_rate=payload.tax_rate,
        service_charge=payload.service_charge,
        dietary_type=payload.dietary_type,
        prep_time_minutes=payload.prep_time_minutes,
        modifiers=payload.modifiers,
        allergens=payload.allergens,
        is_active=True,
        tenant_id=tenant_id,
        branch_id=branch_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(item)


def update_item(db: Session, item_id: str, payload: MenuItemUpdate) -> MenuItemOut:
    from fastapi import HTTPException, status

    item = db.get(MenuItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    data = payload.model_dump(exclude_unset=True, by_alias=False)
    for key, val in data.items():
        setattr(item, key, val)
    db.commit()
    db.refresh(item)
    return _to_out(item)


def delete_item(db: Session, item_id: str) -> None:
    """Soft delete if historical orders exist, otherwise physical delete."""
    from fastapi import HTTPException, status
    from app.models.order_item import OrderItem

    item = db.get(MenuItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")

    has_orders = db.query(OrderItem).filter(OrderItem.menu_item_id == item_id).first() is not None
    if has_orders:
        item.is_active = False
        item.available = False
    else:
        db.delete(item)
    db.commit()


def toggle_item(db: Session, item_id: str) -> MenuItemOut:
    from fastapi import HTTPException, status

    item = db.get(MenuItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    item.available = not item.available
    db.commit()
    db.refresh(item)
    return _to_out(item)
