from __future__ import annotations

from app.db import Database
from app.schemas import Claim
from app.verifier import verify

from app.pipeline import run_query
from app.sample_corpus import DEMO_SCENARIOS
from app.config import Settings


def test_all_citations_resolve_to_stored_passages(db: Database, settings: Settings) -> None:
    result = run_query(db, settings, DEMO_SCENARIOS[0].question)
    lookup = db.passage_lookup()
    for citation in result.citations:
        assert citation.passage_id in lookup
        passage, document = lookup[citation.passage_id]
        assert citation.document_id == document.id
        assert citation.title == document.title
        assert citation.version == document.version
        assert citation.page == passage.page


def test_unsupported_claim_is_removed_and_validation_fails(db: Database) -> None:
    claim = Claim(
        id="bad-1",
        text="The expense reimbursement limit is ₹99,000 per employee.",
        support_ids=["doc-expense-policy-p2"],
    )
    outcome = verify(
        db,
        status="resolved",
        claims=[claim],
        citations=[],
        conflicts=[],
        resolution_reason="test",
        resolution_rules=["evidence_grounding"],
    )
    assert outcome.claims == []
    assert outcome.report.removed_claims
    assert outcome.report.valid is False
    assert any(check.id == "claims_supported" and not check.passed for check in outcome.report.checks)


def test_fabricated_citation_fails_validation(db: Database) -> None:
    claim = Claim(
        id="bad-2",
        text="The expense limit is ₹5,000.",
        support_ids=["fabricated-passage"],
    )
    outcome = verify(
        db,
        status="resolved",
        claims=[claim],
        citations=[],
        conflicts=[],
        resolution_reason="test",
        resolution_rules=["evidence_grounding"],
    )
    assert outcome.claims == []
    assert any(check.id == "citations_exist" and not check.passed for check in outcome.report.checks)


def test_resolved_response_has_justified_conflict(db: Database, settings: Settings) -> None:
    result = run_query(db, settings, DEMO_SCENARIOS[0].question)
    assert result.validation.valid is True
    check = next(
        item for item in result.validation.checks if item.id == "resolved_conflict_justified"
    )
    assert check.passed
    assert "supersession" in result.resolution_rules


def test_unresolved_response_does_not_claim_verification(
    db: Database, settings: Settings
) -> None:
    result = run_query(db, settings, DEMO_SCENARIOS[2].question)
    assert result.status == "conflict_unresolved"
    assert result.validation.valid is True
    assert any(
        check.id == "no_false_verification" and check.passed
        for check in result.validation.checks
    )
    assert "not claiming" in result.answer.lower()
    assert "verified as current" in result.answer.lower()
