"""Groq LLM provider — blazing fast, free-tier inference via OpenAI-compatible API.

Uses llama-3.3-70b-versatile for tool-calling chat and llama-3.3-70b-versatile
for general text generation.  Falls back gracefully to Ollama, then to
deterministic answers when neither is available.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI | None:
    """Lazily initialise and cache the Groq-backed OpenAI client."""
    global _client
    if _client is not None:
        return _client
    key = settings.groq_api_key
    if not key:
        logger.info("GROQ_API_KEY not set — Groq LLM disabled, will use fallbacks")
        return None
    _client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=key,
    )
    return _client


# ──── simple text generation ────────────────────────────────────────────────


def generate_text(prompt: str, fallback: str) -> str:
    """Generate a short text completion.  Returns *fallback* on any failure."""
    text = try_generate(prompt)
    return text if text else fallback


def try_generate(prompt: str) -> str | None:
    """Try Groq first, then Ollama.  ``None`` on total failure."""
    client = _get_client()
    if client:
        try:
            res = client.chat.completions.create(
                model=settings.groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=512,
            )
            content = (res.choices[0].message.content or "").strip()
            if content:
                return content
        except Exception as exc:
            logger.warning("Groq generate failed (%s), trying Ollama", exc)

    # Ollama fallback
    try:
        import httpx

        url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
        with httpx.Client(timeout=30.0) as http:
            r = http.post(url, json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
            })
            r.raise_for_status()
            return (r.json().get("response") or "").strip() or None
    except Exception as exc:
        logger.info("Ollama also unavailable (%s)", exc)
        return None


# ──── tool-calling chat completion ──────────────────────────────────────────


def chat_completion(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.1,
) -> dict[str, Any] | None:
    """Run a single chat completion with optional tool definitions.

    Returns the raw OpenAI-style message dict, or ``None`` when Groq is
    unavailable (caller should fall back to deterministic answers).
    """
    client = _get_client()
    if not client:
        return None
    try:
        kwargs: dict[str, Any] = {
            "model": settings.groq_chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        res = client.chat.completions.create(**kwargs)
        msg = res.choices[0].message
        # Normalise into a plain dict so callers don't need openai types.
        result: dict[str, Any] = {
            "role": msg.role,
            "content": msg.content or "",
        }
        if msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        return result
    except Exception as exc:
        logger.warning("Groq chat_completion failed: %s", exc)
        return None
