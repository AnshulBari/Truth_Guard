"""Synthesizer role.

The synthesizer is deliberately not allowed to resolve conflicts. In
deterministic mode it copies evidence statements verbatim. In LLM mode it may
draft an answer, but every claim is re-checked by the critic and verifier.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel, Field, ValidationError

from .config import Settings
from .facts import best_fact_sentence, content_tokens
from .llm import LLMClient, LLMError
from .retrieval import RetrievalResult
from .schemas import Claim, PassageHit


class LLMClaim(BaseModel):
    text: str = Field(min_length=3)
    support_passage_ids: list[str] = Field(default_factory=list)


class LLMSynthesis(BaseModel):
    answer: str = Field(min_length=3)
    claims: list[LLMClaim] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


@dataclass
class SynthesisResult:
    candidate_answer: str
    claims: list[Claim]
    assumptions: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    method: str = "rules"
    used_llm: bool = False
    note: str = ""
    error: str | None = None


SYNTH_SYSTEM_PROMPT = """You are the SYNTHESIZER in an adversarial document-verification pipeline.
Use only the supplied evidence passages. Do not use outside knowledge.
Do not silently reconcile contradictions: if passages disagree, state both positions.
Every claim must list the passage_ids that directly support it. Never invent passage IDs.
Return a single JSON object with exactly these keys:
{
  "answer": "candidate answer grounded in evidence",
  "claims": [{"text": "one atomic factual claim", "support_passage_ids": ["..."]}],
  "assumptions": ["..."],
  "missing_information": ["..."]
}
No markdown fences, no extra commentary."""


def _claim_id(index: int) -> str:
    return f"c{index}"


def _evidence_payload(hits: list[PassageHit]) -> list[dict[str, object]]:
    return [
        {
            "passage_id": hit.passage_id,
            "document_id": hit.document_id,
            "title": hit.title,
            "doc_type": hit.doc_type,
            "version": hit.version,
            "page": hit.page,
            "published_date": hit.published_date.isoformat() if hit.published_date else None,
            "effective_date": hit.effective_date.isoformat() if hit.effective_date else None,
            "authority_label": hit.authority_label,
            "scope": hit.scope,
            "text": hit.text,
        }
        for hit in hits
    ]


NUMERIC_INTENT = re.compile(
    r"\b(how many|how much|limit|threshold|amount|days?|weeks?|months?|years?|hours?|"
    r"rate|percent(?:age)?|cost|price|salary|reimburse(?:ment|d)?|budget|allowance)\b",
    re.IGNORECASE,
)


def _rule_based_synthesis(
    question: str, as_of: date, retrieval: RetrievalResult
) -> SynthesisResult:
    numeric_intent = bool(NUMERIC_INTENT.search(question))
    chosen: list[tuple[PassageHit, str]] = []
    seen_documents: set[str] = set()
    for hit in retrieval.hits:
        if hit.document_id in seen_documents or len(seen_documents) >= 3:
            continue
        fact = best_fact_sentence(hit.text, question)
        if numeric_intent and (fact is None or not fact.measures):
            # A numeric question should not be answered with a broad scope or
            # approval passage that happens to share keywords.
            continue
        seen_documents.add(hit.document_id)
        sentence = fact.sentence if fact else hit.text.strip()[:400]
        chosen.append((hit, sentence))

    if numeric_intent and not chosen:
        # No measure-bearing evidence exists. Fall back to the best sentences so
        # the critic can still report the evidence gap instead of returning an
        # empty candidate.
        seen_documents.clear()
        for hit in retrieval.hits:
            if hit.document_id in seen_documents or len(seen_documents) >= 3:
                continue
            seen_documents.add(hit.document_id)
            fact = best_fact_sentence(hit.text, question)
            chosen.append((hit, fact.sentence if fact else hit.text.strip()[:400]))

    claims: list[Claim] = []
    lines: list[str] = []
    for hit, sentence in chosen:
        claims.append(
            Claim(
                id=_claim_id(len(claims) + 1),
                text=sentence,
                support_ids=[hit.passage_id],
            )
        )
        lines.append(f"• “{sentence}” — {hit.title} v{hit.version}, p. {hit.page}")
    if not claims:
        candidate = "No evidence statements could be composed from the retrieved passages."
    else:
        candidate = (
            "Unreconciled evidence summary (rule-based): the retrieved corpus contains the "
            "following statements. They are listed as found and have not been reconciled.\n\n"
            + "\n".join(lines)
        )
    retrieved_tokens: set[str] = set()
    for hit in retrieval.hits:
        retrieved_tokens.update(content_tokens(hit.text))
    missing_terms = [term for term in retrieval.query_terms if term not in retrieved_tokens]
    missing = []
    if missing_terms:
        missing.append(
            "No retrieved passage contained these query terms: " + ", ".join(missing_terms[:6])
        )
    if retrieval.coverage < 0.6:
        missing.append(
            f"Query-term coverage in retrieved evidence is {int(retrieval.coverage * 100)}%."
        )
    return SynthesisResult(
        candidate_answer=candidate,
        claims=claims,
        assumptions=[
            f"The reference date for applicability is {as_of.isoformat()}.",
            "The question is assumed to concern the scopes recorded in the retrieved documents "
            "unless it explicitly names another group or region.",
        ],
        missing_information=missing,
        method="rules",
        used_llm=False,
        note=(
            "Rule-based synthesizer: claims are verbatim evidence sentences. No model call was "
            "made and no model output is simulated."
        ),
    )


def _llm_synthesis(
    question: str,
    as_of: date,
    retrieval: RetrievalResult,
    settings: Settings,
    client: LLMClient,
) -> SynthesisResult:
    evidence = _evidence_payload(retrieval.hits)
    user = (
        f"Question: {question}\n"
        f"Reference date (as-of): {as_of.isoformat()}\n"
        f"Evidence passages:\n{json.dumps(evidence, ensure_ascii=False, indent=2)}"
    )
    payload = client.complete_json(SYNTH_SYSTEM_PROMPT, user)
    try:
        parsed = LLMSynthesis.model_validate(payload)
    except ValidationError as exc:
        raise LLMError(f"Synthesizer JSON failed schema validation: {exc.error_count()} error(s)") from exc
    claims = [
        Claim(
            id=_claim_id(index),
            text=claim.text.strip(),
            support_ids=[pid for pid in claim.support_passage_ids if pid],
        )
        for index, claim in enumerate(parsed.claims, start=1)
    ]
    return SynthesisResult(
        candidate_answer=parsed.answer.strip(),
        claims=claims,
        assumptions=parsed.assumptions,
        missing_information=parsed.missing_information,
        method="llm",
        used_llm=True,
        note=f"LLM synthesis via {settings.llm_model} ({settings.provider}).",
    )


def synthesize(
    question: str,
    as_of: date,
    retrieval: RetrievalResult,
    settings: Settings,
    client: LLMClient | None = None,
) -> SynthesisResult:
    if not retrieval.hits:
        return SynthesisResult(
            candidate_answer="",
            claims=[],
            method="rules",
            note="Synthesis skipped: no passages were retrieved.",
        )
    if settings.llm_configured:
        try:
            return _llm_synthesis(question, as_of, retrieval, settings, client or LLMClient(settings))
        except LLMError as exc:
            result = _rule_based_synthesis(question, as_of, retrieval)
            result.error = str(exc)
            result.note = (
                "LLM synthesis failed; fell back to the rule-based synthesizer. "
                "The failure is reported rather than masked."
            )
            return result
    return _rule_based_synthesis(question, as_of, retrieval)
