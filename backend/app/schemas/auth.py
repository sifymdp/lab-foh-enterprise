from app.schemas.common import CamelModel


class LoginRequest(CamelModel):
    email: str
    password: str


class AuthUserOut(CamelModel):
    id: str
    name: str
    email: str
    role: str
    permissions: list[str] = []



class LoginResponse(CamelModel):
    access_token: str
    expires_at: str
    user: AuthUserOut
