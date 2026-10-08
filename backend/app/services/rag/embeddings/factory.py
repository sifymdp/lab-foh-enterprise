"""Embedding Provider Factory."""

from __future__ import annotations

from app.config import settings
from app.services.rag.embeddings.fast_local_embeddings import FastLocalEmbeddingProvider
from app.services.rag.embeddings.openrouter_embeddings import OpenRouterEmbeddingProvider
from app.services.rag.interfaces.embedding import EmbeddingProvider

_cached_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured singleton EmbeddingProvider."""
    global _cached_provider
    if _cached_provider is not None:
        return _cached_provider

    provider_type = (settings.rag_embedding_provider or "local").lower().strip()
    dim = settings.rag_embedding_dimensions or 384

    if provider_type in ("openrouter", "openai"):
        _cached_provider = OpenRouterEmbeddingProvider(dimension=dim)
    else:
        _cached_provider = FastLocalEmbeddingProvider(dimension=dim)

    return _cached_provider
