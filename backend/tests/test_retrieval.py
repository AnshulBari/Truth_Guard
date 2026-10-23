from __future__ import annotations

from app.db import Database
from app.retrieval import retrieve


def test_retrieves_competing_documents_with_provenance(db: Database) -> None:
    result = retrieve(
        db,
        "What is the current expense reimbursement limit for client entertainment in India?",
    )
    assert result.hits
    titles = {hit.title for hit in result.hits}
    assert "Finance & Expense Policy" in titles
    assert "Finance Circular 2025-07: Expense Limit Amendment" in titles
    assert result.coverage >= 0.8

    for hit in result.hits:
        assert hit.passage_id
        assert hit.document_id
        assert hit.version
        assert hit.page >= 1
        assert hit.score > 0
        assert hit.rank >= 1
        assert hit.text


def test_bm25_scores_are_ordered(db: Database) -> None:
    result = retrieve(db, "contractor purchase approval threshold in India")
    scores = [hit.score for hit in result.hits]
    assert scores == sorted(scores, reverse=True)
    assert any("Procurement SOP" == hit.title for hit in result.hits)
    assert any("Contractor Engagement Guidelines" == hit.title for hit in result.hits)


def test_irrelevant_query_has_no_evidence(db: Database) -> None:
    result = retrieve(db, "What is the capital of France?")
    assert result.hits == []
    assert result.has_evidence is False


def test_corpus_cap_returns_multiple_documents(db: Database) -> None:
    result = retrieve(db, "annual leave days full-time employees India")
    assert len({hit.document_id for hit in result.hits}) >= 2


def test_empty_corpus_returns_no_hits(empty_db: Database) -> None:
    result = retrieve(empty_db, "What is the expense limit?")
    assert result.hits == []
    assert result.coverage == 0
    assert result.has_evidence is False
