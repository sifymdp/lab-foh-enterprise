"""Model Router and Multi-Provider Fallback Orchestrator."""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.services.ai_agent.llm.legacy_provider import LegacyOpenAICompatProvider
from app.services.ai_agent.llm.openrouter_provider import OpenRouterProvider
from app.services.ai_agent.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class ModelRouter:
    """Selects and dispatches requests to primary, vision, decision, or fallback models."""

    def __init__(self):
        self.openrouter = OpenRouterProvider()
        self.legacy = LegacyOpenAICompatProvider()

    def get_active_provider(self) -> LLMProvider:
        """Prefers OpenRouter if configured, otherwise falls back to legacy provider."""
        if self.openrouter.is_configured():
            return self.openrouter
        return self.legacy

    def get_provider_status(self) -> dict[str, Any]:
        from app.services.groq_llm import _lookup_env_keys
        keys = _lookup_env_keys()
        openrouter_ok = self.openrouter.is_configured()

        status: dict[str, Any] = {
            "connected": openrouter_ok,
            "provider": "OpenRouter" if openrouter_ok else ("Groq" if keys.get("GROQ_API_KEY") else ("Google Gemini" if keys.get("GEMINI_API_KEY") else ("OpenAI" if keys.get("OPENAI_API_KEY") else None))),
            "model": (self.openrouter.default_model or settings.ai_primary_model) if openrouter_ok else settings.ai_primary_model,
            "available_providers": {
                "openrouter": bool(keys.get("OPENROUTER_API_KEY") or self.openrouter.api_key),
                "groq": bool(keys.get("GROQ_API_KEY")),
                "gemini": bool(keys.get("GEMINI_API_KEY") or keys.get("GOOGLE_API_KEY")),
                "openai": bool(keys.get("OPENAI_API_KEY")),
            },
            "multi_model_ready": openrouter_ok,
        }
        if not openrouter_ok:
            from app.services.groq_llm import get_provider_status as legacy_status
            leg = legacy_status()
            if leg.get("connected"):
                status["connected"] = True
                status["provider"] = leg.get("provider")
                status["model"] = leg.get("model")
        return status

    def chat_with_fallback(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        role: str = "primary",
        temperature: float = 0.1,
    ) -> tuple[dict[str, Any] | None, str, str]:
        """Tries primary model on OpenRouter, then fallback models, then legacy provider.

        Returns: (message_dict, model_name, provider_name)
        """
        if self.openrouter.is_configured():
            # Resolve model name based on requested role
            if role == "vision":
                target_model = settings.ai_vision_model
            elif role == "decision":
                target_model = settings.ai_decision_model
            else:
                target_model = settings.ai_primary_model

            # 1. Primary Attempt
            res = self.openrouter.chat_completion(
                messages, tools=tools, model=target_model, temperature=temperature
            )
            if res is not None:
                return res, target_model, "OpenRouter"

            # 2. OpenRouter Fallbacks
            fallback_str = getattr(settings, "ai_fallback_models", "")
            fallbacks = [m.strip() for m in fallback_str.split(",") if m.strip()]
            for fb_model in fallbacks:
                logger.info("Attempting OpenRouter fallback model: %s", fb_model)
                res = self.openrouter.chat_completion(
                    messages, tools=tools, model=fb_model, temperature=temperature
                )
                if res is not None:
                    return res, fb_model, "OpenRouter"

        # 3. Legacy Provider (Groq / Gemini / Local)
        res = self.legacy.chat_completion(messages, tools=tools, temperature=temperature)
        if res is not None:
            return res, self.legacy.get_provider_name(), self.legacy.get_provider_name()

        return None, "none", "none"


model_router = ModelRouter()
