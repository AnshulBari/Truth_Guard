"""Pipeline orchestrator: retrieval → synthesis → critique → resolution → validation."""

from __future__ import annotations

import time
import uuid
from datetime import date

from .config import Settings
from .critic import critique
from .db import Database
from .facts import hit_is_relevant
from .resolution import resolve
from .retrieval import RetrievalResult, retrieve, tokenize
from .schemas import (
    PipelineStage,
    QueryResponse,
    ResolutionStatus,
    utc_now,
)
from .synthesizer import SynthesisResult, synthesize
from .verifier import verify


def _ms(start: float) -> int:
    return max(1, int((time.perf_counter() - start) * 1000))


def _mode_note(
    settings: Settings,
    synthesis: SynthesisResult,
    critique_used_llm: bool,
    critique_note: str,
) -> tuple[str, str]:
    used_llm = synthesis.used_llm or critique_used_llm
    if used_llm:
        parts = [
            "LLM-assisted mode. "
            + ("Synthesis used the configured model. " if synthesis.used_llm else "Synthesis used rules. ")
            + (
                "Semantic critique used the configured model. "
                if critique_used_llm
                else "Semantic critique was unavailable. "
            )
            + "Conflict resolution and evidence validation remain deterministic rules."
        ]
        if critique_note:
            parts.append(critique_note)
        return "llm_assisted", " ".join(parts)
    if settings.llm_configured:
        failure = synthesis.error or critique_note or "The configured model path was unavailable."
        return (
            "deterministic",
            "The model API is configured, but this query used deterministic fallback. "
            + failure
            + " No model output is simulated.",
        )
    return "deterministic", settings.mode_note


