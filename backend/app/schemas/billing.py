from app.schemas.common import CamelModel

class RuleIn(CamelModel):
    name: str
    rate: float

class DiscountIn(CamelModel):
    percent: float
    reason: str

class BillingSummary(CamelModel):
    id: str
    session_id: str
    subtotal: float
    discount_amount: float
    service_charge_amount: float
    tax_amount: float
    total: float
    status: str

class DiscountOut(CamelModel):
    id: str
    bill_id: str
    percent: float
    status: str
    reason: str
