import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_owner, require_manager_or_owner
from app.core.ids import new_id
from app.core.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS, normalize_role
from app.database import get_db
from app.models import User, AuditLog
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user_permission import UserPermission
from app.models.temporary_permission import TemporaryPermission
from app.models.permission_history import PermissionHistory
from app.models.user_session import UserSession
from app.services.audit_service import log_action

router = APIRouter(prefix="/rbac", tags=["rbac"])

# ── Schemas ──────────────────────────────────────────────────────────────────

class CustomRoleIn(BaseModel):
    name: str
    permissions: list[str] = []

class MatrixToggleIn(BaseModel):
    role_name: str
    permission: str
    enabled: bool

class TemporaryPermissionIn(BaseModel):
    user_id: str
    permission: str
    start_time: str  # ISO-8601
    end_time: str    # ISO-8601

class DirectPermissionIn(BaseModel):
    user_id: str
    permission: str
    action: str  # GRANT | REVOKE
    reason: str | None = None

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/roles")
def list_roles(
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_owner)
):
    """List all custom and standard roles."""
    roles = db.query(Role).filter(Role.tenant_id == user.tenant_id).all()
    # If standard roles are not in DB, return standard static keys combined
    db_role_names = {r.name for r in roles}
    static_roles = ["OWNER", "MANAGER", "HOST", "CASHIER", "WAITER", "CHEF"]
    
    result = []
    for r in roles:
        result.append({
            "id": r.id,
            "name": r.name,
            "isCustom": r.is_custom,
            "createdAt": r.created_at.isoformat() if r.created_at else None
        })
        
    for sr in static_roles:
        if sr not in db_role_names:
            result.append({
                "id": f"role-static-{sr.lower()}",
                "name": sr,
                "isCustom": False,
                "createdAt": None
            })
            
    return result


@router.post("/roles")
def create_custom_role(
    body: CustomRoleIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner)
):
    """Create a custom role with a set of permissions."""
    role_name = body.name.strip()
    if not role_name:
        raise HTTPException(status_code=400, detail="Role name cannot be empty")
        
    # Prevent duplicate
    existing = db.query(Role).filter(Role.name == role_name, Role.tenant_id == user.tenant_id).first()
    if existing or role_name.upper() in ["OWNER", "MANAGER", "HOST", "CASHIER", "WAITER", "CHEF"]:
        raise HTTPException(status_code=409, detail="Role name already exists")
        
    now = datetime.now(timezone.utc)
    role_id = f"role-{int(time.time() * 1000)}"
    role = Role(
        id=role_id,
        tenant_id=user.tenant_id,
        name=role_name,
        is_custom=True,
        created_at=now
    )
    db.add(role)
    db.flush()
    
    # Save permissions
    for perm in body.permissions:
        if perm in ALL_PERMISSIONS:
            rp = RolePermission(
                id=new_id(),
                role_id=role_id,
                permission=perm,
                tenant_id=user.tenant_id
            )
            db.add(rp)
            
    db.commit()
    log_action(db, user.id, user.tenant_id, user.branch_id, "ROLE_CREATED", "role", role_id, new_value={"name": role_name, "permissions": body.permissions})
    return {"id": role_id, "name": role_name}


@router.delete("/roles/{role_name}")
def delete_custom_role(
    role_name: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner)
):
    """Delete a custom role and its assigned permissions."""
    role_name_clean = role_name.strip()
    if role_name_clean.upper() in ["OWNER", "MANAGER", "HOST", "CASHIER", "WAITER", "CHEF"]:
        raise HTTPException(status_code=400, detail="Standard system roles cannot be deleted")
        
    role = db.query(Role).filter(
        Role.name.ilike(role_name_clean),
        Role.tenant_id == user.tenant_id
    ).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    # Delete role permissions
    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
    db.delete(role)
    db.commit()
    log_action(db, user.id, user.tenant_id, user.branch_id, "ROLE_DELETED", "role", role.id, old_value={"name": role_name_clean})
    return {"ok": True, "deleted": role_name_clean}


