"""
SQL-Backed Universal Vector Store
──────────────────────────────────
Persists dense vector representations within the existing relational database.
Works uniformly on SQLite and PostgreSQL with strict tenant & branch isolation,
cosine similarity calculation, and JSON metadata parsing.
"""

from __future__ import annotations

import json
import math
from typing import Any
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.rag import KnowledgeChunk, KnowledgeDocument
from app.services.rag.interfaces.vector_store import (
    VectorRecord,
    VectorSearchResult,
    VectorStore,
)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two float vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return max(0.0, min(1.0, (dot / (norm_a * norm_b) + 1.0) / 2.0))


class SQLVectorStore(VectorStore):
    """Database-backed vector store implementation."""

    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory

    def _session_ctx(self, db: Session | None):
        """Helper to safely manage external vs internal database sessions."""
        if db is not None:
            class _NoopCtx:
                def __enter__(self):
                    return db
                def __exit__(self, exc_type, exc_val, exc_tb):
                    pass
            return _NoopCtx(), False
        return self.session_factory(), True

    def upsert_chunks(self, records: list[VectorRecord], db: Session | None = None) -> int:
        if not records:
            return 0
        count = 0
        ctx, should_commit = self._session_ctx(db)
        with ctx as s:
            for r in records:
                existing = (
                    s.query(KnowledgeChunk)
                    .filter(
                        KnowledgeChunk.id == r.id,
                        KnowledgeChunk.tenant_id == r.tenant_id,
                    )
                    .first()
                )
                emb_str = json.dumps(r.embedding)
                meta_str = json.dumps(r.metadata) if r.metadata else None

                if existing:
                    existing.title = r.title
                    existing.content = r.content
                    existing.domain = r.domain
                    existing.embedding_json = emb_str
                    existing.metadata_json = meta_str
                    existing.token_count = len(r.content.split())
                else:
                    new_chunk = KnowledgeChunk(
                        id=r.id,
                        document_id=r.document_id,
                        tenant_id=r.tenant_id,
                        branch_id=r.branch_id,
                        domain=r.domain,
                        chunk_index=r.chunk_index,
                        title=r.title,
                        content=r.content,
                        embedding_json=emb_str,
                        token_count=len(r.content.split()),
                        metadata_json=meta_str,
                    )
                    s.add(new_chunk)
                count += 1
            if should_commit:
                s.commit()
        return count

    def search(
        self,
        query_embedding: list[float],
        tenant_id: str,
        branch_id: str | None = None,
        domain: str | None = None,
        top_k: int = 4,
        min_score: float = 0.0,
        db: Session | None = None,
    ) -> list[VectorSearchResult]:
        """Perform semantic similarity search with strict tenant isolation."""
        ctx, _ = self._session_ctx(db)
        with ctx as s:
            query = s.query(KnowledgeChunk).join(
                KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id
            )
            # 1. Enforce Tenant Isolation (Mandatory)
            filters = [
                KnowledgeChunk.tenant_id == tenant_id,
                KnowledgeDocument.status == "ACTIVE",
            ]

            # 2. Enforce Branch Isolation (if scoped)
            if branch_id:
                filters.append(
                    or_(
                        KnowledgeChunk.branch_id == branch_id,
                        KnowledgeChunk.branch_id.is_(None),
                    )
                )

            # 3. Filter by Knowledge Domain (if specified)
            if domain:
                filters.append(KnowledgeChunk.domain == domain)

            chunks = query.filter(and_(*filters)).all()
            if not chunks:
                return []

            scored_results: list[VectorSearchResult] = []
            for c in chunks:
                if not c.embedding_json:
                    continue
                try:
                    chunk_vec = json.loads(c.embedding_json)
                except Exception:
                    continue

                sim = _cosine_similarity(query_embedding, chunk_vec)
                if sim >= min_score:
                    meta = {}
                    if c.metadata_json:
                        try:
                            meta = json.loads(c.metadata_json)
                        except Exception:
                            pass

                    scored_results.append(
                        VectorSearchResult(
                            chunk_id=c.id,
                            document_id=c.document_id,
                            tenant_id=c.tenant_id,
                            branch_id=c.branch_id,
                            domain=c.domain,
                            title=c.title,
                            content=c.content,
                            score=round(sim, 4),
                            metadata=meta,
                        )
                    )

            scored_results.sort(key=lambda x: x.score, reverse=True)
            return scored_results[:top_k]

    def delete_by_document(self, document_id: str, tenant_id: str, db: Session | None = None) -> int:
        ctx, should_commit = self._session_ctx(db)
        with ctx as s:
            deleted = (
                s.query(KnowledgeChunk)
                .filter(
                    KnowledgeChunk.document_id == document_id,
                    KnowledgeChunk.tenant_id == tenant_id,
                )
                .delete(synchronize_session=False)
            )
            if should_commit:
                s.commit()
            return deleted

    def delete_chunk(self, chunk_id: str, tenant_id: str, db: Session | None = None) -> bool:
        ctx, should_commit = self._session_ctx(db)
        with ctx as s:
            deleted = (
                s.query(KnowledgeChunk)
                .filter(
                    KnowledgeChunk.id == chunk_id,
                    KnowledgeChunk.tenant_id == tenant_id,
                )
                .delete(synchronize_session=False)
            )
            if should_commit:
                s.commit()
            return deleted > 0

    def health_check(self) -> dict[str, Any]:
        with self.session_factory() as db:
            total_chunks = db.query(KnowledgeChunk).count()
            total_docs = db.query(KnowledgeDocument).count()
            return {
                "status": "HEALTHY",
                "backend": "sql_vector_store",
                "total_documents": total_docs,
                "total_chunks": total_chunks,
            }
