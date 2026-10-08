"""
Document Chunker Interface
───────────────────────────
Abstract base class for structure-aware document chunking.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, Field


class ChunkOutput(BaseModel):
    chunk_index: int
    title: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    token_count: int = 0


class DocumentChunker(ABC):
    """Abstract interface for document chunkers."""

    @abstractmethod
    def chunk_document(
        self,
        raw_text: str,
        document_title: str,
        metadata: dict[str, Any] | None = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> list[ChunkOutput]:
        """Split raw text into structured, semantically coherent chunks."""
        pass
