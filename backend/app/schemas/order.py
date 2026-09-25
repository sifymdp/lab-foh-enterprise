from app.schemas.common import CamelModel


class OrderItemIn(CamelModel):
    menu_item_id: str
    quantity: int = 1
    notes: str | None = None


class OrderCreate(CamelModel):
    table_id: str | None = None
    session_id: str | None = None
    items: list[OrderItemIn]
    source: str | None = "bot"
    approval_status: str | None = "PENDING"
    notes: str | None = None


class OrderItemOut(CamelModel):
    id: str
    item_name: str
    unit_price: float
    quantity: int
    station: str | None = None
    notes: str | None = None
    allergy_flag: bool = False
    item_status: str = "RECEIVED"


class OrderOut(CamelModel):
    id: str
    session_id: str
    table_id: str
    table_number: str | None = None
    placed_at: str
    status: str
    source: str = "bot"
    approval_status: str = "PENDING"
    notes: str | None = None
    items: list[OrderItemOut]


class BillItemOut(CamelModel):
    item_name: str
    unit_price: float
    quantity: int
    line_total: float


class BillOut(CamelModel):
    id: str
    session_id: str
    subtotal: float
    total: float
    status: str
    generated_at: str
    paid_at: str | None = None
    items: list[BillItemOut]
