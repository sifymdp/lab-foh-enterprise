"""Text generation helper — delegates to groq_llm with transparent fallback.

Every call site that used `generate_text(prompt, fallback)` continues to work
unchanged.  Internally, Groq is tried first, then Ollama, then the fallback.
"""

from app.services.groq_llm import generate_text, try_generate  # noqa: F401

__all__ = ["generate_text", "try_generate"]
