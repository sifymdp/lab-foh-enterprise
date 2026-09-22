from app.schemas.common import CamelModel


class MenuItemOut(CamelModel):
    id: str
    name: str
    description: str | None = None
    price: float
    category: str
    available: bool
    display_order: int


class MenuItemCreate(CamelModel):
    name: str
    description: str | None = None
    price: float
    category: str
    available: bool = True
    display_order: int = 0


class MenuItemUpdate(CamelModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None
    category: str | None = None
    available: bool | None = None
    display_order: int | None = None
