"""OpenRouter Provider Implementation.

Provides model-agnostic access to cutting-edge reasoning, vision, and decision models
via the OpenRouter gateway.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from openai import OpenAI

from app.config import settings
from app.services.ai_agent.llm.provider import LLMProvider, ModelCapabilities

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(LLMProvider):
    """OpenRouter Gateway implementation supporting dynamic model switching and tool calling."""

    def __init__(self, api_key: str | None = None, default_model: str | None = None):
        self.api_key = (
            api_key
            or getattr(settings, "openrouter_api_key", "")
            or os.getenv("OPENROUTER_API_KEY", "")
        ).strip()
        self.default_model = (
            default_model
            or getattr(settings, "ai_primary_model", "openai/gpt-4o-mini")
        )
        self.set_api_key(self.api_key, self.default_model)

    def set_api_key(self, api_key: str, default_model: str | None = None) -> None:
        """Dynamically activates OpenRouter with the given API key."""
        self.api_key = api_key.strip()
        if default_model:
            self.default_model = default_model.strip()
        if self.api_key and not self.api_key.startswith("your_") and "your_api_key_here" not in self.api_key:
            self._client = OpenAI(
                base_url=OPENROUTER_BASE_URL,
                api_key=self.api_key,
                default_headers={
                    "HTTP-Referer": "https://foh-enterprise.restaurant",
                    "X-Title": "FOH Enterprise AI Operations",
                },
                timeout=float(getattr(settings, "ai_request_timeout_seconds", 20)),
            )
            logger.info("OpenRouter client configured with model: %s", self.default_model)
        else:
            self._client = None

    def is_configured(self) -> bool:
        if not self._client or not self.api_key:
            current_key = (
                getattr(settings, "openrouter_api_key", "")
                or os.getenv("OPENROUTER_API_KEY", "")
            ).strip()
            if current_key and not current_key.startswith("your_") and "your_api_key_here" not in current_key:
                self.set_api_key(current_key, getattr(settings, "ai_primary_model", None))
        return bool(self._client and self.api_key)

    def get_provider_name(self) -> str:
        return "OpenRouter"

    def check_capabilities(self, model_id: str) -> ModelCapabilities:
        """Validates model capabilities before using in production tool-calling path."""
        # Known defaults for prevalent OpenRouter models; can query /api/v1/models if needed
        is_vision = any(v in model_id.lower() for v in ["vision", "4o", "gemini", "claude-3", "vl"])
        # Most modern frontier models support tools
        supports_tools = True
        return ModelCapabilities(
            supports_tools=supports_tools,
            supports_vision=is_vision,
            context_length=128000,
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
        if not self._client:
            logger.debug("OpenRouter client is not initialized (missing API key)")
            return None

        target_model = model or self.default_model

        kwargs: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            res = self._client.chat.completions.create(**kwargs)
            msg = res.choices[0].message

            result: dict[str, Any] = {
                "role": msg.role or "assistant",
                "content": msg.content or "",
            }

            if getattr(msg, "tool_calls", None):
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": getattr(tc, "type", "function") or "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]

            return result

        except Exception as exc:
            logger.warning("OpenRouter invocation failed for model '%s': %s", target_model, exc)
            return None
