from app.schemas.common import CamelModel


class AIEventOut(CamelModel):
    id: str
    table_id: str | None = None
    event_type: str
    message: str
    target_role: str | None = None
    created_at: str
    resolved: bool
    acknowledged: bool = False
    metadata_json: str | None = None
    metadata: dict | None = None


class AIEventCreate(CamelModel):
    event_type: str
    message: str
    target_role: str | None = None
    table_id: str | None = None
    metadata: dict | None = None
    metadata_json: str | None = None


class SeatingSuggestIn(CamelModel):
    party_size: int


class SeatingResponse(CamelModel):
    suggestion: str
    party_size: int


class ShiftReport(CamelModel):
    report_date: str
    content: str
    stats: dict


class ChatMessage(CamelModel):
    role: str  # "user" | "assistant"
    content: str


class ChatIn(CamelModel):
    message: str
    history: list[ChatMessage] = []


class ChatOut(CamelModel):
    reply: str
    ai_generated: bool


class ChatRequest(CamelModel):
    messages: list[ChatMessage]


class ChatAction(CamelModel):
    tool: str
    summary: str
    ok: bool


class ChatResponse(CamelModel):
    reply: str
    actions: list[ChatAction] = []
