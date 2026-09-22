from datetime import datetime, timezone

from fastapi import HTTPException, status

from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.core.status_machine import ACTIVE_SESSION_STATUSES
from app.models import CleaningEvent, DiningSession, Table
from app.schemas.session import DiningSessionOut, SeatGuestIn
from app.services.table_service import (
    _emit_table_updated,
    _on_status_change,
    active_session_for_table,
    get_table,
    record_history,
)
from app.socket_manager import sio


def session_to_out(session: DiningSession) -> DiningSessionOut:
    seated = session.seated_at
    if isinstance(seated, datetime):
        seated_str = seated.isoformat().replace("+00:00", "Z")
        if seated.tzinfo is None:
            seated_str = seated.isoformat() + "Z"
    else:
        seated_str = str(seated)
    return DiningSessionOut(
        id=session.id,
        table_id=session.table_id,
        guest_name=session.guest_name,
        party_size=session.party_size,
        seated_at=seated_str,
        status=session.status,
    )


def list_sessions(
    db: Session,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> list[DiningSessionOut]:
    q = db.query(DiningSession)
    if tenant_id:
        q = q.filter(DiningSession.tenant_id == tenant_id)
    if branch_id:
        q = q.filter(DiningSession.branch_id == branch_id)
    sessions = q.order_by(DiningSession.seated_at.desc()).all()
    return [session_to_out(s) for s in sessions]


def seat_guest(
    db: Session,
    payload: SeatGuestIn,
    host_id: str | None,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> DiningSessionOut:
    table = get_table(db, payload.table_id, tenant_id, branch_id)
    if payload.party_size > table.capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Party size exceeds table capacity",
        )
    if table.status not in ("AVAILABLE", "RESERVED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Table is not available for seating",
        )
    if active_session_for_table(db, payload.table_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Table already has an active session",
        )
    now = datetime.now(timezone.utc)
    old_status = table.status
    session = DiningSession(
        id=new_id(),
        table_id=payload.table_id,
        tenant_id=table.tenant_id,
        branch_id=table.branch_id,
        guest_name=payload.guest_name,
        party_size=payload.party_size,
        seated_at=now,
        status="SEATED",
        host_id=host_id,
    )
    table.status = "SEATED"
    table.consecutive_person_scans = 0
    table.consecutive_empty_scans = 0
    db.add(session)
    record_history(db, table.id, old_status, "SEATED", host_id, session.id)
    db.commit()
    db.refresh(session)
    db.refresh(table)
    _emit_table_updated(table)
    session_out = session_to_out(session)
    sio.emit_sync("session:created", session_out.model_dump(by_alias=True), room=str(table.floor_id))
    return session_out


def close_session(
    db: Session,
    session_id: str,
    user_id: str | None,
    tenant_id: str | None = None,
    branch_id: str | None = None,
) -> DiningSessionOut:
    q = db.query(DiningSession).filter(DiningSession.id == session_id)
    if tenant_id:
        q = q.filter(DiningSession.tenant_id == tenant_id)
    if branch_id:
        q = q.filter(DiningSession.branch_id == branch_id)
    session = q.first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    now = datetime.now(timezone.utc)
    table = db.get(Table, session.table_id)
    if table:
        old = table.status
        table.status = "CLEANING"
        # resets counters + alert flags and stamps cleaning_started_at
        _on_status_change(table, old, "CLEANING")
        record_history(db, table.id, old, "CLEANING", user_id, session.id)
        db.add(
            CleaningEvent(
                id=new_id(),
                table_id=table.id,
                dining_session_id=session.id,
                status="REQUESTED",
                requested_at=now,
            )
        )
    session.status = "CLEANING"
    session.closed_at = now  # stamp closure time for duration queries
    db.commit()
    db.refresh(session)
    if table:
        db.refresh(table)
        _emit_table_updated(table)
    return session_to_out(session)
