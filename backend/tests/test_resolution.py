from __future__ import annotations

from datetime import date

from app.config import Settings
from app.db import Database
from app.pipeline import run_query
from app.sample_corpus import DEMO_SCENARIOS
from tests.conftest import add_document, make_document

EXPENSE = DEMO_SCENARIOS[0].question
LEAVE = DEMO_SCENARIOS[1].question
CONTRACTOR = DEMO_SCENARIOS[2].question


def test_supersession_resolves_to_amendment_and_cites_both(db: Database, settings: Settings) -> None:
    result = run_query(db, settings, EXPENSE, as_of=date(2026, 10, 23))
    assert result.status == "resolved"
    assert "₹8,000" in result.answer
    assert "Finance Circular 2025-07" in result.answer
    assert "Finance & Expense Policy" in result.answer
    assert "supersession" in result.resolution_rules
    resolved = [conflict for conflict in result.conflicts if conflict.resolution == "resolved"]
    assert len(resolved) == 1
    assert resolved[0].preferred_document_title == "Finance Circular 2025-07: Expense Limit Amendment"
    cited_titles = {citation.title for citation in result.citations}
    assert {"Finance & Expense Policy", "Finance Circular 2025-07: Expense Limit Amendment"} <= cited_titles
    assert result.validation.valid is True


def test_effective_date_not_newest_wins(db: Database, settings: Settings) -> None:
    # Before the amendment took effect, the older policy governs — not the newer doc.
    result = run_query(db, settings, EXPENSE, as_of=date(2024, 6, 1))
    assert result.status == "resolved"
    assert "₹5,000" in result.answer
    assert "effective_date" in result.resolution_rules
    assert "Finance Circular 2025-07" in " ".join(
        citation.title for citation in result.citations
    )
    conflict = result.conflicts[0]
    assert conflict.preferred_document_title == "Finance & Expense Policy"
    assert conflict.superseding_document_title == "Finance Circular 2025-07: Expense Limit Amendment"
    assert conflict.superseded_document_title == "Finance & Expense Policy"
    assert result.validation.valid is True


def test_stale_faq_cannot_override_handbook(db: Database, settings: Settings) -> None:
    result = run_query(db, settings, LEAVE, as_of=date(2026, 10, 23))
    assert result.status == "conflict_unresolved"
    assert "12" in result.answer and "18" in result.answer
    assert "not claiming" in result.answer.lower()
    assert any(conflict.kind == "staleness" for conflict in result.conflicts)
    assert all(conflict.preferred_document_title is None for conflict in result.conflicts)
    assert result.validation.valid is True


def test_unresolvable_contractor_conflict_abstains(db: Database, settings: Settings) -> None:
    result = run_query(db, settings, CONTRACTOR, as_of=date(2026, 10, 23))
    assert result.status == "conflict_unresolved"
    assert "₹50,000" in result.answer
    assert "₹1,00,000" in result.answer
    assert "abstain" in result.resolution_reason.lower()
    assert {citation.title for citation in result.citations} == {
        "Procurement SOP",
        "Contractor Engagement Guidelines",
    }
    unresolved = [conflict for conflict in result.conflicts if conflict.resolution == "unresolved"]
    assert unresolved and all(len(conflict.statements) == 2 for conflict in unresolved)
    assert result.validation.valid is True


def test_documented_authority_rule_applies_when_clear(
    empty_db: Database, settings: Settings
) -> None:
    add_document(
        empty_db,
        *make_document(
            document_id="auth-standard",
            title="Access Control Standard",
            text="All workforce accounts must rotate passwords every 90 days.",
            doc_type="standard",
            authority_rank=90,
            authority_label="Mandatory security standard",
        ),
    )
    add_document(
        empty_db,
        *make_document(
            document_id="auth-guideline",
            title="Helpdesk Guidance Note",
            text="All workforce accounts must rotate passwords every 30 days.",
            doc_type="guideline",
            authority_rank=50,
            authority_label="Informal guidance",
        ),
    )
    result = run_query(
        empty_db,
        settings,
        "How often must workforce accounts rotate passwords?",
        as_of=date(2026, 10, 1),
    )
    assert result.status == "resolved"
    assert "authority" in result.resolution_rules
    assert "90 days" in result.answer
    assert any(
        conflict.preferred_document_title == "Access Control Standard"
        for conflict in result.conflicts
    )


def test_effective_date_rule_resolves_future_document(
    empty_db: Database, settings: Settings
) -> None:
    add_document(
        empty_db,
        *make_document(
            document_id="effective-now",
            title="Current Security Policy",
            text="All workforce accounts must rotate passwords every 90 days.",
            effective=date(2024, 1, 1),
            authority_rank=70,
        ),
    )
    add_document(
        empty_db,
        *make_document(
            document_id="effective-future",
            title="Future Security Policy",
            text="All workforce accounts must rotate passwords every 30 days.",
            effective=date(2027, 1, 1),
            authority_rank=70,
        ),
    )
    result = run_query(
        empty_db,
        settings,
        "How often must workforce accounts rotate passwords?",
        as_of=date(2026, 1, 1),
    )
    assert result.status == "resolved"
    assert "effective_date" in result.resolution_rules
    assert "90 days" in result.answer
    assert "Future Security Policy" in " ".join(citation.title for citation in result.citations)


def test_empty_corpus_reports_no_relevant_evidence(
    empty_db: Database, settings: Settings
) -> None:
    result = run_query(empty_db, settings, "What is the expense reimbursement limit?")
    assert result.status == "no_relevant_evidence"
    assert result.citations == []
    assert result.claims == []
    assert "No relevant evidence" in result.answer


def test_missing_evidence_abstains_without_guessing(db: Database, settings: Settings) -> None:
    result = run_query(db, settings, "What is the capital of France?")
    assert result.status == "no_relevant_evidence"
    assert result.conflicts == []
    assert result.validation.valid is True