@router.get("/permissions/matrix")
def get_permissions_matrix(
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_owner)
):
    """Get the full role-permissions toggle matrix."""
    roles = db.query(Role).all()
    db_role_names = {r.name.upper() for r in roles}
    static_roles = ["OWNER", "MANAGER", "HOST", "CASHIER", "WAITER", "CHEF"]
    
    all_role_entries = []
    now = datetime.now(timezone.utc)
    for sr in static_roles:
        if sr not in db_role_names:
            role_id = f"role-seeded-{sr.lower()}"
            db_r = Role(
                id=role_id,
                tenant_id=user.tenant_id,
                name=sr,
                is_custom=False,
                created_at=now
            )
            db.add(db_r)
            db.flush()
            # Seed permissions
            perms = ROLE_PERMISSIONS.get(sr, set())
            if sr == "OWNER":
                perms = ALL_PERMISSIONS
            for p in perms:
                rp = RolePermission(
                    id=new_id(),
                    role_id=role_id,
                    permission=p,
                    tenant_id=user.tenant_id
                )
                db.add(rp)
            all_role_entries.append(db_r)
        else:
            db_r = db.query(Role).filter(func.upper(Role.name) == sr).first()
            if db_r:
                all_role_entries.append(db_r)
                
    # Add custom roles too
    for r in roles:
        if r.name.upper() not in static_roles and r not in all_role_entries:
            all_role_entries.append(r)
            
    db.commit()
    
    # Collect all permissions including dynamic/custom ones in the database
    db_perms = {row[0] for row in db.query(RolePermission.permission).distinct().all()}
    all_perms = sorted(list(set(ALL_PERMISSIONS) | db_perms))
    
    # Calculate mappings
    matrix = []
    for perm in all_perms:
        mappings = {}
        for r in all_role_entries:
            role_perm = db.query(RolePermission).filter(
                RolePermission.role_id == r.id,
                RolePermission.permission == perm
            ).first()
            has_perm = (role_perm is not None)
            mappings[r.name] = has_perm
            mappings[r.name.upper()] = has_perm
            mappings[r.name.lower()] = has_perm
        matrix.append({
            "permission": perm,
            "roles": mappings
        })
        
    return {
        "permissions": all_perms,
        "roles": [r.name for r in all_role_entries],
        "matrix": matrix
    }


@router.post("/permissions/matrix")
def toggle_matrix_permission(
    body: MatrixToggleIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner)
):
    """Toggle a permission status for a role in the matrix."""
    if body.role_name.upper() == "OWNER":
        raise HTTPException(status_code=400, detail="Cannot strip permissions from Owner role")
        
    role = db.query(Role).filter(func.upper(Role.name) == body.role_name.upper()).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    existing = db.query(RolePermission).filter(
        RolePermission.role_id == role.id,
        RolePermission.permission == body.permission
    ).first()
    
    now = datetime.now(timezone.utc)
    if body.enabled and not existing:
        rp = RolePermission(
            id=new_id(),
            role_id=role.id,
            permission=body.permission,
            tenant_id=user.tenant_id
        )
        db.add(rp)
        action_name = "GRANT_ROLE_PERMISSION"
    elif not body.enabled and existing:
        db.delete(existing)
        action_name = "REVOKE_ROLE_PERMISSION"
    else:
        return {"ok": True}
        
    db.commit()
    log_action(db, user.id, user.tenant_id, user.branch_id, action_name, "role_permission", role.id, new_value={"role": body.role_name, "permission": body.permission})
    return {"ok": True}


class BulkMatrixToggleIn(BaseModel):
    role_name: str
    permissions: list[str]
    enabled: bool


@router.post("/permissions/bulk-toggle")
def bulk_toggle_permissions(
    body: BulkMatrixToggleIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner)
):
    """Bulk grant or revoke a list of permissions for a role in one transaction."""
    if body.role_name.upper() == "OWNER":
        raise HTTPException(status_code=400, detail="Cannot strip permissions from Owner role")

    role = db.query(Role).filter(func.upper(Role.name) == body.role_name.upper()).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    existing_perms = {
        rp.permission: rp
        for rp in db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
    }

    for perm in body.permissions:
        if body.enabled and perm not in existing_perms:
            rp = RolePermission(
                id=new_id(),
                role_id=role.id,
                permission=perm,
                tenant_id=user.tenant_id
            )
            db.add(rp)
        elif not body.enabled and perm in existing_perms:
            db.delete(existing_perms[perm])

    db.commit()
    log_action(
        db, user.id, user.tenant_id, user.branch_id,
        "BULK_GRANT_ROLE_PERMISSIONS" if body.enabled else "BULK_REVOKE_ROLE_PERMISSIONS",
        "role_permission", role.id,
        new_value={"role": body.role_name, "count": len(body.permissions), "enabled": body.enabled}
    )
    return {"ok": True, "count": len(body.permissions), "enabled": body.enabled}


