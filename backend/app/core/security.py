from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


import uuid

def create_access_token(user_id: str, tenant_id: str | None = None, branch_id: str | None = None, role: str | None = None) -> tuple[str, str]:
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": user_id, "exp": expires, "jti": uuid.uuid4().hex}
    if tenant_id:
        payload["tenant_id"] = tenant_id
    if branch_id:
        payload["branch_id"] = branch_id
    if role:
        payload["role"] = role
    token = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    return token, expires.isoformat()


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        return user_id if isinstance(user_id, str) else None
    except JWTError:
        return None


def create_customer_access_token(email: str) -> tuple[str, str]:
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.customer_session_expire_hours)
    payload = {"sub": email, "kind": "customer", "exp": expires, "jti": uuid.uuid4().hex}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), expires.isoformat()


def decode_customer_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        email = payload.get("sub")
        return email if payload.get("kind") == "customer" and isinstance(email, str) else None
    except JWTError:
        return None
