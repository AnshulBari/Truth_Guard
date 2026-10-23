"""Resolution engine.

Rules are applied in a fixed order:
1. question scope
2. explicit supersession with an established effective date
3. documented source authority
4. effective dates (never "newest wins")
5. revalidation of the selected evidence
6. otherwise abstain

The resolver never uses confidence language from the synthesizer or critic to
choose a winner. Every winner is backed by a named rule and validated citations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .critic import CONFLICT_KINDS
from .facts import extract_scopes, grounding_ratio
from .retrieval import RetrievalResult
from .schemas import (
    Citation,
    Claim,
    Conflict,
    CriticFinding,
    PassageHit,
    ResolutionStatus,
    SourceDocument,
)
from .synthesizer import SynthesisResult

RULE_SCOPE = "scope"
RULE_SUPERSESSION = "supersession"
RULE_AUTHORITY = "authority"
RULE_EFFECTIVE = "effective_date"
RULE_REVALIDATION = "revalidation"
RULE_ABSTAIN = "abstain_no_precedence"


@dataclass
class ConflictOutcome:
    finding: CriticFinding
    resolution: str
    note: str
    rules: list[str] = field(default_factory=list)
    preferred: SourceDocument | None = None
    winner_hit: PassageHit | None = None
    loser_hit: PassageHit | None = None
    winner_statement: str | None = None
    loser_statement: str | None = None


@dataclass
class ResolutionOutcome:
    status: ResolutionStatus
    answer: str
    claims: list[Claim] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    reason: str = ""
    rules: list[str] = field(default_factory=list)
    selected_hits: list[PassageHit] = field(default_factory=list)


def _effective(document: SourceDocument, as_of: date) -> bool:
    if document.effective_date:
        return document.effective_date <= as_of
    if document.published_date:
        return document.published_date <= as_of
    return False


def _citation(hit: PassageHit, excerpt: str) -> Citation:
    return Citation(
        passage_id=hit.passage_id,
        document_id=hit.document_id,
        title=hit.title,
        doc_type=hit.doc_type,
        version=hit.version,
        page=hit.page,
        published_date=hit.published_date,
        effective_date=hit.effective_date,
        authority_label=hit.authority_label,
        excerpt=excerpt.strip(),
    )


def _sentence_excerpt(text: str, limit: int = 360) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _supersedes(newer: SourceDocument, older: SourceDocument) -> bool:
    keys = {older.id.strip().lower(), older.title.strip().lower()}
    return any(target.strip().lower() in keys for target in newer.supersedes)


def _query_scope_match(
    question: str,
    first: SourceDocument,
    second: SourceDocument,
    first_scopes: set[str],
    second_scopes: set[str],
    hit_a: PassageHit,
    hit_b: PassageHit,
) -> tuple[SourceDocument, PassageHit, str] | None:
    query_scopes = extract_scopes(question)
    if not query_scopes:
        return None
    scopes_a = first_scopes | extract_scopes(hit_a.text) | extract_scopes(first.scope or "")
    scopes_b = second_scopes | extract_scopes(hit_b.text) | extract_scopes(second.scope or "")
    score_a = len(query_scopes & scopes_a)
    score_b = len(query_scopes & scopes_b)
    if score_a > score_b:
        return first, hit_a, second
    if score_b > score_a:
        return second, hit_b, first
    return None


def _resolve_conflict(
    finding: CriticFinding,
    *,
    question: str,
    as_of: date,
    documents: dict[str, SourceDocument],
    hit_map: dict[str, PassageHit],
) -> ConflictOutcome:
    if len(finding.statements) < 2:
        return ConflictOutcome(
            finding=finding,
            resolution="unresolved",
            note="The finding does not contain two identifiable statements to compare.",
            rules=[RULE_ABSTAIN],
        )
    statement_a, statement_b = finding.statements[0], finding.statements[1]
    doc_a = documents.get(statement_a.document_id)
    doc_b = documents.get(statement_b.document_id)
    hit_a = hit_map.get(statement_a.passage_id)
    hit_b = hit_map.get(statement_b.passage_id)
    if not doc_a or not doc_b or not hit_a or not hit_b:
        return ConflictOutcome(
            finding=finding,
            resolution="unresolved",
            note="One or both cited passages are missing from the retrieved evidence.",
            rules=[RULE_ABSTAIN],
        )

    def outcome(
        winner: SourceDocument,
        winner_hit: PassageHit,
        loser: SourceDocument,
        loser_hit: PassageHit,
        winner_statement: str,
        loser_statement: str,
        rule: str,
        note: str,
    ) -> ConflictOutcome:
        # Rule 5: revalidate the selected excerpt against the retrieved passage.
        if winner_statement not in winner_hit.text and (
            grounding_ratio(winner_statement, winner_hit.text) < 0.75
        ):
            return ConflictOutcome(
                finding=finding,
                resolution="unresolved",
                note=(
                    "The proposed winning statement could not be revalidated against its "
                    "retrieved passage, so precedence was not applied."
                ),
                rules=[rule, RULE_ABSTAIN],
            )
        return ConflictOutcome(
            finding=finding,
            resolution="resolved",
            note=note,
            rules=[rule, RULE_REVALIDATION],
            preferred=winner,
            winner_hit=winner_hit,
            loser_hit=loser_hit,
            winner_statement=winner_statement,
            loser_statement=loser_statement,
        )

    # Rule 1: does the question itself establish the scope?
    scope_match = _query_scope_match(
        question,
        doc_a,
        doc_b,
        extract_scopes(statement_a.statement),
        extract_scopes(statement_b.statement),
        hit_a,
        hit_b,
    )
    if scope_match:
        winner, winner_hit, loser = scope_match
        if winner.id == doc_a.id:
            return outcome(
                doc_a,
                hit_a,
                doc_b,
                hit_b,
                statement_a.statement,
                statement_b.statement,
                RULE_SCOPE,
                f"The question names a scope covered only by {doc_a.title} v{doc_a.version}; "
                f"{doc_b.title} v{doc_b.version} covers a different population or region. "
                "The contradictory statement was not applied.",
            )
        return outcome(
            doc_b,
            hit_b,
            doc_a,
            hit_a,
            statement_b.statement,
            statement_a.statement,
            RULE_SCOPE,
            f"The question names a scope covered only by {doc_b.title} v{doc_b.version}; "
            f"{doc_a.title} v{doc_a.version} covers a different population or region. "
            "The contradictory statement was not applied.",
        )

    # Rule 2: explicit supersession with an established effective date.
    if _supersedes(doc_a, doc_b) and not _supersedes(doc_b, doc_a):
        superseding, superseded = doc_a, doc_b
        s_hit, o_hit = hit_a, hit_b
        s_statement, o_statement = statement_a.statement, statement_b.statement
        if superseding.effective_date is None:
            return ConflictOutcome(
                finding=finding,
                resolution="unresolved",
                note=(
                    f"{superseding.title} explicitly supersedes {superseded.title}, but no "
                    "effective date is recorded for the superseding document. Its applicability "
                    "cannot be established, so TruthGuard does not apply it."
                ),
                rules=[RULE_SUPERSESSION, RULE_ABSTAIN],
            )
        if superseding.effective_date > as_of:
            if superseded.effective_date and superseded.effective_date <= as_of:
                return outcome(
                    superseded,
                    o_hit,
                    superseding,
                    s_hit,
                    o_statement,
                    s_statement,
                    RULE_EFFECTIVE,
                    f"{superseding.title} v{superseding.version} explicitly supersedes "
                    f"{superseded.title}, but it is not effective until "
                    f"{superseding.effective_date.isoformat()} — after the reference date "
                    f"{as_of.isoformat()}. The currently effective {superseded.title} "
                    f"v{superseded.version} governs instead.",
                )
            return ConflictOutcome(
                finding=finding,
                resolution="unresolved",
                note=(
                    f"{superseding.title} supersedes {superseded.title}, but it is not effective "
                    f"until {superseding.effective_date.isoformat()} and the reference date is "
                    f"{as_of.isoformat()}. Neither document's applicability can be established."
                ),
                rules=[RULE_SUPERSESSION, RULE_EFFECTIVE, RULE_ABSTAIN],
            )
        return outcome(
            superseding,
            s_hit,
            superseded,
            o_hit,
            s_statement,
            o_statement,
            RULE_SUPERSESSION,
            f"{superseding.title} v{superseding.version} explicitly supersedes "
            f"{superseded.title} v{superseded.version}. It is effective "
            f"{superseding.effective_date.isoformat()}, on or before the reference date "
            f"{as_of.isoformat()}, so the superseding statement governs. The earlier document "
            "is retained as provenance and is still cited.",
        )
    if _supersedes(doc_b, doc_a) and not _supersedes(doc_a, doc_b):
        return _resolve_conflict(
            finding.model_copy(
                update={
                    "statements": [statement_b, statement_a],
                    "passage_ids": [hit_b.passage_id, hit_a.passage_id],
                }
            ),
            question=question,
            as_of=as_of,
            documents=documents,
            hit_map=hit_map,
        )

    # Rule 3: documented source authority, only when both ranks exist and differ clearly.
    if (
        doc_a.authority_rank is not None
        and doc_b.authority_rank is not None
        and abs(doc_a.authority_rank - doc_b.authority_rank) >= 25
    ):
        if doc_a.authority_rank > doc_b.authority_rank:
            winner, loser, w_hit, l_hit = doc_a, doc_b, hit_a, hit_b
            w_stmt, l_stmt = statement_a.statement, statement_b.statement
        else:
            winner, loser, w_hit, l_hit = doc_b, doc_a, hit_b, hit_a
            w_stmt, l_stmt = statement_b.statement, statement_a.statement
        if _effective(winner, as_of):
            return outcome(
                winner,
                w_hit,
                loser,
                l_hit,
                w_stmt,
                l_stmt,
                RULE_AUTHORITY,
                f"{winner.title} v{winner.version} carries authority rank "
                f"{winner.authority_rank} ({winner.authority_label or 'documented source'}), "
                f"which is at least 25 points above {loser.title} v{loser.version} "
                f"(rank {loser.authority_rank}). The higher-ranked document is effective as of "
                f"{as_of.isoformat()}, so its statement is applied. No explicit supersession "
                "relationship was claimed.",
            )

    # Rule 4: effective dates, without assuming newest is correct. Apply this
    # rule only when both documents actually record an effective date; a missing
    # date is not evidence that a document is not yet in force.
    if doc_a.effective_date and doc_b.effective_date:
        a_effective = doc_a.effective_date <= as_of
        b_effective = doc_b.effective_date <= as_of
    else:
        a_effective = b_effective = True
    if doc_a.effective_date and doc_b.effective_date and a_effective != b_effective:
        if a_effective:
            return outcome(
                doc_a,
                hit_a,
                doc_b,
                hit_b,
                statement_a.statement,
                statement_b.statement,
                RULE_EFFECTIVE,
                f"{doc_a.title} v{doc_a.version} is effective as of {as_of.isoformat()}, while "
                f"{doc_b.title} v{doc_b.version} is not yet effective. The effective document "
                "governs; the future document is cited but not applied.",
            )
        return outcome(
            doc_b,
            hit_b,
            doc_a,
            hit_a,
            statement_b.statement,
            statement_a.statement,
            RULE_EFFECTIVE,
            f"{doc_b.title} v{doc_b.version} is effective as of {as_of.isoformat()}, while "
            f"{doc_a.title} v{doc_a.version} is not yet effective. The effective document "
            "governs; the future document is cited but not applied.",
        )

    # Rule 6: no decisive rule. Abstain.
    if finding.kind == "staleness":
        note = (
            f"The conflict remains unresolved. {doc_b.title if _is_newer(doc_b, doc_a) else doc_a.title} "
            "is newer, but it is informational, has no recorded authority rank, and does not "
            "explicitly supersede the other document. A newer date alone does not establish "
            "authority, so TruthGuard does not select a winner."
        )
    elif finding.kind == "scope_mismatch":
        note = (
            "The conflict remains unresolved. The sources appear to cover different scopes, and "
            "the question does not establish which scope applies. Neither statement is treated "
            "as universally correct."
        )
    else:
        note = (
            "The conflict remains unresolved. Both documents are applicable, no explicit "
            "supersession relationship exists, and no documented authority rule is decisive. "
            "TruthGuard abstains rather than inventing a winner."
        )
    return ConflictOutcome(
        finding=finding,
        resolution="unresolved",
        note=note,
        rules=[RULE_SCOPE, RULE_SUPERSESSION, RULE_AUTHORITY, RULE_EFFECTIVE, RULE_ABSTAIN],
        winner_hit=None,
        loser_hit=None,
    )


def _is_newer(first: SourceDocument, second: SourceDocument) -> bool:
    first_date = first.effective_date or first.published_date
    second_date = second.effective_date or second.published_date
    if first_date and second_date:
        return first_date > second_date
    return False


def _hit_statement(hit: PassageHit, statement: str | None) -> str:
    return statement.strip() if statement else hit.text.strip()


def _answer_for_resolved(outcome: ConflictOutcome) -> str:
    assert outcome.winner_hit is not None
    hit = outcome.winner_hit
    sentence = (outcome.winner_statement or hit.text).strip().rstrip(".")
    effective = (
        f", effective {hit.effective_date.isoformat()}" if hit.effective_date else ""
    )
    parts = [
        f"{sentence} — {hit.title} v{hit.version}, p. {hit.page} ({effective.lstrip(', ') or 'date not recorded'})."
    ]
    if outcome.preferred and outcome.loser_hit:
        loser = outcome.loser_hit
        parts.append(
            f"The conflicting statement in {loser.title} v{loser.version} (p. {loser.page}) is "
            "retained as provenance; it does not govern under the rule stated below."
        )
    return " ".join(parts)


def _answer_for_unresolved(outcomes: list[ConflictOutcome]) -> str:
    lines = [
        "The corpus does not establish a single authoritative answer to this question. "
        "Both positions are presented below exactly as retrieved."
    ]
    for outcome in outcomes:
        finding = outcome.finding
        if len(finding.statements) >= 2:
            first, second = finding.statements[0], finding.statements[1]
            lines.append(
                f"{first.title} v{first.version} ({first.effective_date or first.published_date or 'no date'}, "
                f"p. {first.page}) states: “{first.statement}”"
            )
            lines.append(
                f"{second.title} v{second.version} ({second.effective_date or second.published_date or 'no date'}, "
                f"p. {second.page}) states: “{second.statement}”"
            )
        else:
            lines.append(finding.explanation)
        lines.append(outcome.note)
    lines.append(
        "TruthGuard is not claiming that either position has been verified as current."
    )
    return "\n\n".join(lines)


def _conflict_model(
    outcome: ConflictOutcome, documents: dict[str, SourceDocument]
) -> Conflict:
    superseding = None
    superseded = None
    if outcome.finding.kind == "supersession" and len(outcome.finding.statements) >= 2:
        first = documents.get(outcome.finding.statements[0].document_id)
        second = documents.get(outcome.finding.statements[1].document_id)
        if first and second:
            if _supersedes(first, second):
                superseding, superseded = first, second
            elif _supersedes(second, first):
                superseding, superseded = second, first
    return Conflict(
        **outcome.finding.model_dump(),
        resolution="resolved" if outcome.resolution == "resolved" else "unresolved",
        preferred_document_id=outcome.preferred.id if outcome.preferred else None,
        preferred_document_title=outcome.preferred.title if outcome.preferred else None,
        resolution_note=outcome.note,
        superseding_document_id=superseding.id if superseding else None,
        superseding_document_title=superseding.title if superseding else None,
        superseded_document_id=superseded.id if superseded else None,
        superseded_document_title=superseded.title if superseded else None,
    )


def resolve(
    question: str,
    as_of: date,
    retrieval: RetrievalResult,
    documents: dict[str, SourceDocument],
    findings: list[CriticFinding],
    synthesis: SynthesisResult,
) -> ResolutionOutcome:
    if not retrieval.hits:
        return ResolutionOutcome(
            status="no_relevant_evidence",
            answer=(
                "No relevant evidence was found in the corpus, so TruthGuard cannot answer. "
                "Load documents or rephrase the question."
            ),
            reason="Retrieval returned no passages above the relevance threshold.",
            rules=["no_evidence"],
        )

    hit_map = {hit.passage_id: hit for hit in retrieval.hits}
    deterministic_conflicts = [
        finding
        for finding in findings
        if finding.source == "deterministic" and finding.kind in CONFLICT_KINDS
    ]
    outcomes: list[ConflictOutcome] = []
    for finding in deterministic_conflicts:
        outcomes.append(
            _resolve_conflict(
                finding,
                question=question,
                as_of=as_of,
                documents=documents,
                hit_map=hit_map,
            )
        )

    # Model-observed conflicts are not automatically correct. A high-severity one
    # forces abstention rather than being accepted as proof or dismissed silently.
    llm_conflicts = [
        finding
        for finding in findings
        if finding.source == "llm"
        and finding.kind in CONFLICT_KINDS
        and finding.severity in {"medium", "high"}
    ]
    unresolved_outcomes = [outcome for outcome in outcomes if outcome.resolution == "unresolved"]
    for finding in llm_conflicts:
        unresolved_outcomes.append(
            ConflictOutcome(
                finding=finding,
                resolution="unresolved",
                note=(
                    "A model-observed semantic finding raised this concern. It is shown for "
                    "review but is not treated as proven; deterministic metadata rules could not "
                    "verify it, so the answer is not presented as resolved."
                ),
                rules=["llm_review", RULE_ABSTAIN],
            )
        )

    claims: list[Claim] = []
    citations: dict[str, Citation] = {}
    selected_hits: dict[str, PassageHit] = {}

    def add_citation(hit: PassageHit, excerpt: str) -> None:
        if hit.passage_id not in citations:
            citations[hit.passage_id] = _citation(hit, _sentence_excerpt(excerpt))
        selected_hits.setdefault(hit.passage_id, hit)

    for finding in llm_conflicts:
        for passage_id in finding.passage_ids[:4]:
            hit = hit_map.get(passage_id)
            if hit:
                add_citation(hit, hit.text)

    for outcome in outcomes:
        finding = outcome.finding
        if outcome.resolution == "resolved" and outcome.winner_hit:
            winner_hit = outcome.winner_hit
            winner_statement = outcome.winner_statement or winner_hit.text
            claim_id = f"final-{len(claims) + 1}"
            claims.append(
                Claim(
                    id=claim_id,
                    text=winner_statement.strip(),
                    support_ids=[winner_hit.passage_id],
                )
            )
            add_citation(winner_hit, winner_statement)
            if outcome.loser_hit and outcome.loser_statement:
                add_citation(outcome.loser_hit, outcome.loser_statement)
                if outcome.rules and RULE_SUPERSESSION in outcome.rules and outcome.preferred:
                    loser_doc = documents.get(outcome.loser_hit.document_id)
                    supersession_hit = next(
                        (
                            candidate
                            for candidate in retrieval.hits
                            if candidate.document_id == outcome.preferred.id
                            and "supersed" in candidate.text.lower()
                        ),
                        None,
                    )
                    if loser_doc and supersession_hit:
                        add_citation(supersession_hit, supersession_hit.text)
                        claims.append(
                            Claim(
                                id=f"final-{len(claims) + 1}",
                                text=(
                                    f"{outcome.preferred.title} v{outcome.preferred.version} "
                                    f"explicitly supersedes the conflicting statement in "
                                    f"{loser_doc.title} v{loser_doc.version}."
                                ),
                                support_ids=[
                                    supersession_hit.passage_id,
                                    outcome.winner_hit.passage_id,
                                    outcome.loser_hit.passage_id,
                                ],
                            )
                        )
        else:
            for statement in finding.statements:
                hit = hit_map.get(statement.passage_id)
                if not hit:
                    continue
                claims.append(
                    Claim(
                        id=f"final-{len(claims) + 1}",
                        text=statement.statement,
                        support_ids=[statement.passage_id],
                    )
                )
                add_citation(hit, statement.statement)

    if not outcomes:
        # No conflict. Reuse supported candidate claims; otherwise fall back to
        # the highest-ranked passage's best sentence.
        supported_candidate = [
            claim
            for claim in synthesis.claims
            if claim.support_ids and all(pid in hit_map for pid in claim.support_ids)
        ]
        if supported_candidate:
            for claim in supported_candidate[:3]:
                claims.append(
                    Claim(
                        id=f"final-{len(claims) + 1}",
                        text=claim.text,
                        support_ids=claim.support_ids,
                    )
                )
                for pid in claim.support_ids:
                    add_citation(hit_map[pid], hit_map[pid].text)
        else:
            top_hit = retrieval.hits[0]
            claims.append(
                Claim(
                    id="final-1",
                    text=top_hit.text.strip(),
                    support_ids=[top_hit.passage_id],
                )
            )
            add_citation(top_hit, top_hit.text)

    all_resolved = bool(outcomes) and all(o.resolution == "resolved" for o in outcomes)
    has_unresolved = bool(unresolved_outcomes)
    rules: list[str] = []
    for outcome in outcomes:
        for rule in outcome.rules:
            if rule not in rules:
                rules.append(rule)
    for outcome in unresolved_outcomes:
        for rule in outcome.rules:
            if rule not in rules:
                rules.append(rule)
    if not outcomes:
        rules = ["evidence_grounding"]

    if has_unresolved:
        reasons = []
        for outcome in outcomes:
            if outcome.resolution == "unresolved":
                reasons.append(outcome.note)
        for outcome in unresolved_outcomes:
            if outcome not in outcomes:
                reasons.append(outcome.note)
        reason = " ".join(dict.fromkeys(reasons)) or (
            "Precedence could not be established from the corpus."
        )
        answer = _answer_for_unresolved(unresolved_outcomes)
        status: ResolutionStatus = "conflict_unresolved"
    elif outcomes:
        reason = " ".join(dict.fromkeys(o.note for o in outcomes if o.resolution == "resolved"))
        answer = " ".join(_answer_for_resolved(outcome) for outcome in outcomes)
        status = "resolved" if all_resolved else "conflict_unresolved"
        if status == "resolved":
            answer += " " + reason
    else:
        high_gap = any(
            finding.kind == "evidence_gap" and finding.severity == "high" for finding in findings
        )
        if retrieval.coverage < 0.2 or high_gap or not claims:
            status = "insufficient_evidence"
            reason = (
                "Related passages were retrieved, but the evidence coverage or scope is "
                "insufficient to support a reliable answer."
            )
            answer = (
                "The corpus contains related material, but not enough to answer reliably. "
                "TruthGuard is reporting an evidence gap instead of guessing."
            )
        else:
            status = "resolved"
            reason = (
                "No contradiction, supersession, authority or scope conflict was detected among "
                "the retrieved passages. The answer is supported by the cited excerpts."
            )
            if synthesis.used_llm and synthesis.candidate_answer and not any(
                finding.kind == "unsupported_claim" and finding.severity == "high"
                for finding in findings
            ):
                answer = synthesis.candidate_answer
            else:
                hit = hit_map[claims[0].support_ids[0]]
                sentence = claims[0].text.strip().rstrip(".")
                effective = (
                    f", effective {hit.effective_date.isoformat()}" if hit.effective_date else ""
                )
                answer = (
                    f"{sentence} — {hit.title} v{hit.version}, p. {hit.page}"
                    f" ({effective.lstrip(', ') or 'date not recorded'}). {reason}"
                )

    ordered_citations = sorted(
        citations.values(),
        key=lambda citation: (
            selected_hits[citation.passage_id].rank
            if citation.passage_id in selected_hits
            else 999
        ),
    )
    return ResolutionOutcome(
        status=status,
        answer=answer.strip(),
        claims=claims,
        citations=ordered_citations,
        conflicts=[_conflict_model(outcome, documents) for outcome in outcomes]
        + [
            Conflict(
                **outcome.finding.model_dump(),
                resolution="unresolved",
                preferred_document_id=None,
                preferred_document_title=None,
                resolution_note=outcome.note,
            )
            for outcome in unresolved_outcomes
            if outcome not in outcomes
        ],
        reason=reason,
        rules=rules,
        selected_hits=list(selected_hits.values()),
    )
