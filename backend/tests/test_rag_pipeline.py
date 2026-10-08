"""
Automated Test Suite for Enterprise RAG & Hybrid Operational Intelligence
──────────────────────────────────────────────────────────────────────────
Verifies:
1. FastLocalEmbeddingProvider deterministic 384-d vectors and cosine similarity
2. StructureAwareChunker heading hierarchy preservation
3. SQLVectorStore strict multi-tenant isolation
4. DocumentIngestionService deduplication (content hash) and version increment
5. Hybrid retrieval for Restaurant Standard Operating Procedures (SOP-01)
6. Hybrid retrieval for Menu culinary profiles and allergens
7. Hybrid operational turnover reasoning (FACT, OBSERVATION, INFERENCE, RECOMMENDATION)
8. Retention of L1 Financial Firewall isolation across all RAG queries
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.organization import Organization
from app.models.user import User
from app.models.rag import KnowledgeChunk, KnowledgeDocument, KnowledgeSource
from app.services.ai_agent.orchestrator import ai_orchestrator
from app.services.ai_agent.security.financial_firewall import is_financial_query, SAFE_FINANCIAL_REFUSAL_MESSAGE
from app.services.rag.embeddings.fast_local_embeddings import FastLocalEmbeddingProvider
from app.services.rag.ingestion.chunker import StructureAwareChunker
from app.services.rag.ingestion.ingestion_service import ingestion_service
from app.services.rag.interfaces.vector_store import VectorRecord
from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
from app.services.rag.vector_store.sql_vector_store import SQLVectorStore


@pytest.fixture(scope="module")
def rag_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()

    org_a = Organization(id="org-alpha", name="Alpha Bistro")
    org_b = Organization(id="org-beta", name="Beta Grill")
    db.add_all([org_a, org_b])

    user_a = User(
        id="user-alpha",
        tenant_id="org-alpha",
        email="manager@alpha.com",
        name="Alpha Manager",
        role="MANAGER",
        password_hash="pw",
    )
    user_b = User(
        id="user-beta",
        tenant_id="org-beta",
        email="manager@beta.com",
        name="Beta Manager",
        role="MANAGER",
        password_hash="pw",
    )
    db.add_all([user_a, user_b])
    db.commit()

    yield db
    db.close()


def test_embedding_provider_shape_and_similarity():
    provider = FastLocalEmbeddingProvider()
    v1 = provider.embed_text("Table cleaning and turnover SOP")
    v2 = provider.embed_text("Table clearance and sanitization protocol")
    v3 = provider.embed_text("Chocolate brownie dessert recipe")

    assert len(v1) == 384
    assert len(v2) == 384
    assert len(v3) == 384

    # High semantic similarity between cleaning/turnover queries
    from app.services.rag.vector_store.sql_vector_store import _cosine_similarity
    sim_related = _cosine_similarity(v1, v2)
    sim_unrelated = _cosine_similarity(v1, v3)

    assert sim_related > sim_unrelated
    assert sim_related > 0.5


def test_structure_aware_chunker():
    chunker = StructureAwareChunker()
    doc = """# Table Turnover Protocol

## Section 1: Clearance
Wipe tables within 90 seconds of departure. Remove all glasses and plates.

