from app.schemas.common import CamelModel


class DiningSessionOut(CamelModel):
    id: str
    table_id: str
    guest_name: str | None = None
    party_size: int
    seated_at: str
    status: str


class SeatGuestIn(CamelModel):
    table_id: str
    party_size: int
    guest_name: str | None = None
