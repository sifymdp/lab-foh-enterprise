import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def try_generate(prompt: str) -> str | None:
    """Ask Ollama for text. ``None`` means it was unreachable or answered empty.

    Callers that can tell the user which happened (e.g. the chat assistant)
    want that distinction; ``generate_text`` keeps the old silent-fallback
    behaviour for everything else.
    """
    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            res = client.post(url, json=payload)
            res.raise_for_status()
            data = res.json()
            return (data.get("response") or "").strip() or None
    except Exception as exc:
        logger.info("Ollama unavailable (%s), using fallback", exc)
        return None


def generate_text(prompt: str, fallback: str) -> str:
    return try_generate(prompt) or fallback
