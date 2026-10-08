"""
Enterprise RAG (Retrieval-Augmented Generation) & Knowledge Base Database Models
────────────────────────────────────────────────────────────────────────────────
Provides structured, multi-tenant persistence for restaurant SOPs, menu metadata,
historical operational incident summaries, and vision event knowledge.
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeSource(Base):
    """
    Logical grouping / repository of knowledge (e.g., 'Restaurant Operational SOPs',
    'Menu Culinary Profiles', 'Vision Anomaly Archive').
    """
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # RESTAURANT_SOP | MENU | OPERATIONAL_HISTORY | INCIDENT | VISION | STAFF_TRAINING
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    documents: Mapped[list["KnowledgeDocument"]] = relationship(
        "KnowledgeDocument", back_populates="source", cascade="all, delete-orphan"
    )


class KnowledgeDocument(Base):
    """
    A single knowledge document, policy, procedure, or structured knowledge item.
    Supports atomic versioning and content hashes for seamless re-indexing.
    """
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON-encoded dictionary of extra metadata
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ACTIVE | ARCHIVED | DEPRECATED
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    source: Mapped["KnowledgeSource"] = relationship("KnowledgeSource", back_populates="documents")
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk", back_populates="document", cascade="all, delete-orphan"
    )


class KnowledgeChunk(Base):
    """
    A single semantically coherent chunk of a document with its vector embedding.
    Stored as JSON-encoded array of floats for universal SQLite & PostgreSQL compatibility.
    """
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    branch_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    domain: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON-encoded list of floats: "[0.012, -0.045, ...]"
    embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    # JSON-encoded tags, headings, or structural breadcrumbs
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    document: Mapped["KnowledgeDocument"] = relationship("KnowledgeDocument", back_populates="chunks")


class RAGQueryLog(Base):
    """
    Audit and performance observability log for all RAG retrieval executions.
    """
    __tablename__ = "rag_query_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    branch_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chunks_retrieved_count: Mapped[int] = mapped_column(Integer, default=0)
    top_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    retrieval_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    embedding_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    total_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    insufficient_evidence: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, index=True)

    feedback: Mapped[list["RAGFeedback"]] = relationship(
        "RAGFeedback", back_populates="query_log", cascade="all, delete-orphan"
    )


class RAGFeedback(Base):
    """
    User feedback on RAG answers (HELPFUL, UNHELPFUL, INCORRECT) for quality evaluation.
    """
    __tablename__ = "rag_feedback"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    query_log_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("rag_query_logs.id", ondelete="SET NULL"), nullable=True
    )
    feedback_type: Mapped[str] = mapped_column(String(32), nullable=False)  # HELPFUL | UNHELPFUL | INCORRECT
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    query_log: Mapped["RAGQueryLog | None"] = relationship("RAGQueryLog", back_populates="feedback")
