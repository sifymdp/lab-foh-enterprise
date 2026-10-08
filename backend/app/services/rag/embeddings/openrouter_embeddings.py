"""
OpenRouter / OpenAI-Compatible Embedding Provider
──────────────────────────────────────────────────
Calls external embedding APIs via HTTP with automatic fallback
to FastLocalEmbeddingProvider on network timeouts or missing keys.
"""

from __future__ import annotations

import logging
from typing import Any
import httpx

from app.config import settings
from app.services.rag.embeddings.fast_local_embeddings import FastLocalEmbeddingProvider
from app.services.rag.interfaces.embedding import EmbeddingProvider

logger = logging.getLogger(__name__)


class OpenRouterEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using OpenRouter or OpenAI embedding API endpoints."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        dimension: int = 384,
    ) -> None:
        self.api_key = api_key or settings.openrouter_api_key or settings.openai_api_key
        self.model = model or settings.rag_embedding_model or "openai/text-embedding-3-small"
        self.base_url = base_url.rstrip("/")
        self.dimension = dimension
        self._fallback_provider = FastLocalEmbeddingProvider(dimension=dimension)

    def get_dimension(self) -> int:
        return self.dimension

    def get_provider_name(self) -> str:
        return f"openrouter:{self.model}"

    def embed_text(self, text: str) -> list[float]:
        res = self.embed_batch([text])
        return res[0] if res else [0.0] * self.dimension

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key or not texts:
            return self._fallback_provider.embed_batch(texts)

        endpoint = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://foh-enterprise.local",
            "X-Title": "FOH Enterprise RAG",
        }
        payload = {
            "model": self.model,
            "input": texts,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(endpoint, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
                    embeddings = [item.get("embedding", []) for item in items]
                    if len(embeddings) == len(texts):
                        return embeddings
                logger.warning(
                    "OpenRouter embedding endpoint returned status %d. Falling back to local.",
                    resp.status_code,
                )
        except Exception as err:
            logger.warning("OpenRouter embedding request failed: %s. Using local fallback.", err)

        return self._fallback_provider.embed_batch(texts)
