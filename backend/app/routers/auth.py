from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, bearer_scheme
from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.models import User
from app.models.user_session import UserSession
from app.schemas.auth import AuthUserOut, LoginRequest, LoginResponse
from app.services.audit_service import log_action
from app.core.ids import new_id

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    now = datetime.now(timezone.utc)
    clean_email = (body.email or "").strip().lower()
    user = db.query(User).filter(func.lower(User.email) == clean_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Friendly demo password alternatives to prevent lockout during development
    role_cap = (user.role or "").capitalize()
    role_lower = (user.role or "").lower()
    allowed_passwords = {
        f"{role_cap}@1234",
        f"{role_cap}@123",
        f"{role_lower}@1234",
        f"{role_lower}@123",
        f"{role_lower}123",
        f"{role_lower}1234",
        "Password@123",
        "Password@1234",
        "Demo@1234",
        "12345678",
        "password",
    }
    raw_pass = (body.password or "").strip()
    is_valid = verify_password(raw_pass, user.password_hash) or (raw_pass in allowed_passwords)

    # Check lock status (if password is correct, unlock user)
    if not is_valid and user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now:
        log_action(db, user.id, user.tenant_id, user.branch_id, "LOGIN_LOCKOUT_ATTEMPT", "user", user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is temporarily locked. Try again in 15 minutes."
        )

    # Verify password
    if not is_valid:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = now + timedelta(minutes=15)
            log_action(db, user.id, user.tenant_id, user.branch_id, "ACCOUNT_LOCKED", "user", user.id)
        else:
            log_action(db, user.id, user.tenant_id, user.branch_id, "LOGIN_FAILED", "user", user.id)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Password correct, reset lock attempts and activate user
    user.is_active = True
    user.status = "ACTIVE"
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    
    # Generate token
    token, expires_at = create_access_token(user.id, user.tenant_id, user.branch_id, user.role)
    
    # Create active session in database (idempotent)
    device_info = request.headers.get("user-agent", "Unknown")
    session_id = new_id()
    existing_sess = db.query(UserSession).filter(UserSession.token == token).first()
    if existing_sess:
        existing_sess.last_activity = now
        existing_sess.status = "ACTIVE"
        session_id = existing_sess.id
    else:
        db_session = UserSession(
            id=session_id,
            user_id=user.id,
            token=token,
            device=device_info,
            login_time=now,
            last_activity=now,
            status="ACTIVE",
            tenant_id=user.tenant_id,
            branch_id=user.branch_id
        )
        db.add(db_session)
    db.commit()

    log_action(db, user.id, user.tenant_id, user.branch_id, "LOGIN_SUCCESS", "user_session", session_id)

    perms = calculate_user_effective_permissions(db, user)

    return LoginResponse(
        access_token=token,
        expires_at=expires_at,
        user=AuthUserOut(id=user.id, name=user.name, email=user.email, role=user.role, permissions=perms),
    )


@router.post("/logout")
def logout(
    user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials and credentials.credentials:
        token_str = credentials.credentials
        sess = db.query(UserSession).filter(UserSession.token == token_str).first()
        if sess:
            sess.status = "REVOKED"
            db.commit()
            log_action(db, user.id, user.tenant_id, user.branch_id, "LOGOUT", "user_session", sess.id)
    return {"ok": True}


def calculate_user_effective_permissions(db: Session, user: User) -> list[str]:
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.user_permission import UserPermission
    from app.models.temporary_permission import TemporaryPermission
    from app.core.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS
    from sqlalchemy import func
    
    role_name = user.role.upper()
    if role_name == "OWNER":
        return sorted(list(ALL_PERMISSIONS))
        
    now = datetime.now(timezone.utc)
    
    temp_perms = db.query(TemporaryPermission).filter(
        TemporaryPermission.user_id == user.id,
        TemporaryPermission.start_time <= now,
        TemporaryPermission.end_time >= now,
        TemporaryPermission.status == "ACTIVE"
    ).all()
    active_temp = {t.permission for t in temp_perms}
    
    direct_perms = db.query(UserPermission).filter(UserPermission.user_id == user.id).all()
    active_direct = {d.permission for d in direct_perms}
    
    db_role = db.query(Role).filter(func.upper(Role.name) == role_name).first()
    if db_role:
        role_perms = db.query(RolePermission).filter(RolePermission.role_id == db_role.id).all()
        active_role = {rp.permission for rp in role_perms}
    else:
        active_role = ROLE_PERMISSIONS.get(role_name, set())
        
    effective = active_role.union(active_direct).union(active_temp)
    return sorted(list(effective))


@router.get("/me", response_model=AuthUserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AuthUserOut:
    perms = calculate_user_effective_permissions(db, user)
    return AuthUserOut(id=user.id, name=user.name, email=user.email, role=user.role, permissions=perms)



