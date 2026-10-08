from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.user import CreateUserIn, SetActiveIn, UserOut, UpdateUserIn
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def get_users(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("users.view")),
) -> list[UserOut]:
    return user_service.list_users(db, user.tenant_id, user.branch_id)


@router.post("", response_model=UserOut)
def create_user(
    body: CreateUserIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("users.create")),
) -> UserOut:
    branch_id = body.branch_id if user.role.upper() == "OWNER" else user.branch_id
    return user_service.create_user(db, body, user.tenant_id, branch_id)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    body: UpdateUserIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("users.update")),
) -> UserOut:
    return user_service.update_user(db, user_id, body, user.tenant_id)


@router.patch("/{user_id}/active", response_model=UserOut)
def set_active(
    user_id: str,
    body: SetActiveIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("users.deactivate")),
) -> UserOut:
    return user_service.set_user_active(db, user_id, body.is_active, user.tenant_id, user.branch_id)


