"""
Embedding Provider Interface
─────────────────────────────
Abstract base class defining the contract for text embedding generation.
Enables pluggable switching between OpenRouter, OpenAI, local embeddings, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract interface for text embedding providers."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Generate a dense vector embedding for a single text string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a batch of text strings."""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Return the vector dimensionality produced by this provider."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider identifier name (e.g. 'openrouter', 'local')."""
        pass
