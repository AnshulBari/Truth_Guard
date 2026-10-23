"""BM25 retrieval over stored passages, with per-document caps so competing
evidence is not crowded out by one verbose source."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from .db import Database
from .schemas import PassageHit, SourceDocument, StoredPassage

STOPWORDS = {
    "a",
    "about",
    "after",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "been",
    "before",
    "being",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "current",
    "currently",
    "did",
    "do",
    "does",
    "doing",
    "during",
    "each",
    "for",
    "from",
    "get",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "him",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "me",
    "more",
    "most",
    "my",
    "no",
    "not",
    "now",
    "of",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "out",
    "over",
    "own",
    "per",
    "please",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "tell",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "up",
    "us",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
}

CANONICAL = {
    "entitled": "entitle",
    "entitlement": "entitle",
    "entitlements": "entitle",
    "reimbursement": "reimburse",
    "reimbursements": "reimburse",
    "reimbursed": "reimburse",
    "reimburse": "reimburse",
    "approvals": "approval",
    "approved": "approve",
    "approves": "approve",
    "requires": "require",
    "required": "require",
    "requirements": "requirement",
    "purchases": "purchase",
    "purchasing": "purchase",
    "employees": "employee",
    "contractors": "contractor",
    "documents": "document",
    "policies": "policy",
    "limits": "limit",
    "thresholds": "threshold",
    "amended": "amend",
    "amendment": "amend",
    "superseded": "supersede",
    "supersedes": "supersede",
}


def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("₹", " inr ")
    # Only rewrite "rs"/"rs." when it is actually a currency prefix followed by
    # digits. A blanket replace corrupts words such as "contractors".
    text = re.sub(r"\brs\.?\s*(?=\d)", "inr ", text)
    text = re.sub(r"(?<=\d),(?=\d{2})", "", text)
    text = re.sub(r"\bcoo\b", " chief operating officer ", text)
    text = re.sub(r"\bcfo\b", " chief financial officer ", text)
    text = re.sub(r"\bfull[\s-]?time\b", " fulltime ", text)
    text = re.sub(r"\bpart[\s-]?time\b", " parttime ", text)
    text = text.replace("&", " and ")
    text = text.replace("–", "-").replace("—", " ")
    return text


def tokenize(text: str, *, keep_stopwords: bool = False) -> list[str]:
    tokens: list[str] = []
    for raw in re.findall(r"[a-z0-9]+", normalize_text(text)):
        token = CANONICAL.get(raw, raw)
        if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        if not keep_stopwords and token in STOPWORDS:
            continue
        if len(token) == 1 and not token.isdigit():
            continue
        tokens.append(token)
    return tokens


@dataclass
class RetrievalResult:
    hits: list[PassageHit] = field(default_factory=list)
    query_terms: list[str] = field(default_factory=list)
    coverage: float = 0.0
    candidate_count: int = 0
    top_score: float = 0.0

    @property
    def has_evidence(self) -> bool:
        return bool(self.hits) and self.top_score > 0 and self.coverage >= 0.2


class BM25Index:
    def __init__(self, records: list[tuple[StoredPassage, SourceDocument]]):
        self.records = records
        self.tokens = []
        for passage, document in records:
            body = f"{document.title} {document.title} {passage.text}"
            self.tokens.append(tokenize(body))
        self.lengths = [len(tokens) for tokens in self.tokens]
        self.avg_length = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        self.doc_freq: Counter[str] = Counter()
        for tokens in self.tokens:
            self.doc_freq.update(set(tokens))
        self.n_docs = len(self.tokens)
        self.k1 = 1.5
        self.b = 0.75

    def _idf(self, term: str) -> float:
        df = self.doc_freq.get(term, 0)
        if df == 0:
            return 0.0
        return math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))

    def _score(self, index: int, query_terms: Counter[str]) -> float:
        tokens = self.tokens[index]
        if not tokens:
            return 0.0
        freqs = Counter(tokens)
        length = self.lengths[index]
        score = 0.0
        for term, query_freq in query_terms.items():
            tf = freqs.get(term, 0)
            if not tf:
                continue
            idf = self._idf(term)
            denominator = tf + self.k1 * (1 - self.b + self.b * length / (self.avg_length or 1))
            score += idf * (tf * (self.k1 + 1) / denominator) * query_freq
        return score

    def search(
        self, query: str, *, top_k: int = 8, per_document_cap: int = 2
    ) -> tuple[list[tuple[StoredPassage, SourceDocument, float]], list[str], int]:
        query_terms = Counter(tokenize(query))
        if not query_terms:
            return [], [], 0
        scored = []
        for index, record in enumerate(self.records):
            score = self._score(index, query_terms)
            if score > 0:
                scored.append((record[0], record[1], score))
        scored.sort(key=lambda item: (-item[2], item[0].document_id, item[0].ordinal))
        selected: list[tuple[StoredPassage, SourceDocument, float]] = []
        counts: Counter[str] = Counter()
        for item in scored:
            if counts[item[0].document_id] >= per_document_cap:
                continue
            selected.append(item)
            counts[item[0].document_id] += 1
            if len(selected) >= top_k:
                break
        return selected, list(query_terms), len(scored)


def retrieve(db: Database, question: str, *, top_k: int = 8) -> RetrievalResult:
    records = db.list_passages_with_documents()
    if not records:
        return RetrievalResult()
    index = BM25Index(records)
    selected, query_terms, candidate_count = index.search(question, top_k=top_k)
    if not selected:
        return RetrievalResult(query_terms=query_terms, candidate_count=candidate_count)
    max_score = max(item[2] for item in selected) or 1.0
    hits: list[PassageHit] = []
    for rank, (passage, document, score) in enumerate(selected, start=1):
        hits.append(
            PassageHit(
                passage_id=passage.id,
                document_id=document.id,
                title=document.title,
                doc_type=document.doc_type,
                version=document.version,
                page=passage.page,
                published_date=document.published_date,
                effective_date=document.effective_date,
                authority_rank=document.authority_rank,
                authority_label=document.authority_label,
                scope=document.scope,
                text=passage.text,
                score=round(score, 4),
                rank=rank,
            )
        )
    retrieved_terms: set[str] = set()
    for hit in hits:
        retrieved_terms.update(tokenize(hit.text))
    unique_query = set(query_terms)
    matched = len(unique_query & retrieved_terms)
    coverage = matched / len(unique_query) if unique_query else 0.0
    return RetrievalResult(
        hits=hits,
        query_terms=sorted(unique_query),
        coverage=round(coverage, 3),
        candidate_count=candidate_count,
        top_score=round(max_score, 4),
    )
