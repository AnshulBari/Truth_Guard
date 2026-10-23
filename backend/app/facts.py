"""Deterministic fact and scope extraction.

Numeric matching is intentionally conservative: a date/version/measure is only
compared when two sentences share enough subject vocabulary. The resulting
findings are flags for review, not automatic proof of contradiction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .retrieval import tokenize

MEASURE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("INR", re.compile(r"(?:₹|inr|rs\.?)\s*([0-9][0-9,]*(?:\.[0-9]+)?)", re.IGNORECASE)),
    ("INR", re.compile(r"\b([0-9][0-9,]*)\s*(?:rupees|inr)\b", re.IGNORECASE)),
    ("DAYS", re.compile(r"\b(\d{1,3})\s*(?:calendar\s+|working\s+|business\s+)?days?\b", re.I)),
    ("PERCENT", re.compile(r"\b(\d{1,3}(?:\.\d+)?)\s*%")),
    ("HOURS", re.compile(r"\b(\d{1,3})\s*hours?\b", re.IGNORECASE)),
    ("WEEKS", re.compile(r"\b(\d{1,2})\s*weeks?\b", re.IGNORECASE)),
    ("YEARS", re.compile(r"\b(\d{1,2})\s*years?\b", re.IGNORECASE)),
]

UNIT_LABELS = {
    "INR": "currency amounts",
    "DAYS": "day counts",
    "PERCENT": "percentages",
    "HOURS": "hour counts",
    "WEEKS": "week counts",
    "YEARS": "year counts",
}

RULE_MARKERS = {
    "must",
    "may",
    "require",
    "requires",
    "required",
    "entitled",
    "eligible",
    "limit",
    "limits",
    "approval",
    "approve",
    "approve",
    "reimburse",
    "retain",
    "mandatory",
}

GENERIC_FACT_TOKENS = {
    "all",
    "business",
    "calendar",
    "claim",
    "day",
    "days",
    "document",
    "each",
    "employee",
    "employe",
    "entitle",
    "eligible",
    "faq",
    "fulltime",
    "guideline",
    "hour",
    "hours",
    "india",
    "inr",
    "many",
    "may",
    "month",
    "months",
    "must",
    "now",
    "one",
    "parttime",
    "paid",
    "policy",
    "receive",
    "require",
    "section",
    "staff",
    "standard",
    "subject",
    "vendor",
    "week",
    "working",
    "workforce",
    "year",
    "years",
    "weeks",
}

SCOPE_TERMS = {
    "fulltime": "full-time employees",
    "parttime": "part-time employees",
    "contractor": "contractors",
    "intern": "interns",
    "manager": "managers",
    "employee": "employees",
    "vendor": "vendors",
    "staff": "all staff",
}

REGION_TERMS = {
    "india": "India",
    "us": "US",
    "usa": "US",
    "uk": "UK",
    "eu": "EU",
    "tier1": "Tier-1 cities",
    "tier2": "Tier-2 cities",
}

POPULATION_LABELS = set(SCOPE_TERMS.values())
REGION_LABELS = set(REGION_TERMS.values())


@dataclass
class Measure:
    unit: str
    value: float
    raw: str
    sentence: str


@dataclass
class FactSentence:
    sentence: str
    measures: list[Measure] = field(default_factory=list)
    tokens: set[str] = field(default_factory=set)


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _amount(raw: str) -> float:
    try:
        return float(raw.replace(",", "").strip())
    except ValueError:
        return 0.0


def extract_fact_sentences(text: str) -> list[FactSentence]:
    results: list[FactSentence] = []
    for sentence in split_sentences(text):
        sentence = re.sub(r"^[AQ]:\s*", "", sentence).strip()
        if not sentence:
            continue
        measures: list[Measure] = []
        seen: set[tuple[str, float]] = set()
        for unit, pattern in MEASURE_PATTERNS:
            for match in pattern.finditer(sentence):
                value = _amount(match.group(1))
                if (unit, value) in seen:
                    continue
                seen.add((unit, value))
                measures.append(Measure(unit=unit, value=value, raw=match.group(0), sentence=sentence))
        results.append(
            FactSentence(
                sentence=sentence,
                measures=measures,
                tokens={token for token in tokenize(sentence) if not token.isdigit()},
            )
        )
    return results


def content_tokens(text: str) -> set[str]:
    return {token for token in tokenize(text) if not token.isdigit()}


def focus_tokens(text: str) -> set[str]:
    """Content words that identify the subject of a statement, not its boilerplate."""
    return {
        token
        for token in tokenize(text)
        if not token.isdigit() and token not in GENERIC_FACT_TOKENS
    }


def hit_is_relevant(question: str, title: str, text: str) -> bool:
    """Relevance gate that prevents incidental lexical matches from driving critique."""
    question_focus = focus_tokens(question)
    if not question_focus:
        return True
    required = 1 if len(question_focus) == 1 else (3 if len(question_focus) >= 4 else 2)
    return len(question_focus & focus_tokens(f"{title} {text}")) >= required


def statement_similarity(first: str, second: str) -> tuple[float, int]:
    a = content_tokens(first)
    b = content_tokens(second)
    if not a or not b:
        return 0.0, 0
    shared = a & b
    overlap = len(shared) / min(len(a), len(b))
    return overlap, len(shared)


def extract_scopes(text: str) -> set[str]:
    normalized = text.lower()
    tokens = set(tokenize(text))
    scopes = {scopes_label for token, scopes_label in SCOPE_TERMS.items() if token in tokens}
    for token, label in REGION_TERMS.items():
        if re.search(rf"\b{re.escape(token)}\b", normalized):
            scopes.add(label)
    return scopes


def scopes_compatible(first: set[str], second: set[str]) -> bool:
    """Compare populations and regions separately.

    Sharing a region does not make two different employee populations compatible.
    """
    if not first or not second:
        return True
    populations_first = first & POPULATION_LABELS
    populations_second = second & POPULATION_LABELS
    if populations_first and populations_second:
        if not (populations_first & populations_second):
            return False
    regions_first = first & REGION_LABELS
    regions_second = second & REGION_LABELS
    if regions_first and regions_second and not (regions_first & regions_second):
        return False
    return True


def grounding_ratio(claim_text: str, evidence_text: str) -> float:
    claim_tokens = content_tokens(claim_text)
    if not claim_tokens:
        return 0.0
    evidence_tokens = content_tokens(evidence_text)
    return len(claim_tokens & evidence_tokens) / len(claim_tokens)


def _sentence_score(sentence: str, question_tokens: set[str], measures: list[Measure]) -> float:
    tokens = content_tokens(sentence)
    query_overlap = (
        len(tokens & question_tokens) / len(question_tokens) if question_tokens else 0.0
    )
    score = query_overlap
    if measures:
        score += 0.35
    if tokens & RULE_MARKERS:
        score += 0.12
    if len(sentence) < 30:
        score -= 0.1
    return score


def best_fact_sentence(text: str, question: str) -> FactSentence | None:
    """Pick the sentence most relevant to the question, preferring rule-like facts."""
    sentences = extract_fact_sentences(text)
    if not sentences:
        return None
    question_tokens = content_tokens(question)
    best = max(sentences, key=lambda item: _sentence_score(item.sentence, question_tokens, item.measures))
    if _sentence_score(best.sentence, question_tokens, best.measures) <= -0.05:
        return sentences[0]
    return best


def find_measure_conflict(
    first_text: str, second_text: str
) -> tuple[FactSentence, FactSentence, Measure, Measure, float] | None:
    """Find the strongest incompatible numeric statement across two passages."""
    first_sentences = extract_fact_sentences(first_text)
    second_sentences = extract_fact_sentences(second_text)
    best: tuple[FactSentence, FactSentence, Measure, Measure, float] | None = None
    for first in first_sentences:
        for second in second_sentences:
            overlap, shared = statement_similarity(first.sentence, second.sentence)
            if shared < 3 or overlap < 0.3:
                continue
            # The two statements must describe the same kind of fact. Without this
            # gate, "5 days of carry-forward leave" can look like it contradicts
            # "18 days of annual leave".
            focus_a = focus_tokens(first.sentence)
            focus_b = focus_tokens(second.sentence)
            focus_shared = focus_a & focus_b
            focus_union = focus_a | focus_b
            focus_jaccard = len(focus_shared) / len(focus_union) if focus_union else 0.0
            if len(focus_shared) < 2 or focus_jaccard < 0.45:
                continue
            for first_measure in first.measures:
                for second_measure in second.measures:
                    if first_measure.unit != second_measure.unit:
                        continue
                    if first_measure.value == second_measure.value:
                        continue
                    if best is None or overlap > best[4]:
                        best = (first, second, first_measure, second_measure, overlap)
    return best


def format_measure(measure: Measure) -> str:
    if measure.unit == "INR":
        value = int(measure.value) if measure.value == int(measure.value) else measure.value
        return f"₹{value:,}"
    if measure.unit == "PERCENT":
        return f"{measure.value:g}%"
    labels = {
        "DAYS": "days",
        "HOURS": "hours",
        "WEEKS": "weeks",
        "YEARS": "years",
    }
    return f"{int(measure.value)} {labels.get(measure.unit, measure.unit.lower())}"
