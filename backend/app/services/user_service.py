import time

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User
from app.schemas.user import CreateUserIn, UserOut


import time
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User
from app.schemas.user import CreateUserIn, UpdateUserIn, UserOut



def user_to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        status=user.status,
        is_active=user.is_active,
        branch_id=user.branch_id
    )


def is_last_owner(db: Session, tenant_id: str, user_id: str) -> bool:
    owners = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.role == "OWNER",
        User.status == "ACTIVE",
        User.is_active.is_(True)
    ).all()
    if len(owners) <= 1 and any(o.id == user_id for o in owners):
        return True
    return False


def list_users(db: Session, tenant_id: str | None = None, branch_id: str | None = None) -> list[UserOut]:
    q = db.query(User)
    if tenant_id:
        q = q.filter((User.tenant_id == tenant_id) | (User.tenant_id.is_(None)))
    users = q.order_by(User.name).all()
    return [user_to_out(u) for u in users]


def create_user(
    db: Session,
    payload: CreateUserIn,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> UserOut:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
        
    user = User(
        id=f"u-{int(time.time() * 1000)}" if "time" in globals() else f"u-{new_id()}" if "new_id" in globals() else f"u-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        name=payload.name,
        email=payload.email,
        role=payload.role,
        status=payload.status.upper(),
        password_hash=hash_password(payload.password),
        is_active=(payload.status.upper() == "ACTIVE"),
        tenant_id=tenant_id,
        branch_id=payload.branch_id or branch_id,
        created_at=datetime.now(timezone.utc)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user_to_out(user)


def update_user(
    db: Session,
    user_id: str,
    payload: UpdateUserIn,
    tenant_id: str,
) -> UserOut:
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    # Check if changing role or status violates Owner Safety rule
    if user.role.upper() == "OWNER" and payload.role.upper() != "OWNER":
        if is_last_owner(db, tenant_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last active Owner of the organization."
            )
            
    if payload.status.upper() != "ACTIVE" and user.status == "ACTIVE":
        if is_last_owner(db, tenant_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate or suspend the last active Owner of the organization."
            )
            
    user.name = payload.name
    user.email = payload.email
    user.role = payload.role
    user.status = payload.status.upper()
    user.is_active = (user.status == "ACTIVE")
    user.branch_id = payload.branch_id
    db.commit()
    db.refresh(user)
    return user_to_out(user)


def set_user_active(
    db: Session,
    user_id: str,
    is_active: bool,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> UserOut:
    q = db.query(User).filter(User.id == user_id)
    if tenant_id:
        q = q.filter(User.tenant_id == tenant_id)
    if branch_id:
        q = q.filter(User.branch_id == branch_id)
    user = q.first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    if not is_active and user.is_active:
        if is_last_owner(db, tenant_id or user.tenant_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last active Owner of the organization."
            )
            
    user.is_active = is_active
    user.status = "ACTIVE" if is_active else "INACTIVE"
    db.commit()
    db.refresh(user)
    return user_to_out(user)

