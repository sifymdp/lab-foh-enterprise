"""Legacy OpenAI-Compatible Provider Adapter.

Bridges existing Groq, Gemini, and direct OpenAI configurations into the
standard LLMProvider interface for resilience and fallback.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.ai_agent.llm.provider import LLMProvider, ModelCapabilities
from app.services.groq_llm import chat_completion as legacy_chat_completion, get_active_provider

logger = logging.getLogger(__name__)


class LegacyOpenAICompatProvider(LLMProvider):
    """Wraps the existing groq_llm service as an LLMProvider fallback."""

    def get_provider_name(self) -> str:
        active = get_active_provider()
        if active:
            return active[2]
        return "Local Engine"

    def check_capabilities(self, model_id: str) -> ModelCapabilities:
        return ModelCapabilities(
            supports_tools=True,
            supports_vision=False,
            context_length=32768,
            model_id=model_id,
        )

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> dict[str, Any] | None:
        try:
            return legacy_chat_completion(messages, tools=tools, temperature=temperature)
        except Exception as exc:
            logger.warning("Legacy provider completion failed: %s", exc)
            return None
