"""Pydantic contracts shared by the API, pipeline and tests."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    """Naive UTC timestamp used for SQLite serialization without deprecation warnings."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

DocType = Literal[
    "policy",
    "amendment",
    "handbook",
    "faq",
    "sop",
    "guideline",
    "standard",
    "circular",
    "document",
]
ResolutionStatus = Literal[
    "resolved",
    "conflict_unresolved",
    "insufficient_evidence",
    "no_relevant_evidence",
]
Severity = Literal["info", "low", "medium", "high"]
FindingKind = Literal[
    "contradiction",
    "staleness",
    "supersession",
    "unsupported_claim",
    "scope_mismatch",
    "evidence_gap",
    "citation_error",
]
Mode = Literal["deterministic", "llm_assisted"]


class DocumentRef(BaseModel):
    document_id: str
    title: str
    version: str


class SourceDocument(BaseModel):
    """Stored metadata for one corpus document."""

    id: str
    title: str
    doc_type: DocType = "document"
    version: str = "1.0"
    published_date: date | None = None
    effective_date: date | None = None
    supersedes: list[str] = Field(default_factory=list)
    authority_rank: int | None = None
    authority_label: str | None = None
    scope: str | None = None
    source_filename: str | None = None
    is_sample: bool = False
    page_count: int = 1
    created_at: datetime = Field(default_factory=utc_now)


class StoredPassage(BaseModel):
    id: str
    document_id: str
    page: int
    ordinal: int
    text: str


class DocumentSummary(BaseModel):
    id: str
    title: str
    doc_type: DocType
    version: str
    published_date: date | None
    effective_date: date | None
    supersedes: list[str]
    authority_rank: int | None
    authority_label: str | None
    scope: str | None
    source_filename: str | None
    is_sample: bool
    page_count: int
    passage_count: int
    created_at: datetime
    superseded_by: list[DocumentRef] = Field(default_factory=list)
    missing_metadata: list[str] = Field(default_factory=list)


class DocumentDetail(DocumentSummary):
    passages: list[StoredPassage] = Field(default_factory=list)


class CorpusStats(BaseModel):
    documents: int
    passages: int
    sample_documents: int
    uploaded_documents: int
    supersession_links: int


class DocumentsResponse(BaseModel):
    documents: list[DocumentSummary]
    stats: CorpusStats


class DemoScenario(BaseModel):
    id: str
    label: str
    question: str
    hint: str
    expected_status: ResolutionStatus
    expected_outcome: str


class ScenariosResponse(BaseModel):
    scenarios: list[DemoScenario]
    corpus_note: str


class HealthResponse(BaseModel):
    status: str
    mode: Mode
    mode_note: str
    llm_configured: bool
    model: str
    provider: str
    document_count: int
    version: str


class PassageHit(BaseModel):
    passage_id: str
    document_id: str
    title: str
    doc_type: DocType
    version: str
    page: int
    published_date: date | None
    effective_date: date | None
    authority_rank: int | None
    authority_label: str | None
    scope: str | None
    text: str
    score: float
    rank: int


class Claim(BaseModel):
    id: str
    text: str
    support_ids: list[str] = Field(default_factory=list)
    supported: bool = True
    note: str | None = None


class ConflictStatement(BaseModel):
    passage_id: str
    document_id: str
    title: str
    doc_type: DocType
    version: str
    published_date: date | None
    effective_date: date | None
    authority_label: str | None
    page: int
    statement: str


class CriticFinding(BaseModel):
    id: str
    kind: FindingKind
    severity: Severity
    passage_ids: list[str] = Field(default_factory=list)
    statements: list[ConflictStatement] = Field(default_factory=list)
    explanation: str
    suggested_action: str
    source: Literal["deterministic", "llm"] = "deterministic"


class Conflict(CriticFinding):
    resolution: Literal["resolved", "unresolved"] = "unresolved"
    preferred_document_id: str | None = None
    preferred_document_title: str | None = None
    resolution_note: str = ""
    # Declared direction of a supersession relationship, independent of which
    # document wins under the effective-date rule.
    superseding_document_id: str | None = None
    superseding_document_title: str | None = None
    superseded_document_id: str | None = None
    superseded_document_title: str | None = None


class Citation(BaseModel):
    passage_id: str
    document_id: str
    title: str
    doc_type: DocType
    version: str
    page: int
    published_date: date | None
    effective_date: date | None
    authority_label: str | None
    excerpt: str


class ValidationCheck(BaseModel):
    id: str
    name: str
    passed: bool
    detail: str


class ValidationReport(BaseModel):
    valid: bool
    checks: list[ValidationCheck]
    notes: list[str] = Field(default_factory=list)
    removed_claims: list[str] = Field(default_factory=list)
    semantic_caveat: str = (
        "Citation existence proves provenance, not semantic correctness. A valid citation can "
        "still support a misread claim; the critic and resolution rules reduce this risk but "
        "cannot eliminate it."
    )


class PipelineStage(BaseModel):
    id: str
    name: str
    status: Literal["completed", "fallback", "skipped", "failed"]
    summary: str
    duration_ms: int
    details: dict[str, Any] = Field(default_factory=dict)


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    as_of: date | None = None
    top_k: int = Field(default=8, ge=4, le=20)

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Question is too short")
        return value


class QueryResponse(BaseModel):
    query_id: str
    question: str
    as_of: date
    mode: Mode
    mode_note: str
    answer: str
    status: ResolutionStatus
    claims: list[Claim]
    citations: list[Citation]
    conflicts: list[Conflict]
    critic_findings: list[CriticFinding]
    resolution_reason: str
    resolution_rules: list[str]
    validation: ValidationReport
    pipeline_trace: list[PipelineStage]
    retrieved_passages: list[PassageHit]
    created_at: datetime = Field(default_factory=utc_now)


class UploadResponse(BaseModel):
    document: DocumentDetail
    message: str


class SampleLoadResponse(BaseModel):
    message: str
    loaded: int
    documents: list[DocumentSummary]
    stats: CorpusStats


class DeleteResponse(BaseModel):
    message: str
    deleted_id: str
