from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_floor_editor
from app.database import get_db
from app.models.user import User
from app.schemas.floor import FloorOut
from app.services.floor_service import floor_to_out, get_current_floor, reset_floor, update_floor

router = APIRouter(prefix="/floors", tags=["floors"])


@router.get("/current", response_model=FloorOut)
def get_floor(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FloorOut:
    return floor_to_out(get_current_floor(db, user.tenant_id, user.branch_id))


@router.put("/current", response_model=FloorOut)
def put_floor(
    body: FloorOut,
    db: Session = Depends(get_db),
    user: User = Depends(require_floor_editor),
) -> FloorOut:
    return update_floor(db, body, user.tenant_id, user.branch_id)


@router.post("/current/reset", response_model=FloorOut)
def post_reset(
    db: Session = Depends(get_db),
    user: User = Depends(require_floor_editor),
) -> FloorOut:
    return reset_floor(db, user.tenant_id, user.branch_id)
