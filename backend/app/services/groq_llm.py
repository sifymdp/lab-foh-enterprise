"""Multi-provider LLM service — high speed, tool-calling inference via OpenAI-compatible APIs.

Supports:
1. Groq (llama-3.3-70b-versatile) — Free, lightning-fast inference
2. Google Gemini (gemini-2.0-flash / gemini-1.5-flash) — Free tier via OpenAI endpoint
3. OpenAI / OpenRouter (gpt-4o-mini)
4. Ollama (local)
5. Graceful fallback to deterministic/local NLU engine
"""

from __future__ import annotations

import logging
import os
from typing import Any

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)


def get_active_provider() -> tuple[OpenAI, str, str] | None:
    """Detect and return the active (client, model_name, provider_name)."""
    # 1. Groq Cloud
    groq_key = (settings.groq_api_key or os.getenv("GROQ_API_KEY") or "").strip()
    if groq_key:
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key,
        )
        return client, settings.groq_chat_model or "llama-3.3-70b-versatile", "Groq"

    # 2. Google Gemini (OpenAI-compatible endpoint)
    gemini_key = (
        settings.gemini_api_key
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or ""
    ).strip()
    if gemini_key:
        client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=gemini_key,
        )
        return client, settings.gemini_model or "gemini-2.0-flash", "Google Gemini"

    # 3. OpenAI / OpenRouter
    openai_key = (settings.openai_api_key or os.getenv("OPENAI_API_KEY") or "").strip()
    if openai_key:
        base_url = (settings.openai_base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip()
        client = OpenAI(
            base_url=base_url,
            api_key=openai_key,
        )
        return client, settings.openai_model or "gpt-4o-mini", "OpenAI"

    return None


def get_provider_status() -> dict[str, Any]:
    active = get_active_provider()
    if active:
        return {"connected": True, "provider": active[2], "model": active[1]}
    return {"connected": False, "provider": None, "model": None}


# ──── Simple Text Generation ────────────────────────────────────────────────


def generate_text(prompt: str, fallback: str) -> str:
    """Generate a short text completion. Returns *fallback* on failure."""
    text = try_generate(prompt)
    return text if text else fallback


def try_generate(prompt: str) -> str | None:
    """Try active cloud LLM first, then Ollama. Returns None on total failure."""
    active = get_active_provider()
    if active:
        client, model, provider = active
        try:
            res = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=512,
            )
            content = (res.choices[0].message.content or "").strip()
            if content:
                return content
        except Exception as exc:
            logger.warning("%s generate failed (%s), trying fallbacks", provider, exc)

    # Local Ollama fallback
    try:
        import httpx

        url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
        with httpx.Client(timeout=5.0) as http:
            r = http.post(url, json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
            })
            r.raise_for_status()
            return (r.json().get("response") or "").strip() or None
    except Exception as exc:
        logger.debug("Ollama unavailable (%s)", exc)
        return None


# ──── Tool-Calling Chat Completion ──────────────────────────────────────────


def chat_completion(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.1,
) -> dict[str, Any] | None:
    """Run a single chat completion with optional tool definitions.

    Returns the raw OpenAI-style message dict, or None when no cloud LLM is
    available (caller should fall back to deterministic answers).
    """
    active = get_active_provider()
    if not active:
        return None

    client, model, provider = active
    try:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        res = client.chat.completions.create(**kwargs)
        msg = res.choices[0].message

        result: dict[str, Any] = {
            "role": msg.role or "assistant",
            "content": msg.content or "",
        }
        if getattr(msg, "tool_calls", None):
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
        logger.warning("%s chat_completion failed: %s", provider, exc)
        return None
