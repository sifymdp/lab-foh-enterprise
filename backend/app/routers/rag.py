"""
Enterprise RAG Knowledge Administration & Feedback Router
──────────────────────────────────────────────────────────
Provides secure endpoints for knowledge ingestion, manual sync triggers,
vector store health monitoring, and user feedback collection.
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_manager_or_owner, require_menu_manager
from app.database import get_db
from app.models.rag import RAGFeedback
from app.models.user import User
from app.services.rag import (
    get_vector_store,
    ingestion_service,
    seed_default_sops,
    sync_menu_to_rag,
    sync_operational_history_to_rag,
    sync_vision_events_to_rag,
)

router = APIRouter(prefix="/rag", tags=["rag"])


class IngestDocumentIn(BaseModel):
    title: str = Field(..., min_length=2)
    domain: str = Field(..., description="RESTAURANT_SOP | MENU | OPERATIONAL_HISTORY | INCIDENT | VISION | STAFF_TRAINING")
    source_name: str = Field("Manual Upload", min_length=2)
    content: str = Field(..., min_length=10)
    metadata: dict[str, Any] | None = None
    force_reindex: bool = False


class RAGFeedbackIn(BaseModel):
    query_log_id: str | None = None
    feedback_type: str = Field(..., description="HELPFUL | UNHELPFUL | INCORRECT")
    notes: str | None = None


@router.get("/health")
def get_rag_health(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Check vector store health, total indexed documents and chunks."""
    store = get_vector_store()
    return store.health_check()


@router.post("/ingest")
def ingest_knowledge_document(
    body: IngestDocumentIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_owner),
) -> dict[str, Any]:
    """Ingest or update a custom knowledge document into the vector store."""
    valid_domains = {"RESTAURANT_SOP", "MENU", "OPERATIONAL_HISTORY", "INCIDENT", "VISION", "STAFF_TRAINING"}
    dom = body.domain.upper().strip()
    if dom not in valid_domains:
        raise HTTPException(status_code=400, detail=f"Invalid domain. Must be one of: {', '.join(valid_domains)}")

    result = ingestion_service.ingest_document(
        db=db,
        tenant_id=user.tenant_id,
        branch_id=user.branch_id,
        user_id=user.id,
        domain=dom,
        source_name=body.source_name,
        title=body.title,
        raw_content=body.content,
        metadata=body.metadata,
        force_reindex=body.force_reindex,
    )
    return result


@router.post("/sync/sops")
def sync_sops(
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_owner),
) -> dict[str, Any]:
    """Seed or update standard operational procedures (SOPs) into RAG."""
    count = seed_default_sops(db, tenant_id=user.tenant_id, branch_id=user.branch_id)
    return {"status": "SUCCESS", "sops_synced": count}


@router.post("/sync/menu")
def sync_menu(
    db: Session = Depends(get_db),
    user: User = Depends(require_menu_manager),
) -> dict[str, Any]:
    """Sync active menu catalog and allergen profiles into RAG."""
    count = sync_menu_to_rag(db, tenant_id=user.tenant_id, branch_id=user.branch_id)
    return {"status": "SUCCESS", "menu_items_synced": count}


@router.post("/sync/operational")
def sync_operational(
    days_back: int = 14,
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_owner),
) -> dict[str, Any]:
    """Summarize recent operational delay bottlenecks into RAG."""
    count = sync_operational_history_to_rag(db, tenant_id=user.tenant_id, branch_id=user.branch_id, days_back=days_back)
    return {"status": "SUCCESS", "operational_archives_synced": count}


@router.post("/sync/vision")
def sync_vision(
    days_back: int = 14,
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_owner),
) -> dict[str, Any]:
    """Summarize recent CCTV camera mismatches and events into RAG."""
    count = sync_vision_events_to_rag(db, tenant_id=user.tenant_id, branch_id=user.branch_id, days_back=days_back)
    return {"status": "SUCCESS", "vision_events_synced": count}


@router.post("/feedback")
def submit_rag_feedback(
    body: RAGFeedbackIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Record user feedback on RAG-generated answers for quality evaluation."""
    import uuid
    fb = RAGFeedback(
        id=f"rfb_{uuid.uuid4().hex[:12]}",
        tenant_id=user.tenant_id,
        user_id=user.id,
        query_log_id=body.query_log_id,
        feedback_type=body.feedback_type.upper().strip(),
        notes=body.notes,
    )
    return {"status": "SUCCESS", "feedback_id": fb.id}


@router.get("/domains")
def list_rag_domains(
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """List all registered RAG domains and their schema configurations."""
    from app.services.rag.domains.registry import domain_registry
    domains = [
        {
            "key": d.key,
            "display_name": d.display_name,
            "description": d.description,
            "source_types": d.source_types,
            "allow_cross_branch": d.allow_cross_branch,
            "requires_forecast_labeling": d.requires_forecast_labeling,
        }
        for d in domain_registry.list_all()
    ]
    return {"domains": domains, "total": len(domains)}


@router.post("/sync/all-domains")
def sync_all_domains(
    db: Session = Depends(get_db),
    user: User = Depends(require_manager_or_owner),
) -> dict[str, Any]:
    """Seed or update operational knowledge across all 17 Enterprise RAG domains."""
    from app.services.rag.domains import seed_all_enterprise_rag_domains
    results = seed_all_enterprise_rag_domains(db, tenant_id=user.tenant_id, branch_id=user.branch_id)
    return {"status": "SUCCESS", "synced_counts": results, "total_domains": len(results)}

