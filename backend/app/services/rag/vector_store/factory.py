"""Vector Store Factory."""

from __future__ import annotations

from app.config import settings
from app.services.rag.interfaces.vector_store import VectorStore
from app.services.rag.vector_store.sql_vector_store import SQLVectorStore

_cached_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Return the configured singleton VectorStore."""
    global _cached_store
    if _cached_store is not None:
        return _cached_store

    # We currently use the robust SQLVectorStore which operates seamlessly
    # across SQLite and PostgreSQL, with zero external infrastructure overhead.
    _cached_store = SQLVectorStore()
    return _cached_store