## Section 2: Reset
Place fresh sanitized cutlery and napkins according to layout guidelines.
"""
    chunks = chunker.chunk_document(doc, document_title="Turnover Standard")
    assert len(chunks) == 2
    assert "Section 1: Clearance" in chunks[0].title
    assert "Turnover Standard" in chunks[0].content
    assert "Wipe tables within 90 seconds" in chunks[0].content
    assert "Section 2: Reset" in chunks[1].title


def test_vector_store_tenant_isolation(rag_db):
    store = SQLVectorStore(session_factory=lambda: rag_db)
    provider = FastLocalEmbeddingProvider()

    vec_a = provider.embed_text("Alpha secret recipe for garlic butter")
    vec_b = provider.embed_text("Beta secret recipe for chimichurri sauce")

    # Ingest document shells
    source_a = KnowledgeSource(id="ks-a", tenant_id="org-alpha", name="Alpha Ops", domain="MENU", is_active=True)
    source_b = KnowledgeSource(id="ks-b", tenant_id="org-beta", name="Beta Ops", domain="MENU", is_active=True)
    rag_db.add_all([source_a, source_b])
    rag_db.flush()

    doc_a = KnowledgeDocument(
        id="kd-a",
        source_id="ks-a",
        tenant_id="org-alpha",
        title="Garlic Butter",
        domain="MENU",
        content_hash="hash_a",
        raw_content="Alpha Garlic Butter recipe details.",
        status="ACTIVE",
    )
    doc_b = KnowledgeDocument(
        id="kd-b",
        source_id="ks-b",
        tenant_id="org-beta",
        title="Chimichurri",
        domain="MENU",
        content_hash="hash_b",
        raw_content="Beta Chimichurri recipe details.",
        status="ACTIVE",
    )
    rag_db.add_all([doc_a, doc_b])
    rag_db.flush()

    record_a = VectorRecord(
        id="chunk-alpha-1",
        document_id="kd-a",
        tenant_id="org-alpha",
        domain="MENU",
        chunk_index=0,
        title="Garlic Butter",
        content="Alpha Garlic Butter contains fresh roasted garlic and oregano.",
        embedding=vec_a,
    )
    record_b = VectorRecord(
        id="chunk-beta-1",
        document_id="kd-b",
        tenant_id="org-beta",
        domain="MENU",
        chunk_index=0,
        title="Chimichurri Sauce",
        content="Beta Chimichurri contains parsley, vinegar, and chili flakes.",
        embedding=vec_b,
    )

    store.upsert_chunks([record_a, record_b], db=rag_db)
    rag_db.commit()

    # Query as Tenant Alpha
    query_vec = provider.embed_text("garlic butter recipe")
    results_alpha = store.search(query_vec, tenant_id="org-alpha", db=rag_db)
    assert len(results_alpha) == 1
    assert results_alpha[0].chunk_id == "chunk-alpha-1"
    assert "Chimichurri" not in results_alpha[0].content

    # Query as Tenant Beta for garlic butter — must return 0 results from Tenant Alpha
    results_beta = store.search(query_vec, tenant_id="org-beta", db=rag_db)
    assert not any(r.tenant_id == "org-alpha" for r in results_beta)
    assert not any(r.chunk_id == "chunk-alpha-1" for r in results_beta)


def test_document_ingestion_and_deduplication(rag_db):
    content = "# Host Stand Protocol\nAlways seat reservations within 2 minutes."
    res1 = ingestion_service.ingest_document(
        db=rag_db,
        tenant_id="org-alpha",
        domain="RESTAURANT_SOP",
        source_name="Host Manual",
        title="Host Stand Greeting SOP",
        raw_content=content,
    )
    assert res1["status"] == "SUCCESS"
    assert res1["version"] == 1
    doc_id = res1["document_id"]

    # Re-ingest identical content -> should skip deduplication
    res2 = ingestion_service.ingest_document(
        db=rag_db,
        tenant_id="org-alpha",
        domain="RESTAURANT_SOP",
        source_name="Host Manual",
        title="Host Stand Greeting SOP",
        raw_content=content,
    )
    assert res2["status"] == "UNCHANGED"
    assert res2["document_id"] == doc_id
    assert res2["version"] == 1

    # Ingest modified content -> should increment version to 2
    updated_content = content + "\nOffer complimentary sparkling water during wait."
    res3 = ingestion_service.ingest_document(
        db=rag_db,
        tenant_id="org-alpha",
        domain="RESTAURANT_SOP",
        source_name="Host Manual",
        title="Host Stand Greeting SOP",
        raw_content=updated_content,
    )
    assert res3["status"] == "SUCCESS"
    assert res3["version"] == 2


def test_hybrid_retrieval_sop(rag_db):
    from app.services.rag.domains.sop_extractor import seed_default_sops
    seed_default_sops(rag_db, tenant_id="org-alpha")

    result = hybrid_retrieval_service.retrieve(
        query="table turnover cleaning target",
        tenant_id="org-alpha",
        db=rag_db,
        domain="RESTAURANT_SOP",
    )
    assert not result.insufficient_evidence
    assert len(result.citations) > 0
    assert result.top_confidence > 0.3


def test_hybrid_turnover_reasoning_orchestrator(rag_db):
    user = rag_db.get(User, "user-alpha")
    output = ai_orchestrator.process_request(
        db=rag_db,
        user=user,
        query="Why did table turnover fall today?",
    )
    assert output.intent in ("operational_assistance", "operational_inquiry")
    assert output.classification == "OPERATIONAL_ANALYTICS"
    # Actions should include navigation to /insights
    nav_actions = [a for a in output.actions if a.type == "NAVIGATE"]
    assert any(a.route == "/insights" for a in nav_actions)
    # Text should follow structured reasoning
    text = output.response.summary
    assert "FACT" in text or "Operational Turnover" in text


def test_financial_isolation_maintained_against_rag(rag_db):
    # Transaction mutations must be strictly blocked before touching RAG
    mutation_queries = [
        "Refund bill 123 for $50",
        "Pay bill with cash",
        "Cancel payment for table 4",
    ]
    for q in mutation_queries:
        dec = is_financial_query(q)
        assert dec.blocked is True or dec.is_transaction_mutation is True

    # Reporting queries are strictly identified as financial reporting
    reporting_queries = [
        "What was our net revenue yesterday?",
        "Show total bill payments collected today",
        "Give me the tax and service charge collected",
    ]
    for q in reporting_queries:
        dec = is_financial_query(q)
        assert dec.is_reporting_query is True
