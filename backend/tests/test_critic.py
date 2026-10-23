from __future__ import annotations

from datetime import date

from app.critic import critique
from app.db import Database
from app.pipeline import run_query
from app.retrieval import retrieve
from app.sample_corpus import DEMO_SCENARIOS
from app.config import Settings
from tests.conftest import add_document, make_document

EXPENSE = DEMO_SCENARIOS[0].question
LEAVE = DEMO_SCENARIOS[1].question
CONTRACTOR = DEMO_SCENARIOS[2].question


def test_direct_contradiction_is_detected(db: Database, settings: Settings) -> None:
    result = run_query(db, settings, CONTRACTOR)
    contradictions = [finding for finding in result.critic_findings if finding.kind == "contradiction"]
    assert contradictions
    statements = " ".join(
        statement.statement for finding in contradictions for statement in finding.statements
    )
    assert "₹50,000" in statements
    assert "₹1,00,000" in statements
    assert result.status == "conflict_unresolved"


def test_numeric_question_does_not_synthesize_broad_scope_passage(
    db: Database, settings: Settings
) -> None:
    result = run_query(db, settings, CONTRACTOR)
    synthesis = next(stage for stage in result.pipeline_trace if stage.id == "synthesis")
    claims = synthesis.details.get("claims", [])
    support_ids = {
        passage_id
        for claim in claims
        for passage_id in claim.get("support_ids", [])
    }
    assert "doc-expense-policy-p1" not in support_ids
    assert any("doc-procurement-sop-p1" == passage_id for passage_id in support_ids)
    assert any(
        "doc-contractor-guidelines-p1" == passage_id for passage_id in support_ids
    )


def test_supersession_is_detected(db: Database, settings: Settings) -> None:
    result = run_query(db, settings, EXPENSE)
    supersessions = [finding for finding in result.critic_findings if finding.kind == "supersession"]
    assert supersessions
    finding = supersessions[0]
    assert len(finding.statements) == 2
    assert "supersedes" in finding.explanation.lower()
    assert result.status == "resolved"


def test_newer_informational_source_is_staleness_not_authority(db: Database, settings: Settings) -> None:
    result = run_query(db, settings, LEAVE)
    staleness = [finding for finding in result.critic_findings if finding.kind == "staleness"]
    assert staleness
    assert any("informational" in finding.explanation.lower() for finding in staleness)
    assert result.status == "conflict_unresolved"


def test_scope_mismatch_detected_and_query_scope_resolves(db: Database, settings: Settings) -> None:
    contractor_doc = make_document(
        document_id="scope-contractor-travel",
        title="Contractor Travel Policy",
        text=(
            "Contractor hotel accommodation is reimbursed up to ₹4,000 per night in India."
        ),
        scope="Contractors in India",
        authority_rank=70,
    )
    employee_doc = make_document(
        document_id="scope-employee-travel",
        title="Employee Travel Policy",
        text=(
            "Employee hotel accommodation is reimbursed up to ₹6,000 per night in India."
        ),
        scope="Full-time employees in India",
        authority_rank=70,
    )
    add_document(db, *contractor_doc)
    add_document(db, *employee_doc)

    result = run_query(
        db,
        settings,
        "What is the hotel accommodation limit for contractors in India?",
        as_of=date(2026, 10, 1),
    )
    mismatches = [
        finding for finding in result.critic_findings if finding.kind == "scope_mismatch"
    ]
    assert mismatches
    assert result.status == "resolved"
    assert "scope" in result.resolution_rules
    assert "₹4,000" in result.answer


def test_evidence_gap_for_uncovered_scope(db: Database, settings: Settings) -> None:
    result = run_query(
        db,
        settings,
        "What is the annual leave entitlement for interns in Germany?",
    )
    assert result.status in {"insufficient_evidence", "no_relevant_evidence"}
    assert any(
        finding.kind == "evidence_gap" for finding in result.critic_findings
    )


def test_unsupported_candidate_claim_is_flagged(db: Database, settings: Settings) -> None:
    retrieval = retrieve(db, EXPENSE)
    from app.schemas import Claim

    fake_claim = Claim(
        id="c-bad",
        text="The expense limit is ₹99,000 per employee.",
        support_ids=["passage-that-does-not-exist"],
    )
    result = critique(
        EXPENSE,
        date(2026, 10, 1),
        retrieval,
        {document.id: document for document in db.list_documents()},
        "A candidate answer",
        [fake_claim],
        settings,
    )
    kinds = {finding.kind for finding in result.findings}
    assert "citation_error" in kinds
    assert "unsupported_claim" in kinds
    assert result.findings[-1].source == "deterministic"
