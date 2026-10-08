"""LLM Providers and Model Routing Package."""

from app.services.ai_agent.llm.provider import LLMProvider, ModelCapabilities
from app.services.ai_agent.llm.openrouter_provider import OpenRouterProvider
from app.services.ai_agent.llm.legacy_provider import LegacyOpenAICompatProvider
from app.services.ai_agent.llm.model_router import model_router, ModelRouter

__all__ = [
    "LLMProvider",
    "ModelCapabilities",
    "OpenRouterProvider",
    "LegacyOpenAICompatProvider",
    "model_router",
    "ModelRouter",
]
