"""Short-term In-Memory Conversation & Operational Context Store."""

from __future__ import annotations

import time
from typing import Any
from pydantic import BaseModel, Field


class ConversationContext(BaseModel):
    conversation_id: str
    last_updated: float = Field(default_factory=time.time)
    intent: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    focused_tables: list[str] = Field(default_factory=list)
    recent_messages: list[dict[str, str]] = Field(default_factory=list)


class ConversationStore:
    """Manages conversational session state with TTL cleanup."""

    def __init__(self, ttl_seconds: int = 1800):
        self._store: dict[str, ConversationContext] = {}
        self.ttl = ttl_seconds

    def get_or_create(self, conv_id: str) -> ConversationContext:
        self._cleanup()
        if conv_id not in self._store:
            self._store[conv_id] = ConversationContext(conversation_id=conv_id)
        ctx = self._store[conv_id]
        ctx.last_updated = time.time()
        return ctx

    def update_context(
        self,
        conv_id: str,
        intent: str | None = None,
        filters: dict[str, Any] | None = None,
        focused_tables: list[str] | None = None,
        new_user_msg: str | None = None,
        new_assistant_msg: str | None = None,
    ) -> None:
        ctx = self.get_or_create(conv_id)
        if intent:
            ctx.intent = intent
        if filters:
            ctx.filters.update(filters)
        if focused_tables is not None:
            ctx.focused_tables = focused_tables

        if new_user_msg:
            ctx.recent_messages.append({"role": "user", "content": new_user_msg})
        if new_assistant_msg:
            ctx.recent_messages.append({"role": "assistant", "content": new_assistant_msg})

        # Keep last 12 messages only
        if len(ctx.recent_messages) > 12:
            ctx.recent_messages = ctx.recent_messages[-12:]

    def _cleanup(self) -> None:
        now = time.time()
        expired = [cid for cid, ctx in self._store.items() if now - ctx.last_updated > self.ttl]
        for cid in expired:
            del self._store[cid]


conversation_store = ConversationStore()
