from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_menu_manager
from app.database import get_db
from app.models.user import User
from app.schemas.menu import MenuItemCreate, MenuItemOut, MenuItemUpdate
from app.services import menu_service

router = APIRouter(prefix="/menu", tags=["menu"])


@router.get("", response_model=list[MenuItemOut])
def list_public_menu(db: Session = Depends(get_db)) -> list[MenuItemOut]:
    return menu_service.list_available(db)


@router.get("/all", response_model=list[MenuItemOut])
def list_all_menu(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[MenuItemOut]:
    return menu_service.list_all(db)


@router.post("/items", response_model=MenuItemOut)
def create_menu_item(
    body: MenuItemCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_menu_manager),
) -> MenuItemOut:
    return menu_service.create_item(db, body)


@router.patch("/items/{item_id}", response_model=MenuItemOut)
def update_menu_item(
    item_id: str,
    body: MenuItemUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_menu_manager),
) -> MenuItemOut:
    return menu_service.update_item(db, item_id, body)


@router.delete("/items/{item_id}", status_code=204)
def delete_menu_item(
    item_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_menu_manager),
) -> None:
    menu_service.delete_item(db, item_id)


@router.patch("/items/{item_id}/toggle", response_model=MenuItemOut)
def toggle_menu_item(
    item_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_menu_manager),
) -> MenuItemOut:
    return menu_service.toggle_item(db, item_id)
