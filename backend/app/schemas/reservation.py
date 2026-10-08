from app.schemas.common import CamelModel


class ReservationOut(CamelModel):
    id: str
    table_id: str
    guest_name: str
    party_size: int
    reserved_for: str
    reserved_until: str
    status: str
    notes: str | None = None


class ReservationCreate(CamelModel):
    table_id: str
    guest_name: str
    party_size: int
    reserved_for: str
    reserved_until: str
    notes: str | None = None
