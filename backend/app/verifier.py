"""Evidence verification.

This module proves structural properties: cited passages exist, metadata matches,
claims are lexically grounded, and resolved conflicts carry a rule-backed
justification. It does not prove that a cited passage means what the answer says.
That limitation is stated explicitly in every report.
"""

from __future__ import annotations

from dataclasses import dataclass

from .db import Database
from .facts import extract_fact_sentences, format_measure, grounding_ratio
from .schemas import (
    Citation,
    Claim,
    Conflict,
    ResolutionStatus,
    ValidationCheck,
    ValidationReport,
)

PRECEDENCE_RULES = {"scope", "supersession", "authority", "effective_date", "revalidation"}


@dataclass
class ValidationOutcome:
    report: ValidationReport
    claims: list[Claim]


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def verify(
    db: Database,
    *,
    status: ResolutionStatus,
    claims: list[Claim],
    citations: list[Citation],
    conflicts: list[Conflict],
    resolution_reason: str,
    resolution_rules: list[str],
) -> ValidationOutcome:
    lookup = db.passage_lookup()
    checks: list[ValidationCheck] = []
    notes: list[str] = []
    removed: list[Claim] = []

    citation_errors: list[str] = []
    for citation in citations:
        record = lookup.get(citation.passage_id)
        if record is None:
            citation_errors.append(f"{citation.passage_id} does not exist")
            continue
        passage, document = record
        if (
            citation.document_id != document.id
            or citation.title != document.title
            or citation.version != document.version
            or citation.page != passage.page
        ):
            citation_errors.append(
                f"{citation.passage_id} metadata does not match the stored document/page"
            )
            continue
        ratio = grounding_ratio(citation.excerpt, passage.text)
        if ratio < 0.6:
            citation_errors.append(
                f"{citation.passage_id} excerpt is only {int(ratio * 100)}% grounded in the passage"
            )
    if not citations and status not in {"no_relevant_evidence"}:
        citation_errors.append("The answer has no citations for an evidence-bearing response.")
    checks.append(
        ValidationCheck(
            id="citations_exist",
            name="Citations resolve to stored passages",
            passed=not citation_errors,
            detail=(
                f"{len(citations)} citation(s) checked against SQLite provenance."
                if not citation_errors
                else "; ".join(citation_errors[:4])
            ),
        )
    )

    kept: list[Claim] = []
    removal_reasons: list[str] = []
    for claim in claims:
        missing = [pid for pid in claim.support_ids if pid not in lookup]
        if missing or not claim.support_ids:
            removed.append(claim)
            removal_reasons.append(
                f"{claim.id}: no valid supporting passage ({', '.join(missing) or 'none cited'})"
            )
            continue
        support_parts = []
        for pid in claim.support_ids:
            passage, _ = lookup[pid]
            support_parts.append(passage.text)
        support_text = "\n".join(support_parts)
        ratio = grounding_ratio(claim.text, support_text)
        claim_measures = [
            measure
            for sentence in extract_fact_sentences(claim.text)
            for measure in sentence.measures
        ]
        support_measures = [
            measure
            for sentence in extract_fact_sentences(support_text)
            for measure in sentence.measures
        ]
        missing_measures = [
            measure
            for measure in claim_measures
            if not any(
                existing.unit == measure.unit and existing.value == measure.value
                for existing in support_measures
            )
        ]
        if ratio < 0.45 or missing_measures:
            removed.append(claim)
            detail = f"{claim.id}: grounding {int(ratio * 100)}%"
            if missing_measures:
                detail += (
                    "; unsupported value(s) "
                    + ", ".join(format_measure(measure) for measure in missing_measures)
                )
            removal_reasons.append(detail)
            continue
        kept.append(claim.model_copy(update={"supported": True, "note": None}))

    checks.append(
        ValidationCheck(
            id="claims_supported",
            name="Every final claim has grounded evidence",
            passed=not removed,
            detail=(
                f"{len(kept)} final claim(s) passed lexical and numeric support checks."
                if not removed
                else f"{len(removed)} unsupported claim(s) removed: " + "; ".join(removal_reasons[:3])
            ),
        )
    )
    if removed:
        notes.append(
            f"Verification removed {len(removed)} unsupported candidate claim(s) from the final answer."
        )

    cited_ids = {citation.passage_id for citation in citations}
    uncovered = [
        claim.id for claim in kept if any(pid not in cited_ids for pid in claim.support_ids)
    ]
    checks.append(
        ValidationCheck(
            id="citations_cover_claims",
            name="Citations cover every claim",
            passed=not uncovered and not (kept and not citations),
            detail=(
                "Every final claim support passage appears in the citation list."
                if not uncovered
                else f"Claims missing a citation: {', '.join(uncovered)}"
            ),
        )
    )

    resolved_conflicts = [conflict for conflict in conflicts if conflict.resolution == "resolved"]
    if conflicts and status == "resolved":
        missing_preferred = [c.id for c in resolved_conflicts if not c.preferred_document_id]
        missing_reason = [c.id for c in resolved_conflicts if not c.resolution_note.strip()]
        rule_ok = any(rule in PRECEDENCE_RULES for rule in resolution_rules)
        all_resolved = len(resolved_conflicts) == len(conflicts)
        passed = all_resolved and not missing_preferred and not missing_reason and rule_ok
        details = []
        if not all_resolved:
            details.append("a conflict remains unresolved")
        if missing_preferred:
            details.append(f"missing preferred source: {', '.join(missing_preferred)}")
        if missing_reason:
            details.append(f"missing resolution note: {', '.join(missing_reason)}")
        if not rule_ok:
            details.append("no precedence rule recorded")
        checks.append(
            ValidationCheck(
                id="resolved_conflict_justified",
                name="Resolved conflicts have a documented justification",
                passed=passed,
                detail=(
                    f"Applied rules: {', '.join(resolution_rules) or 'none'}; "
                    f"{len(resolved_conflicts)} resolved conflict(s) have preferred sources and notes."
                    if passed
                    else "; ".join(details)
                ),
            )
        )
    else:
        checks.append(
            ValidationCheck(
                id="resolved_conflict_justified",
                name="Resolved conflicts have a documented justification",
                passed=True,
                detail=(
                    "Not applicable: no conflict was declared resolved."
                    if status != "resolved"
                    else "No conflicts were detected; resolution rests on evidence grounding."
                ),
            )
        )

    unresolved = [conflict for conflict in conflicts if conflict.resolution == "unresolved"]
    if status == "conflict_unresolved":
        balanced = bool(unresolved)
        balance_issues: list[str] = []
        citation_docs = {citation.document_id for citation in citations}
        for conflict in unresolved:
            if conflict.source == "llm" and len(conflict.statements) < 2:
                continue
            if len(conflict.statements) < 2:
                balanced = False
                balance_issues.append(f"{conflict.id} does not present both statements")
                continue
            doc_ids = {statement.document_id for statement in conflict.statements[:2]}
            if not doc_ids.issubset(citation_docs):
                balanced = False
                balance_issues.append(f"{conflict.id} does not cite both sides")
        checks.append(
            ValidationCheck(
                id="unresolved_balanced",
                name="Unresolved conflicts present both positions fairly",
                passed=balanced,
                detail=(
                    f"{len(unresolved)} unresolved conflict(s) present both positions and cite "
                    "both sources."
                    if balanced
                    else "; ".join(balance_issues) or "No unresolved conflict was recorded."
                ),
            )
        )
    else:
        checks.append(
            ValidationCheck(
                id="unresolved_balanced",
                name="Unresolved conflicts present both positions fairly",
                passed=True,
                detail="Not applicable: the final status is not conflict_unresolved.",
            )
        )

    false_verification = status == "resolved" and bool(unresolved)
    checks.append(
        ValidationCheck(
            id="no_false_verification",
            name="No unresolved conflict is reported as resolved",
            passed=not false_verification,
            detail=(
                "Status and conflict outcomes agree."
                if not false_verification
                else "A conflict is unresolved but the response claims 'resolved'."
            ),
        )
    )

    final_claims_present = status not in {"resolved", "conflict_unresolved"} or bool(kept)
    checks.append(
        ValidationCheck(
            id="final_claims_present",
            name="The final answer retains supported claims",
            passed=final_claims_present,
            detail=(
                f"{len(kept)} supported claim(s) remain in the final answer."
                if final_claims_present
                else "All claims were removed; the answer is not sufficiently supported."
            ),
        )
    )
    if not final_claims_present:
        notes.append(
            "All final claims failed verification. The answer must not be treated as reliable."
        )

    if status == "conflict_unresolved":
        notes.append(
            "TruthGuard is abstaining: the final answer presents unresolved positions and does "
            "not assert that either has been verified."
        )
    if conflicts and status == "resolved":
        notes.append(
            "Conflict resolution is rule-based; the justification is shown in the conflict "
            "inspector and is not derived from model confidence."
        )
    notes.append(
        "citation existence is not semantic proof: a real citation can still be misread. "
        "The semantic caveat below applies to every response."
    )

    report = ValidationReport(
        valid=all(check.passed for check in checks),
        checks=checks,
        notes=notes,
        removed_claims=[claim.text for claim in removed],
    )
    return ValidationOutcome(report=report, claims=kept)