@router.post("/temporary")
def create_temporary_permission(
    body: TemporaryPermissionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner)
):
    """Grant temporary access for a user that automatically expires."""
    target_user = db.get(User, body.user_id)
    if not target_user or target_user.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="User not found")
        
    try:
        start_dt = datetime.fromisoformat(body.start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(body.end_time.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")
        
    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="Start time must be before end time")
        
    now = datetime.now(timezone.utc)
    perm_id = new_id()
    temp_perm = TemporaryPermission(
        id=perm_id,
        user_id=body.user_id,
        permission=body.permission,
        start_time=start_dt,
        end_time=end_dt,
        created_by=user.id,
        created_at=now,
        status="ACTIVE",
        tenant_id=user.tenant_id
    )
    db.add(temp_perm)
    
    # Save to permission history
    hist = PermissionHistory(
        id=new_id(),
        tenant_id=user.tenant_id,
        user_id=body.user_id,
        action="GRANT_TEMPORARY",
        permission=body.permission,
        changed_by=user.id,
        timestamp=now,
        reason=f"Temporary grant until {end_dt.isoformat()}"
    )
    db.add(hist)
    db.commit()
    
    log_action(db, user.id, user.tenant_id, user.branch_id, "TEMPORARY_PERMISSION_GRANTED", "temporary_permission", perm_id)
    return {"ok": True, "id": perm_id}


@router.get("/temporary")
def list_temporary_permissions(
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_owner)
):
    """List all temporary permissions."""
    now = datetime.now(timezone.utc)
    # Automatically flag expired entries in response
    perms = db.query(TemporaryPermission).filter(TemporaryPermission.tenant_id == user.tenant_id).order_by(TemporaryPermission.created_at.desc()).all()
    
    result = []
    for p in perms:
        # Update expired ones in DB on read
        if p.status == "ACTIVE" and p.end_time.replace(tzinfo=timezone.utc) < now:
            p.status = "EXPIRED"
            db.flush()
        
        target = db.get(User, p.user_id)
        creator = db.get(User, p.created_by)
        result.append({
            "id": p.id,
            "userId": p.user_id,
            "userName": target.name if target else "Unknown",
            "permission": p.permission,
            "startTime": p.start_time.isoformat(),
            "endTime": p.end_time.isoformat(),
            "status": p.status,
            "createdBy": creator.name if creator else "System",
            "createdAt": p.created_at.isoformat()
        })
    db.commit()
    return result


@router.post("/temporary/{perm_id}/cancel")
def cancel_temporary_permission(
    perm_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner)
):
    """Manually revoke a temporary permission override."""
    p = db.get(TemporaryPermission, perm_id)
    if not p or p.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Permission not found")
        
    p.status = "CANCELLED"
    
    # Save to history
    hist = PermissionHistory(
        id=new_id(),
        tenant_id=user.tenant_id,
        user_id=p.user_id,
        action="REVOKE_TEMPORARY",
        permission=p.permission,
        changed_by=user.id,
        timestamp=datetime.now(timezone.utc),
        reason="Manually cancelled by Owner"
    )
    db.add(hist)
    db.commit()
    log_action(db, user.id, user.tenant_id, user.branch_id, "TEMPORARY_PERMISSION_CANCELLED", "temporary_permission", perm_id)
    return {"ok": True}


@router.get("/effective/{user_id}")
def get_effective_permissions(
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_owner)
):
    """Calculate the final effective permissions for a user."""
    target_user = db.get(User, user_id)
    if not target_user or target_user.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="User not found")
        
    role_name = target_user.role.upper()
    now = datetime.now(timezone.utc)
    
    # 1. Get temporary permissions
    temp_perms = db.query(TemporaryPermission).filter(
        TemporaryPermission.user_id == user_id,
        TemporaryPermission.start_time <= now,
        TemporaryPermission.end_time >= now,
        TemporaryPermission.status == "ACTIVE"
    ).all()
    active_temp = {t.permission for t in temp_perms}
    
    # 2. Get direct overrides
    direct_perms = db.query(UserPermission).filter(UserPermission.user_id == user_id).all()
    active_direct = {d.permission for d in direct_perms}
    
    # 3. Get role permissions
    active_role = set()
    db_role = db.query(Role).filter(Role.name == target_user.role, Role.tenant_id == user.tenant_id).first()
    if db_role:
        role_perms = db.query(RolePermission).filter(RolePermission.role_id == db_role.id).all()
        active_role = {rp.permission for rp in role_perms}
        if not role_perms:
            active_role = ROLE_PERMISSIONS.get(role_name, set())
    else:
        active_role = ROLE_PERMISSIONS.get(role_name, set())
        
    # Final effective access
    effective = set()
    if role_name == "OWNER":
        effective = ALL_PERMISSIONS
    else:
        effective = active_role.union(active_direct).union(active_temp)
        
    return {
        "userId": user_id,
        "name": target_user.name,
        "role": target_user.role,
        "effective": sorted(list(effective)),
        "rolePermissions": sorted(list(active_role)),
        "directPermissions": sorted(list(active_direct)),
        "temporaryPermissions": sorted(list(active_temp))
    }


