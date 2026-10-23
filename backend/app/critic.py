"""Critic / adversary role.

Deterministic checks always run. An optional LLM semantic pass adds observations,
but those are labelled as model-observed and are never automatically treated as
correct by the resolution engine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from .config import Settings
from .facts import (
    extract_fact_sentences,
    extract_scopes,
    find_measure_conflict,
    focus_tokens,
    format_measure,
    grounding_ratio,
    scopes_compatible,
)
from .llm import LLMClient, LLMError
from .retrieval import RetrievalResult
from .schemas import (
    Claim,
    ConflictStatement,
    CriticFinding,
    PassageHit,
    SourceDocument,
)

CONFLICT_KINDS = {"contradiction", "staleness", "supersession", "scope_mismatch"}


@dataclass
class CritiqueResult:
    findings: list[CriticFinding] = field(default_factory=list)
    used_llm: bool = False
    llm_attempted: bool = False
    note: str = ""


class LLMCriticItem(BaseModel):
    kind: Literal[
        "contradiction",
        "staleness",
        "supersession",
        "scope_mismatch",
        "unsupported_claim",
        "evidence_gap",
    ]
    severity: Literal["info", "low", "medium", "high"]
    passage_ids: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=8)
    suggested_action: str = Field(min_length=3)


class LLMCritique(BaseModel):
    findings: list[LLMCriticItem] = Field(default_factory=list)


CRITIC_SYSTEM_PROMPT = """You are the ADVERSARIAL CRITIC in a document-verification pipeline.
Challenge the candidate answer using ONLY the supplied evidence passages and metadata.
Look for direct contradictions, stale or superseded sources, scope mismatches, claims that
lack evidence, and missing information. Do not invent facts or passage IDs.
Return a single JSON object:
{"findings": [{"kind": "contradiction|staleness|supersession|scope_mismatch|unsupported_claim|evidence_gap",
  "severity": "info|low|medium|high", "passage_ids": ["..."],
  "explanation": "what is wrong and why", "suggested_action": "what to do"}]}
