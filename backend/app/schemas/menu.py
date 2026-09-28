from app.schemas.common import CamelModel


class MenuItemOut(CamelModel):
    id: str
    name: str
    description: str | None = None
    price: float
    category: str
    available: bool
    display_order: int
    station: str | None = None
    item_code: str | None = None
    tax_rate: float = 5.0
    service_charge: float = 0.0
    dietary_type: str = "VEG"
    prep_time_minutes: int = 15
    modifiers: str | None = None
    allergens: str | None = None
    is_active: bool = True


class MenuItemCreate(CamelModel):
    name: str
    description: str | None = None
    price: float
    category: str
    available: bool = True
    display_order: int = 0
    station: str | None = None
    item_code: str | None = None
    tax_rate: float = 5.0
    service_charge: float = 0.0
    dietary_type: str = "VEG"
    prep_time_minutes: int = 15
    modifiers: str | None = None
    allergens: str | None = None


class MenuItemUpdate(CamelModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None
    category: str | None = None
    available: bool | None = None
    display_order: int | None = None
    station: str | None = None
    item_code: str | None = None
    tax_rate: float | None = None
    service_charge: float | None = None
    dietary_type: str | None = None
    prep_time_minutes: int | None = None
    modifiers: str | None = None
    allergens: str | None = None
    is_active: bool | None = None
