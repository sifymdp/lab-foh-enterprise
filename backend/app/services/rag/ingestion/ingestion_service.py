"""
Document Ingestion & Versioning Service
────────────────────────────────────────
Coordinates document normalization, deduplication via content hashes,
version promotion, chunking, embedding generation, and vector store upsertion.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session

from app.config import settings
from app.models.rag import KnowledgeChunk, KnowledgeDocument, KnowledgeSource
from app.services.rag.embeddings.factory import get_embedding_provider
from app.services.rag.ingestion.chunker import StructureAwareChunker
from app.services.rag.interfaces.vector_store import VectorRecord
from app.services.rag.vector_store.factory import get_vector_store

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DocumentIngestionService:
    """Manages full lifecycle of knowledge document ingestion and versioning."""

    def __init__(self) -> None:
        self.chunker = StructureAwareChunker()

    def ingest_document(
        self,
        db: Session,
        tenant_id: str,
        domain: str,
        source_name: str,
        title: str,
        raw_content: str,
        branch_id: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        force_reindex: bool = False,
    ) -> dict[str, Any]:
        """Ingest or update a knowledge document with automatic versioning and vector indexing."""
        content_hash = hashlib.sha256(raw_content.strip().encode("utf-8")).hexdigest()

        # 1. Ensure KnowledgeSource exists
        source = (
            db.query(KnowledgeSource)
            .filter(
                KnowledgeSource.tenant_id == tenant_id,
                KnowledgeSource.name == source_name,
                KnowledgeSource.domain == domain,
            )
            .first()
        )
        if not source:
            source = KnowledgeSource(
                id=f"ks_{uuid.uuid4().hex[:12]}",
                tenant_id=tenant_id,
                branch_id=branch_id,
                name=source_name,
                domain=domain,
                description=f"Auto-registered source for {domain}",
                is_active=True,
            )
            db.add(source)
            db.flush()

        # 2. Check for existing active document with same title
        existing_doc = (
            db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.tenant_id == tenant_id,
                KnowledgeDocument.source_id == source.id,
                KnowledgeDocument.title == title,
                KnowledgeDocument.status == "ACTIVE",
            )
            .first()
        )

        version = 1
        if existing_doc:
            if existing_doc.content_hash == content_hash and not force_reindex:
                logger.info("Document '%s' already indexed with identical hash. Skipping.", title)
                return {
                    "status": "UNCHANGED",
                    "document_id": existing_doc.id,
                    "version": existing_doc.version,
                    "chunks_count": len(existing_doc.chunks),
                }

            # Increment version and archive previous active document
            version = existing_doc.version + 1
            existing_doc.status = "ARCHIVED"
            db.flush()

            # Remove old chunks from vector store
            vector_store = get_vector_store()
            vector_store.delete_by_document(existing_doc.id, tenant_id, db=db)

        # 3. Create new KnowledgeDocument record
        meta_str = json.dumps(metadata) if metadata else None
        doc_id = f"kd_{uuid.uuid4().hex[:12]}"
        new_doc = KnowledgeDocument(
            id=doc_id,
            source_id=source.id,
            tenant_id=tenant_id,
            branch_id=branch_id,
            title=title,
            domain=domain,
            version=version,
            content_hash=content_hash,
            raw_content=raw_content,
            metadata_json=meta_str,
            status="ACTIVE",
            created_by_user_id=user_id,
        )
        db.add(new_doc)
        db.flush()

        # 4. Chunk document
        chunks = self.chunker.chunk_document(
            raw_text=raw_content,
            document_title=title,
            metadata=metadata,
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )

        if not chunks:
            db.commit()
            return {"status": "SUCCESS", "document_id": doc_id, "version": version, "chunks_count": 0}

        # 5. Generate embeddings in batch
        texts_to_embed = [c.content for c in chunks]
        embedding_provider = get_embedding_provider()
        embeddings = embedding_provider.embed_batch(texts_to_embed)

        # 6. Prepare vector records
        vector_records: list[VectorRecord] = []
        for idx, (c, emb) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"kc_{uuid.uuid4().hex[:12]}"
            vector_records.append(
                VectorRecord(
                    id=chunk_id,
                    document_id=doc_id,
                    tenant_id=tenant_id,
                    branch_id=branch_id,
                    domain=domain,
                    chunk_index=c.chunk_index,
                    title=c.title,
                    content=c.content,
                    embedding=emb,
                    metadata=c.metadata,
                )
            )

        # 7. Upsert to Vector Store
        vector_store = get_vector_store()
        vector_store.upsert_chunks(vector_records, db=db)

        db.commit()
        logger.info("Successfully ingested document '%s' (v%d) with %d chunks.", title, version, len(chunks))

        return {
            "status": "SUCCESS",
            "document_id": doc_id,
            "version": version,
            "chunks_count": len(chunks),
        }

    def delete_document(self, db: Session, document_id: str, tenant_id: str) -> bool:
        """Deactivate and delete a knowledge document and its chunks."""
        doc = (
            db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.tenant_id == tenant_id,
            )
            .first()
        )
        if not doc:
            return False

        doc.status = "DEPRECATED"
        # Delete from vector store
        get_vector_store().delete_by_document(document_id, tenant_id, db=db)
        db.commit()
        return True


ingestion_service = DocumentIngestionService()