Only include findings that are materially useful. No markdown fences."""


def _statement(hit: PassageHit, sentence: str) -> ConflictStatement:
    return ConflictStatement(
        passage_id=hit.passage_id,
        document_id=hit.document_id,
        title=hit.title,
        doc_type=hit.doc_type,
        version=hit.version,
        published_date=hit.published_date,
        effective_date=hit.effective_date,
        authority_label=hit.authority_label,
        page=hit.page,
        statement=sentence.strip(),
    )


def _doc_date(document: SourceDocument) -> date | None:
    return document.effective_date or document.published_date


def _date_text(value: date | None) -> str:
    return value.isoformat() if value else "no recorded date"


def _supersedes(newer: SourceDocument, older: SourceDocument) -> bool:
    older_keys = {older.id.strip().lower(), older.title.strip().lower()}
    return any(target.strip().lower() in older_keys for target in newer.supersedes)


def _is_informational(document: SourceDocument) -> bool:
    return document.doc_type == "faq" or (
        document.authority_rank is None and document.doc_type in {"faq", "document"}
    )


def _authority_decisive(first: SourceDocument, second: SourceDocument) -> bool:
    if first.authority_rank is None or second.authority_rank is None:
        return False
    return abs(first.authority_rank - second.authority_rank) >= 25


def _newer_doc(
    first: SourceDocument, second: SourceDocument
) -> tuple[SourceDocument, SourceDocument]:
    first_date = _doc_date(first)
    second_date = _doc_date(second)
    if first_date and second_date and first_date != second_date:
        return (first, second) if first_date > second_date else (second, first)
    return second, first


def _conflict_finding(
    *,
    finding_id: str,
    doc_a: SourceDocument,
    doc_b: SourceDocument,
    hit_a: PassageHit,
    hit_b: PassageHit,
    sentence_a: str,
    sentence_b: str,
    measure_a,
    measure_b,
    as_of: date,
    overlap: float,
) -> CriticFinding:
    supersession_ab = _supersedes(doc_a, doc_b)
    supersession_ba = _supersedes(doc_b, doc_a)
    newer, older = _newer_doc(doc_a, doc_b)
    statement_scopes_a = extract_scopes(sentence_a)
    statement_scopes_b = extract_scopes(sentence_b)
    scope_a = statement_scopes_a or extract_scopes(doc_a.scope or "")
    scope_b = statement_scopes_b or extract_scopes(doc_b.scope or "")
    scope_mismatch = not scopes_compatible(scope_a, scope_b)

    if supersession_ab or supersession_ba:
        kind = "supersession"
        superseding = doc_a if supersession_ab else doc_b
        effective = superseding.effective_date
        if effective and effective > as_of:
            timing = (
                f"Its effective date {effective.isoformat()} is after the reference date "
                f"{as_of.isoformat()}, so it must not be applied yet."
            )
            severity = "high"
            action = (
                "Do not apply the superseding document as of the reference date; apply the "
                "currently effective source and note the future amendment."
            )
        else:
            timing = (
                f"It has a recorded effective date of {_date_text(effective)} and explicitly "
                "claims supersession."
            )
            severity = "high"
            action = (
                "Follow the explicit supersession only after confirming the effective date, "
                "then cite both the amendment and the document it replaces."
            )
        explanation = (
            f"{doc_a.title} v{doc_a.version} states: “{sentence_a}” "
            f"{doc_b.title} v{doc_b.version} states: “{sentence_b}” "
            f"{superseding.title} v{superseding.version} explicitly supersedes "
            f"{(doc_b if superseding is doc_a else doc_a).title}. {timing}"
        )
    elif scope_mismatch:
        kind = "scope_mismatch"
        severity = "medium"
        explanation = (
            f"The statements differ ({format_measure(measure_a)} vs {format_measure(measure_b)}) "
            f"and the passages appear to cover different populations or regions. "
            f"{doc_a.title} scope: {doc_a.scope or 'not recorded'}. "
            f"{doc_b.title} scope: {doc_b.scope or 'not recorded'}."
        )
        action = "Establish which scope applies to the question before comparing the values."
    elif _is_informational(newer) and not _authority_decisive(doc_a, doc_b):
        kind = "staleness"
        severity = "high" if newer.doc_type == "faq" else "medium"
        explanation = (
            f"The newer source ({newer.title} v{newer.version}, {_date_text(_doc_date(newer))}) "
            f"states {format_measure(measure_a if newer is doc_a else measure_b)}, while "
            f"{older.title} v{older.version} ({_date_text(_doc_date(older))}) states "
            f"{format_measure(measure_b if newer is doc_a else measure_a)}. "
            "The newer source is informational, has no recorded authority rank, and does not "
            "explicitly supersede the older document. Newness alone is not proof of authority."
        )
        action = (
            "Check whether the newer source was formally approved. If not, do not treat it as "
            "controlling; report the entitlement as unestablished."
        )
    else:
        kind = "contradiction"
        severity = "high"
        explanation = (
            f"Two applicable passages make incompatible claims about "
            f"{'currency amounts' if measure_a.unit == 'INR' else 'the same fact'}: "
            f"{doc_a.title} v{doc_a.version} ({_date_text(_doc_date(doc_a))}) states "
            f"{format_measure(measure_a)}, while {doc_b.title} v{doc_b.version} "
            f"({_date_text(_doc_date(doc_b))}) states {format_measure(measure_b)}. "
            "No explicit supersession relationship between these documents was found."
        )
        action = (
            "Apply an explicit scope, authority or effective-date rule. If no rule establishes "
            "precedence, present both positions and abstain."
        )

    return CriticFinding(
        id=finding_id,
        kind=kind,
        severity=severity,
        passage_ids=[hit_a.passage_id, hit_b.passage_id],
        statements=[_statement(hit_a, sentence_a), _statement(hit_b, sentence_b)],
        explanation=explanation,
        suggested_action=action,
        source="deterministic",
    )


def _unsupported_claim_findings(
    claims: list[Claim], hits: list[PassageHit], start: int
) -> list[CriticFinding]:
    hit_map = {hit.passage_id: hit for hit in hits}
    findings: list[CriticFinding] = []
    counter = start
    for claim in claims:
        support_ids = [sid for sid in claim.support_ids if sid in hit_map]
        invalid_ids = [sid for sid in claim.support_ids if sid not in hit_map]
        if invalid_ids:
            counter += 1
            findings.append(
                CriticFinding(
                    id=f"f{counter}",
                    kind="citation_error",
                    severity="high",
                    passage_ids=[],
                    explanation=(
                        f"Candidate claim {claim.id} cites passage IDs that are not in the "
                        f"retrieved evidence: {', '.join(invalid_ids)}."
                    ),
                    suggested_action="Reject the claim until it is supported by a real excerpt.",
                    source="deterministic",
                )
            )
        if not claim.support_ids:
            counter += 1
            findings.append(
                CriticFinding(
                    id=f"c{claim.id}",
                    kind="unsupported_claim",
                    severity="high",
                    passage_ids=[],
                    explanation=f"Candidate claim has no supporting passage: “{claim.text}”",
                    suggested_action="Remove the claim or explicitly qualify it as unverified.",
                    source="deterministic",
                )
            )
            continue
        if not support_ids:
            counter += 1
            findings.append(
                CriticFinding(
                    id=f"c{claim.id}",
                    kind="unsupported_claim",
                    severity="high",
                    passage_ids=[],
                    explanation=(
                        f"No valid support remains for candidate claim “{claim.text}”. "
                        "Every cited passage ID was invalid."
                    ),
                    suggested_action="Remove the claim from the final answer.",
                    source="deterministic",
                )
            )
            continue
        support_text = "\n".join(hit_map[sid].text for sid in support_ids)
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
        if missing_measures:
            counter += 1
            findings.append(
                CriticFinding(
                    id=f"c{claim.id}",
                    kind="unsupported_claim",
                    severity="high",
                    passage_ids=support_ids,
                    explanation=(
                        f"Candidate claim states {', '.join(format_measure(m) for m in missing_measures)}, "
                        "but that value does not appear in the cited supporting passage(s)."
                    ),
                    suggested_action=(
                        "Remove the unsupported value or cite a passage that states it."
                    ),
                    source="deterministic",
                )
            )
        elif ratio < 0.45:
            counter += 1
            findings.append(
                CriticFinding(
                    id=f"c{claim.id}",
                    kind="unsupported_claim",
                    severity="medium",
                    passage_ids=support_ids,
                    explanation=(
                        f"Candidate claim overlaps its cited evidence only {int(ratio * 100)}% by "
                        "content terms. The citation may be mismatched or paraphrased too freely."
                    ),
                    suggested_action=(
                        "Revalidate the claim against the excerpt; qualify or remove it if not "
                        "directly supported."
                    ),
                    source="deterministic",
                )
            )
    return findings


def _llm_critique(
    question: str,
    as_of: date,
    retrieval: RetrievalResult,
    candidate_answer: str,
    settings: Settings,
    client: LLMClient,
) -> list[CriticFinding]:
    hit_map = {hit.passage_id: hit for hit in retrieval.hits}
    evidence = [
        {
            "passage_id": hit.passage_id,
            "title": hit.title,
            "version": hit.version,
            "page": hit.page,
            "published_date": hit.published_date.isoformat() if hit.published_date else None,
            "effective_date": hit.effective_date.isoformat() if hit.effective_date else None,
            "authority_label": hit.authority_label,
            "scope": hit.scope,
            "text": hit.text,
        }
        for hit in retrieval.hits
    ]
    user = (
        f"Question: {question}\nAs-of date: {as_of.isoformat()}\n"
        f"Candidate answer:\n{candidate_answer}\n\n"
        f"Evidence:\n{json.dumps(evidence, ensure_ascii=False, indent=2)}"
    )
    payload = client.complete_json(CRITIC_SYSTEM_PROMPT, user)
    try:
        parsed = LLMCritique.model_validate(payload)
    except ValidationError as exc:
        raise LLMError(f"Critic JSON failed schema validation: {exc.error_count()} error(s)") from exc
    findings: list[CriticFinding] = []
    for item in parsed.findings:
        valid_ids = [pid for pid in item.passage_ids if pid in hit_map]
        if item.kind in CONFLICT_KINDS and not valid_ids:
            continue
        if item.kind in CONFLICT_KINDS:
            statements = []
            for pid in valid_ids[:4]:
                hit = hit_map[pid]
                first_sentence = hit.text.split(". ")[0].strip()
                statements.append(_statement(hit, first_sentence))
        else:
            statements = []
        findings.append(
            CriticFinding(
                id=f"llm{len(findings) + 1}",
                kind=item.kind,
                severity=item.severity,
                passage_ids=valid_ids,
                statements=statements,
                explanation=item.explanation.strip(),
                suggested_action=item.suggested_action.strip(),
                source="llm",
            )
        )
    return findings


def critique(
    question: str,
    as_of: date,
    retrieval: RetrievalResult,
    documents: dict[str, SourceDocument],
    candidate_answer: str,
    claims: list[Claim],
    settings: Settings,
    client: LLMClient | None = None,
) -> CritiqueResult:
    findings: list[CriticFinding] = []
    counter = 0
    by_document: dict[str, list[PassageHit]] = {}
    for hit in retrieval.hits:
        by_document.setdefault(hit.document_id, []).append(hit)
    doc_ids = list(by_document)
    conflict_doc_pairs: set[tuple[str, str]] = set()
    no_precedence: list[tuple[SourceDocument, SourceDocument]] = []
    missing_dates: list[str] = []

    question_focus = focus_tokens(question)
    for first_index, doc_a_id in enumerate(doc_ids):
        for doc_b_id in doc_ids[first_index + 1 :]:
            doc_a = documents.get(doc_a_id)
            doc_b = documents.get(doc_b_id)
            if not doc_a or not doc_b:
                continue
            best = None
            for hit_a in by_document[doc_a_id]:
                for hit_b in by_document[doc_b_id]:
                    match = find_measure_conflict(hit_a.text, hit_b.text)
                    if match is None:
                        continue
                    if best is None or match[4] > best[0]:
                        best = (match[4], hit_a, hit_b, match)
            if best is None:
                continue
            overlap, hit_a, hit_b, match = best
            sentence_a, sentence_b, measure_a, measure_b = match[0], match[1], match[2], match[3]
            if question_focus and not (
                (focus_tokens(sentence_a.sentence) | focus_tokens(sentence_b.sentence))
                & question_focus
            ):
                # Both statements may pass lexical retrieval while discussing a
                # different subject. Do not raise a conflict they never raise.
                continue
            counter += 1
            finding = _conflict_finding(
                finding_id=f"f{counter}",
                doc_a=doc_a,
                doc_b=doc_b,
                hit_a=hit_a,
                hit_b=hit_b,
                sentence_a=sentence_a.sentence,
                sentence_b=sentence_b.sentence,
                measure_a=measure_a,
                measure_b=measure_b,
                as_of=as_of,
                overlap=overlap,
            )
            findings.append(finding)
            conflict_doc_pairs.add((doc_a_id, doc_b_id))
            if finding.kind in {"contradiction", "staleness", "scope_mismatch"}:
                has_supersession = _supersedes(doc_a, doc_b) or _supersedes(doc_b, doc_a)
                if not has_supersession and not _authority_decisive(doc_a, doc_b):
                    no_precedence.append((doc_a, doc_b))
                if not doc_a.effective_date or not doc_b.effective_date:
                    missing_dates.extend([doc_a.title, doc_b.title])

    findings.extend(_unsupported_claim_findings(claims, retrieval.hits, counter))
    counter = len(findings)

    if no_precedence:
        counter += 1
        pairs = "; ".join(f"{a.title} v{a.version} vs {b.title} v{b.version}" for a, b in no_precedence)
        findings.append(
            CriticFinding(
                id=f"f{counter}",
                kind="evidence_gap",
                severity="medium",
                passage_ids=[],
                explanation=(
                    f"The corpus does not establish precedence for {pairs}. No explicit "
                    "supersession link or decisive authority rule applies to the conflicting "
                    "statements."
                ),
                suggested_action=(
                    "Abstain from selecting a winner unless an applicable precedence rule can be "
                    "documented from the corpus."
                ),
                source="deterministic",
            )
        )
    if retrieval.coverage < 0.5:
        counter += 1
        findings.append(
            CriticFinding(
                id=f"f{counter}",
                kind="evidence_gap",
                severity="medium" if retrieval.coverage >= 0.3 else "high",
                passage_ids=[hit.passage_id for hit in retrieval.hits[:4]],
                explanation=(
                    f"Only {int(retrieval.coverage * 100)}% of distinct question terms appear in "
                    "the retrieved evidence. The answer may not address the question as asked."
                ),
                suggested_action="Ask a narrower question or add relevant documents to the corpus.",
                source="deterministic",
            )
        )
    question_scopes = extract_scopes(question)
    if question_scopes:
        evidence_scopes: set[str] = set()
        for hit in retrieval.hits:
            evidence_scopes |= extract_scopes(hit.text)
            document = documents.get(hit.document_id)
            if document and document.scope:
                evidence_scopes |= extract_scopes(document.scope)
        if not (question_scopes & evidence_scopes):
            counter += 1
            findings.append(
                CriticFinding(
                    id=f"f{counter}",
                    kind="evidence_gap",
                    severity="high",
                    passage_ids=[],
                    explanation=(
                        "The question names a population or region ("
                        + ", ".join(sorted(question_scopes))
                        + ") that no retrieved document explicitly covers."
                    ),
                    suggested_action="Do not answer for that scope without supporting evidence.",
                    source="deterministic",
                )
            )
    if missing_dates:
        counter += 1
        findings.append(
            CriticFinding(
                id=f"f{counter}",
                kind="evidence_gap",
                severity="low",
                passage_ids=[],
                explanation=(
                    "At least one side of a conflict has no effective date ("
                    + ", ".join(sorted(set(missing_dates)))
                    + "). Applicability cannot be confirmed from metadata alone."
                ),
                suggested_action="Treat the conflict conservatively; do not invent a date.",
                source="deterministic",
            )
        )

    result = CritiqueResult(findings=findings)
    if settings.llm_configured:
        result.llm_attempted = True
        try:
            llm_findings = _llm_critique(
                question,
                as_of,
                retrieval,
                candidate_answer,
                settings,
                client or LLMClient(settings),
            )
            existing_keys = {
                (finding.kind, tuple(sorted(finding.passage_ids))) for finding in findings
            }
            for finding in llm_findings:
                if (finding.kind, tuple(sorted(finding.passage_ids))) in existing_keys:
                    continue
                findings.append(finding)
            result.used_llm = True
            result.note = (
                f"Semantic LLM critique completed via {settings.llm_model}; findings are marked "
                "as model-observed and are not authoritative."
            )
        except LLMError as exc:
            result.note = f"Semantic LLM critique unavailable: {exc}. Deterministic checks still ran."
    else:
        result.note = (
            "Semantic LLM contradiction analysis skipped: no LLM_API_KEY configured. "
            "Deterministic numeric, metadata and citation checks ran."
        )
    return result