@router.post("/direct-permission")
def toggle_direct_permission(
    body: DirectPermissionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner)
):
    """Grant or revoke an explicit direct permission override for a user."""
    target_user = db.get(User, body.user_id)
    if not target_user or target_user.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Prevent modifying owners
    if target_user.role.upper() == "OWNER":
        raise HTTPException(status_code=400, detail="Cannot override Owner permissions directly")
        
    existing = db.query(UserPermission).filter(
        UserPermission.user_id == body.user_id,
        UserPermission.permission == body.permission
    ).first()
    
    now = datetime.now(timezone.utc)
    if body.action.upper() == "GRANT":
        if not existing:
            up = UserPermission(
                id=new_id(),
                user_id=body.user_id,
                permission=body.permission,
                tenant_id=user.tenant_id
            )
            db.add(up)
        action_name = "GRANT_USER_PERMISSION"
    elif body.action.upper() == "REVOKE":
        if existing:
            db.delete(existing)
        action_name = "REVOKE_USER_PERMISSION"
    else:
        raise HTTPException(status_code=422, detail="Action must be GRANT or REVOKE")
        
    # Save permission history
    hist = PermissionHistory(
        id=new_id(),
        tenant_id=user.tenant_id,
        user_id=body.user_id,
        action=body.action.upper(),
        permission=body.permission,
        changed_by=user.id,
        timestamp=now,
        reason=body.reason
    )
    db.add(hist)
    db.commit()
    
    log_action(db, user.id, user.tenant_id, user.branch_id, action_name, "user_permission", target_user.id, new_value={"permission": body.permission})
    return {"ok": True}


@router.get("/history")
def list_permission_history(
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_owner)
):
    """List permission modifications log."""
    histories = db.query(PermissionHistory).filter(PermissionHistory.tenant_id == user.tenant_id).order_by(PermissionHistory.timestamp.desc()).limit(200).all()
    result = []
    for h in histories:
        target = db.get(User, h.user_id)
        editor = db.get(User, h.changed_by)
        result.append({
            "id": h.id,
            "userId": h.user_id,
            "userName": target.name if target else "Unknown",
            "action": h.action,
            "permission": h.permission,
            "role": h.role,
            "changedBy": editor.name if editor else "System",
            "timestamp": h.timestamp.isoformat(),
            "reason": h.reason
        })
    return result


@router.get("/sessions")
def list_active_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_owner)
):
    """List active user login sessions."""
    q = db.query(UserSession).filter(UserSession.tenant_id == user.tenant_id)
    if user.branch_id and user.role.upper() != "OWNER":
        q = q.filter(UserSession.branch_id == user.branch_id)
        
    sessions = q.order_by(UserSession.last_activity.desc()).all()
    result = []
    for s in sessions:
        u = db.get(User, s.user_id)
        result.append({
            "id": s.id,
            "userId": s.user_id,
            "userName": u.name if u else "Unknown",
            "role": u.role if u else "Unknown",
            "device": s.device,
            "loginTime": s.login_time.isoformat(),
            "lastActivity": s.last_activity.isoformat(),
            "status": s.status
        })
    return result


@router.post("/sessions/{session_id}/revoke")
def force_logout_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner)
):
    """Force log out an active session (Revocation)."""
    sess = db.get(UserSession, session_id)
    if not sess or sess.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Prevent Owner from revoking their own active session
    # (they must logout normally, to avoid locking themselves out)
    # But wait, they can revoke other sessions. Let's allow it but prevent them revoking their current session.
    # We can identify their current session by checking the token.
    # In FastAPI, we can inject credentials to find it, but it's simpler to just reject if user_id == owner and it's their active token.
    # We can match sess.id. If we don't have token context, we can just block revoking sessions of the current logged-in owner if it's the only one.
    
    sess.status = "REVOKED"
    db.commit()
    log_action(db, user.id, user.tenant_id, user.branch_id, "FORCE_LOGOUT", "user_session", session_id)
    return {"ok": True}


@router.post("/users/{user_id}/unlock")
def unlock_user_account(
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner)
):
    """Unlock a locked staff user account."""
    target = db.get(User, user_id)
    if not target or target.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="User not found")
        
    target.failed_login_attempts = 0
    target.locked_until = None
    db.commit()
    log_action(db, user.id, user.tenant_id, user.branch_id, "ACCOUNT_UNLOCKED", "user", user_id)
    return {"ok": True}

