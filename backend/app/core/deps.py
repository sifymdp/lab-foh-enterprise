from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.permissions import (
    has_user_permission,
    normalize_role,
)
from app.core.security import decode_token, decode_customer_token
from app.database import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_customer_email(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> str:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Customer login required")
    email = decode_customer_token(credentials.credentials)
    if email:
        return email
    user_id = decode_token(credentials.credentials)
    if user_id:
        user = db.get(User, user_id)
        if user and user.is_active:
            return user.email
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Customer login required")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    token_str = credentials.credentials
    user_id = decode_token(token_str)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        
    # Check session status in database
    from app.models.user_session import UserSession
    from datetime import datetime, timezone
    session_record = db.query(UserSession).filter(UserSession.token == token_str).first()
    
    # If session is revoked or expired, reject
    if not session_record or session_record.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or forced logout")
        
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        
    # Inactive or suspended users must not be allowed to authenticate
    if not user.is_active or user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive or suspended"
        )
        
    # Update last activity
    session_record.last_activity = datetime.now(timezone.utc)
    db.commit()
    
    return user


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if not credentials or not credentials.credentials:
        return None
    try:
        token_str = credentials.credentials
        user_id = decode_token(token_str)
        if not user_id:
            return None
        user = db.get(User, user_id)
        if not user or not user.is_active or user.status != "ACTIVE":
            return None
        return user
    except Exception:
        return None



def get_user_branches(db: Session, user: User) -> list[str] | None:
    """
    Returns the list of branch IDs the user has access to.
    Returns None if the user has access to all branches (e.g. Owner or organization-wide manager).
    """
    from app.models.user_branch import UserBranch
    
    # OWNER has access to all branches
    if user.role.upper() == "OWNER":
        return None
        
    # If primary branch is None and they are manager/owner, they get org-wide access
    if not user.branch_id and user.role.upper() == "MANAGER":
        return None
        
    branches = []
    if user.branch_id:
        branches.append(user.branch_id)
        
    # Retrieve explicitly mapped branches from user_branches mapping table
    user_branches = db.query(UserBranch).filter(UserBranch.user_id == user.id).all()
    for ub in user_branches:
        if ub.branch_id not in branches:
            branches.append(ub.branch_id)
            
    # Fallback to single branch filter if set, else org-wide if empty
    if not branches:
        return None
        
    return branches


def require_floor_editor(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not has_user_permission(db, user, "floor.edit") and not has_user_permission(db, user, "tables.manage"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Floor edit not allowed")
    return user


def require_owner(user: User = Depends(get_current_user)) -> User:
    if normalize_role(user.role) != "OWNER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner access required")
    return user


def require_manager_or_owner(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if normalize_role(user.role) not in ("OWNER", "MANAGER") and not has_user_permission(db, user, "users.view"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager access required")
    return user


def require_menu_manager(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not has_user_permission(db, user, "menu.manage"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Menu management not allowed")
    return user


def require_reservations_access(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not has_user_permission(db, user, "booking.view") and not has_user_permission(db, user, "reservations.manage"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reservations access not allowed")
    return user


def require_kitchen_access(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if normalize_role(user.role) not in ("OWNER", "MANAGER", "CHEF", "WAITER") and not has_user_permission(db, user, "kitchen.view"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Kitchen access not allowed")
    return user


def require_permission(permission: str):
    """Dependency factory for the new permission system.

    Usage in a router:
        @router.post("/bills/{id}/discount-request")
        def request_discount(..., user: User = Depends(require_permission(PERM_DISCOUNT_APPLY))):
            ...
    """

    def _check(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if not has_user_permission(db, user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission}",
            )
        return user

    return _check

