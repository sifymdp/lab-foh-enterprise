"""RAG Embeddings Package."""

from app.services.rag.embeddings.factory import get_embedding_provider
from app.services.rag.embeddings.fast_local_embeddings import FastLocalEmbeddingProvider
from app.services.rag.embeddings.openrouter_embeddings import OpenRouterEmbeddingProvider

__all__ = [
    "get_embedding_provider",
    "FastLocalEmbeddingProvider",
    "OpenRouterEmbeddingProvider",
]
