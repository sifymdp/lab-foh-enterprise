"""
Vector Store Interface
───────────────────────
Abstract base class defining CRUD and similarity search operations
for the RAG vector store layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, Field


class VectorRecord(BaseModel):
    """Normalized vector record for upserting into the vector store."""
    id: str
    document_id: str
    tenant_id: str
    branch_id: str | None = None
    domain: str
    chunk_index: int
    title: str | None = None
    content: str
    embedding: list[float]
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorSearchResult(BaseModel):
    """Result item returned by vector similarity search."""
    chunk_id: str
    document_id: str
    tenant_id: str
    branch_id: str | None = None
    domain: str
    title: str | None = None
    content: str
    score: float  # Cosine similarity or fused score between 0.0 and 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorStore(ABC):
    """Abstract interface for RAG vector stores."""

    @abstractmethod
    def upsert_chunks(self, records: list[VectorRecord], db: Any = None) -> int:
        """Upsert a list of vector records into storage. Returns count of inserted/updated chunks."""
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        tenant_id: str,
        branch_id: str | None = None,
        domain: str | None = None,
        top_k: int = 4,
        min_score: float = 0.0,
        db: Any = None,
    ) -> list[VectorSearchResult]:
        """Perform semantic similarity search strictly filtered by tenant/branch and optional domain."""
        pass

    @abstractmethod
    def delete_by_document(self, document_id: str, tenant_id: str, db: Any = None) -> int:
        """Delete all chunks associated with a specific document. Returns deleted count."""
        pass

    @abstractmethod
    def delete_chunk(self, chunk_id: str, tenant_id: str, db: Any = None) -> bool:
        """Delete a single chunk by ID."""
        pass

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Return operational health status and total indexed vector count."""
        pass
