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
        available=item.available,
        display_order=item.display_order,
    )


def list_available_models(db: Session) -> list[MenuItem]:
    return (
        db.query(MenuItem)
        .filter(MenuItem.available.is_(True))
        .order_by(MenuItem.category, MenuItem.display_order)
        .all()
    )


def list_available(db: Session) -> list[MenuItemOut]:
    return [_to_out(r) for r in list_available_models(db)]


def list_all(db: Session) -> list[MenuItemOut]:
    rows = db.query(MenuItem).order_by(MenuItem.category, MenuItem.display_order).all()
    return [_to_out(r) for r in rows]


def create_item(db: Session, payload: MenuItemCreate) -> MenuItemOut:
    item = MenuItem(
        id=new_id(),
        name=payload.name,
        description=payload.description,
        price=payload.price,
        category=payload.category,
        available=payload.available,
        display_order=payload.display_order,
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
    from fastapi import HTTPException, status

    item = db.get(MenuItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
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
