"""
Hybrid RAG Retrieval & Source Citation Engine
──────────────────────────────────────────────
Combines dense vector similarity with sparse keyword matching,
metadata filtering, tenant isolation, and strict score thresholding.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.models.rag import RAGQueryLog
from app.services.rag.embeddings.factory import get_embedding_provider
from app.services.rag.interfaces.vector_store import VectorSearchResult
from app.services.rag.vector_store.factory import get_vector_store

logger = logging.getLogger(__name__)


class RAGCitation(BaseModel):
    """Source reference exposing document metadata without sensitive internals."""
    id: str
    title: str
    domain: str
    snippet: str
    confidence: float


class HybridRetrievalResult(BaseModel):
    """Complete retrieval output containing grounded context and source citations."""
    query: str
    chunks: list[VectorSearchResult] = Field(default_factory=list)
    citations: list[RAGCitation] = Field(default_factory=list)
    top_confidence: float = 0.0
    insufficient_evidence: bool = False
    context_text: str = ""
    latency_ms: float = 0.0


def _compute_sparse_keyword_score(query: str, text: str) -> float:
    """Calculate normalized lexical match score based on keyword hits."""
    q_words = [w for w in re.sub(r"[^\w\s]", " ", query.lower()).split() if len(w) > 2]
    if not q_words:
        return 0.0
    t_lower = text.lower()
    hits = sum(1 for w in q_words if w in t_lower)
    return min(1.0, hits / max(1, len(q_words)))


class HybridRetrievalService:
    """Performs multi-modal semantic + keyword retrieval with strict tenant filtering."""

    def retrieve(
        self,
        query: str,
        tenant_id: str,
        db: Session | None = None,
        branch_id: str | None = None,
        domain: str | None = None,
        top_k: int | None = None,
        user_id: str | None = None,
        user_role: str | None = None,
        conversation_id: str | None = None,
        entity_filters: dict[str, Any] | None = None,
    ) -> HybridRetrievalResult:
        start_time = time.time()
        from app.services.rag.domains.registry import domain_registry

        # Normalize domain key
        norm_domain = domain_registry.normalize_key(domain) if domain else None

        # Cross-branch RBAC check: only organization-level roles may query cross-branch intelligence
        if norm_domain == "CROSS_BRANCH" and user_role is not None:
            allowed_roles = {"OWNER", "ORGANIZATION_ADMIN", "MULTI_BRANCH_MANAGER"}
            if user_role.upper() not in allowed_roles:
                return HybridRetrievalResult(
                    query=query,
                    chunks=[],
                    citations=[],
                    top_confidence=0.0,
                    insufficient_evidence=True,
                    context_text="Access restricted: Cross-branch operational comparisons require organization-level owner or administrator permissions.",
                    latency_ms=0.0,
                )

        k = top_k or settings.rag_top_k or 4
        dense_weight = settings.rag_hybrid_weight_dense or 0.7
        sparse_weight = settings.rag_hybrid_weight_sparse or 0.3
        min_conf = settings.rag_min_confidence or 0.35

        # 1. Generate query embedding
        emb_start = time.time()
        emb_provider = get_embedding_provider()
        query_emb = emb_provider.embed_text(query)
        emb_latency = (time.time() - emb_start) * 1000

        # 2. Dense vector search in vector store
        vector_store = get_vector_store()
        dense_results = vector_store.search(
            query_embedding=query_emb,
            tenant_id=tenant_id,
            branch_id=branch_id if norm_domain != "CROSS_BRANCH" else None,
            domain=norm_domain,
            top_k=k * 2,  # Oversample for hybrid re-ranking
            min_score=0.1,
            db=db,
        )

        # Apply entity filters if specified (e.g. table_id, station_id)
        if entity_filters and dense_results:
            filtered_results = []
            for r in dense_results:
                match = True
                for ek, ev in entity_filters.items():
                    if ev is not None:
                        val = r.metadata.get(ek)
                        if val is not None and str(val).lower() != str(ev).lower():
                            match = False
                            break
                if match:
                    filtered_results.append(r)
            if filtered_results:
                dense_results = filtered_results

        # 3. Hybrid score fusion with sparse keyword matching
        fused_results: list[tuple[VectorSearchResult, float]] = []
        for r in dense_results:
            sparse_score = _compute_sparse_keyword_score(query, r.content)
            final_score = round(dense_weight * r.score + sparse_weight * sparse_score, 4)
            fused_results.append((r, final_score))

        # Re-sort by fused score
        fused_results.sort(key=lambda x: x[1], reverse=True)
        top_fused = fused_results[:k]

        top_confidence = top_fused[0][1] if top_fused else 0.0
        insufficient = top_confidence < min_conf or len(top_fused) == 0

        # 4. Construct safe citations and formatted context block
        citations: list[RAGCitation] = []
        context_blocks: list[str] = []

        for r, score in top_fused:
            doc_title = r.title or r.metadata.get("document_title") or "FOH Document"
            # Format 120-char excerpt
            clean_snippet = re.sub(r"\s+", " ", r.content).strip()[:140]
            citations.append(
                RAGCitation(
                    id=r.chunk_id,
                    title=doc_title,
                    domain=r.domain,
                    snippet=clean_snippet,
                    confidence=score,
                )
            )
            context_blocks.append(
                f"[Source: {doc_title} | Domain: {r.domain} | Confidence: {score}]\n{r.content}"
            )

        context_text = "\n\n---\n\n".join(context_blocks)
        total_latency = (time.time() - start_time) * 1000

        # 5. Record RAG query log if db session provided
        if db:
            try:
                log_entry = RAGQueryLog(
                    id=f"rql_{uuid.uuid4().hex[:12]}",
                    tenant_id=tenant_id,
                    branch_id=branch_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    query_text=query,
                    domain=domain,
                    chunks_retrieved_count=len(top_fused),
                    top_confidence=top_confidence,
                    retrieval_latency_ms=total_latency - emb_latency,
                    embedding_latency_ms=emb_latency,
                    total_latency_ms=total_latency,
                    insufficient_evidence=insufficient,
                )
                db.add(log_entry)
                db.commit()
            except Exception as err:
                logger.warning("Failed to record RAGQueryLog: %s", err)

        return HybridRetrievalResult(
            query=query,
            chunks=[r for r, _ in top_fused],
            citations=citations,
            top_confidence=top_confidence,
            insufficient_evidence=insufficient,
            context_text=context_text,
            latency_ms=total_latency,
        )


hybrid_retrieval_service = HybridRetrievalService()
