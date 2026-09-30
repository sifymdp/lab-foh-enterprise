from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_manager_or_owner, require_menu_manager
from app.database import get_db
from app.models.user import User
from app.schemas.ai import (
    AIEventCreate,
    AIEventOut,
    ChatIn,
    ChatOut,
    ChatRequest,
    ChatResponse,
    SeatingResponse,
    SeatingSuggestIn,
    ShiftReport,
)
from app.services import ai_service

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/events", response_model=list[AIEventOut])
def list_events(
    resolved: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AIEventOut]:
    return ai_service.list_alerts(db, resolved=resolved, user_role=current_user.role)


@router.post("/events", response_model=AIEventOut)
def create_event(
    body: AIEventCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_owner),
) -> AIEventOut:
    return ai_service.create_alert(db, body)


@router.patch("/events/{event_id}/resolve")
def resolve_event(
    event_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    return ai_service.resolve_alert(db, event_id)


@router.patch("/events/{event_id}/acknowledge", response_model=AIEventOut)
def acknowledge_event(
    event_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> AIEventOut:
    return ai_service.acknowledge_alert(db, event_id)


@router.post("/seating-suggest", response_model=SeatingResponse)
def seating_suggest(
    body: SeatingSuggestIn,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SeatingResponse:
    suggestion = ai_service.seating_suggest(db, body.party_size)
    return SeatingResponse(suggestion=suggestion, party_size=body.party_size)


@router.post("/chat", response_model=ChatResponse)
def assistant_chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    from app.services import chat_service
    messages_payload: list[dict] = []
    if body.messages:
        messages_payload = [m.model_dump(by_alias=False) for m in body.messages]
    elif body.message:
        messages_payload = [m.model_dump(by_alias=False) for m in body.history] + [
            {"role": "user", "content": body.message}
        ]
    reply, actions = chat_service.chat(db, user, messages_payload)
    return ChatResponse(reply=reply, actions=actions)


@router.get("/reports/shift", response_model=ShiftReport)
def shift_report(
    date: str | None = Query(None),
    db: Session = Depends(get_db),
    _user: User = Depends(require_manager_or_owner),
) -> ShiftReport:
    content, stats = ai_service.shift_report(db, date)
    return ShiftReport(report_date=stats.get("reportDate", date or ""), content=content, stats=stats)


@router.get("/provider")
def get_ai_provider(
    _user: User = Depends(get_current_user),
) -> dict:
    """Returns whether cloud LLM is active and provider info."""
    from app.services.groq_llm import get_provider_status
    return get_provider_status()


class ConfigureKeyIn(BaseModel):
    provider: str = "groq"
    api_key: str
    model: str | None = None


@router.post("/configure-key")
def configure_ai_key(
    body: ConfigureKeyIn,
    _user: User = Depends(get_current_user),
) -> dict:
    """Update and persist AI API key directly without restarting the server."""
    from app.services.groq_llm import save_api_key
    return save_api_key(body.provider, body.api_key, body.model)
