from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.security import decode_token
from app.database import SessionLocal
from app.models.user import User
from app.socket_manager import manager

router = APIRouter(tags=["ws"])


@router.get("/ws")
def websocket_info() -> dict:
    """WebSocket connections are not listed as interactive routes — use the URL below."""
    return {
        "connectUrl": "ws://localhost:8000/ws/{floor_id}?token=<jwt>",
        "events": ["table_updated", "ai_alert", "order_placed", "payment_confirmed"],
    }


def _authenticate(token: str | None) -> User | None:
    """Resolve a JWT to an active user. Any role is allowed — auth only, no RBAC."""
    if not token:
        return None
    user_id = decode_token(token)
    if not user_id:
        return None
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if not user or not user.is_active:
            return None
        return user
    finally:
        db.close()


@router.websocket("/ws/{floor_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    floor_id: str,
    token: str | None = Query(None),
) -> None:
    # Accept connections from ANY authenticated user (OWNER, MANAGER, HOST, WAITER).
    # Reject only when the token is missing or invalid — never based on role.
    user = _authenticate(token)
    if user is None:
        await websocket.close(code=1008)
        return
    await manager.connect(websocket, floor_id)
    print(f"[WS] client joined room: {floor_id} (user={user.role})")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, floor_id)