def run_query(
    db: Database,
    settings: Settings,
    question: str,
    *,
    as_of: date | None = None,
    top_k: int = 8,
) -> QueryResponse:
    reference_date = as_of or date.today()
    documents = {document.id: document for document in db.list_documents()}
    stages: list[PipelineStage] = []

    retrieval_started = time.perf_counter()
    retrieval: RetrievalResult = retrieve(db, question, top_k=top_k)
    raw_hit_count = len(retrieval.hits)
    if retrieval.hits:
        relevant_hits = [
            hit for hit in retrieval.hits if hit_is_relevant(question, hit.title, hit.text)
        ]
        if len(relevant_hits) != len(retrieval.hits):
            query_terms = set(retrieval.query_terms)
            retrieved_terms: set[str] = set()
            for hit in relevant_hits:
                retrieved_terms.update(tokenize(f"{hit.title} {hit.text}"))
            coverage = (
                len(query_terms & retrieved_terms) / len(query_terms) if query_terms else 0.0
            )
            retrieval = RetrievalResult(
                hits=relevant_hits,
                query_terms=retrieval.query_terms,
                coverage=round(coverage, 3),
                candidate_count=retrieval.candidate_count,
                top_score=retrieval.top_score,
            )
    filtered_out = raw_hit_count - len(retrieval.hits)
    documents_retrieved = len({hit.document_id for hit in retrieval.hits})
    stages.append(
        PipelineStage(
            id="retrieval",
            name="Retrieval",
            status="completed",
            summary=(
                f"BM25 retrieved {raw_hit_count} candidate passage(s); "
                f"{len(retrieval.hits)} passed the query-focus relevance gate from "
                f"{documents_retrieved} document(s); query-term coverage "
                f"{int(retrieval.coverage * 100)}%."
            ),
            duration_ms=_ms(retrieval_started),
            details={
                "query_terms": retrieval.query_terms,
                "candidate_count": retrieval.candidate_count,
                "raw_hit_count": raw_hit_count,
                "filtered_out": filtered_out,
                "coverage": retrieval.coverage,
                "top_score": retrieval.top_score,
                "passages": [
                    {
                        "passage_id": hit.passage_id,
                        "title": hit.title,
                        "version": hit.version,
                        "page": hit.page,
                        "score": hit.score,
                        "rank": hit.rank,
                    }
                    for hit in retrieval.hits
                ],
            },
        )
    )

    if not retrieval.hits or not retrieval.has_evidence:
        synthesis = SynthesisResult(
            candidate_answer="",
            claims=[],
            method="rules",
            note="Synthesis skipped: retrieval found no evidence above the relevance threshold.",
        )
        synthesis_started = time.perf_counter()
        stages.append(
            PipelineStage(
                id="synthesis",
                name="Synthesis",
                status="skipped",
                summary="No candidate answer was generated because retrieval found no relevant evidence.",
                duration_ms=_ms(synthesis_started),
                details={
                    "reason": "No evidence above threshold",
                    "coverage": retrieval.coverage,
                },
            )
        )
    else:
        synthesis_started = time.perf_counter()
        synthesis = synthesize(
            question, reference_date, retrieval, settings
        )
        stages.append(
            PipelineStage(
                id="synthesis",
                name="Synthesis",
                status="fallback" if synthesis.error else "completed",
                summary=(
                    (
                        f"LLM synthesizer produced {len(synthesis.claims)} candidate claim(s); "
                        "the candidate is unreconciled by design."
                    )
                    if synthesis.used_llm
                    else (
                        f"Rule-based synthesizer produced {len(synthesis.claims)} verbatim "
                        "evidence claim(s); the candidate is unreconciled by design."
                    )
                )
                + (f" LLM fallback reason: {synthesis.error}" if synthesis.error else ""),
                duration_ms=_ms(synthesis_started),
                details={
                    "mode": "llm" if synthesis.used_llm else "rules",
                    "candidate_answer": synthesis.candidate_answer,
                    "claims": [claim.model_dump(mode="json") for claim in synthesis.claims],
                    "assumptions": synthesis.assumptions,
                    "missing_information": synthesis.missing_information,
                    "note": synthesis.note,
                    "error": synthesis.error,
                },
            )
        )

    critique_started = time.perf_counter()
    critique_result = critique(
        question,
        reference_date,
        retrieval,
        documents,
        synthesis.candidate_answer,
        synthesis.claims,
        settings,
    )
    counts: dict[str, int] = {}
    for finding in critique_result.findings:
        counts[finding.kind] = counts.get(finding.kind, 0) + 1
    critique_status = "completed"
    if critique_result.llm_attempted and not critique_result.used_llm:
        critique_status = "fallback"
    stages.append(
        PipelineStage(
            id="critique",
            name="Adversarial critique",
            status=critique_status,
            summary=(
                f"{len(critique_result.findings)} finding(s): "
                + (", ".join(f"{kind}×{count}" for kind, count in sorted(counts.items())) or "none")
                + ". "
                + (
                    "Semantic LLM critique ran; its findings are labelled model-observed."
                    if critique_result.used_llm
                    else critique_result.note
                )
            ),
            duration_ms=_ms(critique_started),
            details={
                "semantic_llm_attempted": critique_result.llm_attempted,
                "semantic_llm_used": critique_result.used_llm,
                "findings": [finding.model_dump(mode="json") for finding in critique_result.findings],
                "note": critique_result.note,
            },
        )
    )

    resolution_started = time.perf_counter()
    resolution = resolve(
        question,
        reference_date,
        retrieval,
        documents,
        critique_result.findings,
        synthesis,
    )
    final_status: ResolutionStatus = resolution.status
    final_answer = resolution.answer
    stages.append(
        PipelineStage(
            id="resolution",
            name="Resolution",
            status="completed",
            summary=(
                f"Status: {final_status}. "
                f"Rules applied: {', '.join(resolution.rules) or 'none'}. "
                f"{resolution.reason}"
            ),
            duration_ms=_ms(resolution_started),
            details={
                "status": final_status,
                "reason": resolution.reason,
                "rules": resolution.rules,
                "conflicts": [conflict.model_dump(mode="json") for conflict in resolution.conflicts],
            },
        )
    )

    validation_started = time.perf_counter()
    validation = verify(
        db,
        status=final_status,
        claims=resolution.claims,
        citations=resolution.citations,
        conflicts=resolution.conflicts,
        resolution_reason=resolution.reason,
        resolution_rules=resolution.rules,
    )
    final_claims = validation.claims
    if not final_claims and final_status == "resolved":
        final_status = "insufficient_evidence"
        final_answer = (
            "Verification removed every supporting claim, so TruthGuard cannot present a "
            "verified answer. The retrieved material is insufficient to support the question."
        )
    if validation.report.removed_claims:
        final_answer += (
            f"\n\nVerification removed {len(validation.report.removed_claims)} unsupported "
            "statement(s) from the final answer. The candidate claims remain visible in the "
            "synthesis trace."
        )
    validation_passed = sum(1 for check in validation.report.checks if check.passed)
    stages.append(
        PipelineStage(
            id="validation",
            name="Evidence validation",
            status="completed",
            summary=(
                f"{validation_passed}/{len(validation.report.checks)} structural checks passed. "
                "Citation existence proves provenance, not semantic truth."
            ),
            duration_ms=_ms(validation_started),
            details={
                "valid": validation.report.valid,
                "checks": [check.model_dump(mode="json") for check in validation.report.checks],
                "notes": validation.report.notes,
                "removed_claims": validation.report.removed_claims,
                "semantic_caveat": validation.report.semantic_caveat,
            },
        )
    )

    mode, mode_note = _mode_note(
        settings, synthesis, critique_result.used_llm, critique_result.note
    )

    return QueryResponse(
        query_id=f"q_{uuid.uuid4().hex[:12]}",
        question=question,
        as_of=reference_date,
        mode=mode,
        mode_note=mode_note,
        answer=final_answer,
        status=final_status,
        claims=final_claims,
        citations=resolution.citations,
        conflicts=resolution.conflicts,
        critic_findings=critique_result.findings,
        resolution_reason=resolution.reason,
        resolution_rules=resolution.rules,
        validation=validation.report,
        pipeline_trace=stages,
        retrieved_passages=retrieval.hits,
        created_at=utc_now(),
    )
