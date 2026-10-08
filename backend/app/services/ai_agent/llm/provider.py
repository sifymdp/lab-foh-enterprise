"""Abstract Base Class for LLM Providers in the AI Agent system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, NamedTuple


class ModelCapabilities(NamedTuple):
    supports_tools: bool
    supports_vision: bool
    context_length: int
    model_id: str


class LLMProvider(ABC):
    """Model-agnostic interface for inference providers."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Returns provider identifier (e.g. 'OpenRouter', 'Groq', 'Ollama')."""
        pass

    @abstractmethod
    def check_capabilities(self, model_id: str) -> ModelCapabilities:
        """Inspects if the model satisfies required agent capabilities."""
        pass

    @abstractmethod
    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> dict[str, Any] | None:
        """Executes a chat completion with optional tool specifications.

        Returns standard OpenAI-style message dict or None on failure.
        """
        pass
