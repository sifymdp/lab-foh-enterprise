from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_manager_or_owner, require_menu_manager, require_owner
from app.database import get_db
from app.models.user import User
from app.schemas.ai import (
    AIEventCreate,
    AIEventOut,
    ChatIn,
    ChatOut,
    ChatAction,
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
    from app.services import kitchen_alert_service
    kitchen_alert_service.evaluate_kitchen_alerts(db)
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
    from app.services.ai_agent import ai_orchestrator

    # Extract user message
    user_query = ""
    if body.message:
        user_query = body.message
    elif body.messages:
        for m in reversed(body.messages):
            if getattr(m, "role", "") == "user":
                user_query = getattr(m, "content", "")
                break

    # Process through central AI orchestrator with L1 Financial Firewall
    res = ai_orchestrator.process_request(db, user, user_query)

    # Convert UI actions to ChatActions
    chat_actions = [
        ChatAction(
            type=a.type,
            route=a.route,
            filter=a.filter,
            table_ids=a.table_ids,
            summary=f"{a.type} -> {a.route}" if a.route else a.type,
            ok=True,
        )
        for a in res.actions
    ]

    return ChatResponse(
        reply=res.response.summary,
        actions=chat_actions,
        classification=res.classification,
        intent=res.intent,
        citations=res.citations or res.response.citations,
    )


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
    from app.services.ai_agent.llm import model_router
    return model_router.get_provider_status()


class ConfigureKeyIn(BaseModel):
    provider: str = "openrouter"
    api_key: str
    model: str | None = None


@router.post("/configure-key")
def configure_ai_key(
    body: ConfigureKeyIn,
    _user: User = Depends(require_manager_or_owner),
) -> dict:
    """Update and persist AI API key directly (Owner or Manager)."""
    from app.services.groq_llm import save_api_key
    from app.services.ai_agent.llm import model_router

    prov = body.provider.lower().strip()
    res = save_api_key(prov, body.api_key, body.model)
    if "openrouter" in prov:
        model_router.openrouter.set_api_key(body.api_key, body.model)

    status = model_router.get_provider_status()
    active_prov = status.get("provider") or prov.capitalize()
    active_model = status.get("model") or body.model or "default"
    return {
        "success": True,
        "ok": True,
        "provider": active_prov,
        "model": active_model,
        "message": f"{active_prov} ({active_model}) activated and connected successfully!",
    }
