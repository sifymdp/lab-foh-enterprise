"""
Deterministic Fast Local Embedding Provider
─────────────────────────────────────────────
Generates normalized, fixed-dimension vector representations using hashed subword
n-grams and term frequencies. Provides zero-latency, 100% offline, dependency-free
vector generation for local development and fallback resilience.
"""

from __future__ import annotations

import hashlib
import math
import re
from app.services.rag.interfaces.embedding import EmbeddingProvider


class FastLocalEmbeddingProvider(EmbeddingProvider):
    """Zero-dependency local embedding provider producing unit-normalized dense vectors."""

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def get_dimension(self) -> int:
        return self.dimension

    def get_provider_name(self) -> str:
        return "local_deterministic"

    def embed_text(self, text: str) -> list[float]:
        vec = [0.0] * self.dimension
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        tokens = [t for t in cleaned.split() if len(t) > 1]
        if not tokens:
            return vec

        # Accumulate token hash buckets with positional and character n-gram weighting
        for idx, token in enumerate(tokens):
            weight = 1.0 / (1.0 + 0.05 * min(idx, 10))
            # Full word hash
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            bucket = h % self.dimension
            sign = 1.0 if ((h >> 16) & 1) == 0 else -1.0
            vec[bucket] += sign * 2.0 * weight

            # 3-char subword n-grams for typo & morphological tolerance
            if len(token) >= 4:
                for i in range(len(token) - 2):
                    ngram = token[i : i + 3]
                    nh = int(hashlib.sha256(ngram.encode("utf-8")).hexdigest(), 16)
                    nbucket = nh % self.dimension
                    nsign = 1.0 if ((nh >> 16) & 1) == 0 else -1.0
                    vec[nbucket] += nsign * 0.75 * weight

        # L2 unit normalization
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 1e-9:
            return [round(x / norm, 6) for x in vec]
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]
