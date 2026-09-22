from pydantic import BaseModel, Field


class CustomerEmail(BaseModel):
    contact: str = Field(min_length=5, max_length=255)
    email: str | None = None

    @property
    def identity(self) -> str:
        return self.contact.strip().lower()


class CustomerVerify(BaseModel):
    contact: str = Field(min_length=5, max_length=255)
    code: str = Field(min_length=6, max_length=6)


class CustomerAvailability(BaseModel):
    requested_date: str
    requested_time: str
    guests: int = Field(ge=1, le=50)


class CustomerHold(CustomerAvailability):
    table_id: str
    guest_name: str = Field(min_length=1, max_length=120)


class CustomerWaitlist(CustomerAvailability):
    guest_name: str = Field(min_length=1, max_length=120)
