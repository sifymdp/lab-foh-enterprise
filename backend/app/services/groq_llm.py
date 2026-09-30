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


def _lookup_env_keys() -> dict[str, str]:
    """Read API keys from memory, environment, and disk files dynamically without needing server restarts."""
    keys: dict[str, str] = {}

    # 1. Process environment and pydantic settings
    for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        val = (getattr(settings, k.lower(), None) or os.getenv(k) or "").strip()
        if val and not val.startswith("your_") and "your_api_key_here" not in val:
            keys[k] = val

    # 2. Check .env files on disk (backend/.env, .env, backend/.env.example)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    env_candidates = [
        os.path.join(base_dir, ".env"),
        os.path.join(base_dir, "..", ".env"),
        ".env",
        "backend/.env",
        os.path.join(base_dir, ".env.example"),
    ]
    for p in env_candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("#") or "=" not in line:
                            continue
                        name, _, val = line.partition("=")
                        name = name.strip()
                        val = val.strip().strip("'\"")
                        if (
                            name in ("GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY")
                            and val
                            and "your_api_key_here" not in val
                            and not val.startswith("your_")
                        ):
                            if name not in keys or not keys[name]:
                                keys[name] = val
            except Exception:
                pass
    return keys


def save_api_key(provider: str, api_key: str, model: str | None = None) -> dict[str, Any]:
    """Persist an API key to backend/.env and update process settings immediately."""
    prov = provider.lower().strip()
    key_name = "GROQ_API_KEY"
    if "gemini" in prov or "google" in prov:
        key_name = "GEMINI_API_KEY"
    elif "openai" in prov:
        key_name = "OPENAI_API_KEY"

    cleaned_key = api_key.strip()
    if not cleaned_key:
        return {"ok": False, "error": "API key cannot be empty"}

    # Update in-memory runtime
    os.environ[key_name] = cleaned_key
    if hasattr(settings, key_name.lower()):
        setattr(settings, key_name.lower(), cleaned_key)

    # Persist to backend/.env
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    target_env = os.path.join(base_dir, ".env")
    try:
        lines: list[str] = []
        found = False
        if os.path.exists(target_env):
            with open(target_env, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for idx, line in enumerate(lines):
                if line.strip().startswith(f"{key_name}=") or line.strip().startswith(f"# {key_name}="):
                    lines[idx] = f"{key_name}={cleaned_key}\n"
                    found = True
                    break
        if not found:
            lines.append(f"\n{key_name}={cleaned_key}\n")

        with open(target_env, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception as e:
        logger.warning("Could not persist key to %s: %s", target_env, e)

    # Verify connection
    status = get_provider_status()
    return {"ok": True, "provider": status.get("provider"), "model": status.get("model")}


def get_active_provider() -> tuple[OpenAI, str, str] | None:
    """Detect and return the active (client, model_name, provider_name)."""
    keys = _lookup_env_keys()

    # 1. Groq Cloud (Free, lightning-fast inference on Llama 3.3 70B)
    groq_key = keys.get("GROQ_API_KEY", "").strip()
    if groq_key:
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key,
        )
        return client, settings.groq_chat_model or "llama-3.3-70b-versatile", "Groq"

    # 2. Google Gemini (Free tier OpenAI-compatible endpoint)
    gemini_key = (keys.get("GEMINI_API_KEY") or keys.get("GOOGLE_API_KEY") or "").strip()
    if gemini_key:
        client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=gemini_key,
        )
        return client, settings.gemini_model or "gemini-2.0-flash", "Google Gemini"

    # 3. OpenAI / OpenRouter
    openai_key = keys.get("OPENAI_API_KEY", "").strip()
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
    return {"connected": False, "provider": "Local Engine", "model": "Rule-Based Maitre D'"}


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
        err_msg = str(exc).lower()
        if provider == "Groq" and ("rate_limit" in err_msg or "model" in err_msg or "429" in err_msg or "404" in err_msg):
            try:
                logger.info("Attempting Groq fast fallback to llama-3.1-8b-instant...")
                kwargs["model"] = "llama-3.1-8b-instant"
                res = client.chat.completions.create(**kwargs)
                msg = res.choices[0].message
                result = {
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
            except Exception as fb_exc:
                logger.warning("Groq fallback model also failed: %s", fb_exc)
        return None
