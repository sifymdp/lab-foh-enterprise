from app.schemas.common import CamelModel


class UserOut(CamelModel):
    id: str
    name: str
    email: str
    role: str
    status: str
    is_active: bool
    branch_id: str | None = None


class CreateUserIn(CamelModel):
    name: str
    email: str
    password: str
    role: str
    branch_id: str | None = None
    status: str = "ACTIVE"
    phone: str | None = None


class UpdateUserIn(CamelModel):
    name: str
    email: str
    role: str
    status: str
    branch_id: str | None = None


class SetActiveIn(CamelModel):
    is_active: bool

