"""TruthGuard API."""

from __future__ import annotations

from datetime import date
from typing import get_args

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .db import Database
from .ingestion import IngestionError, build_document
from .pipeline import run_query
from .sample_corpus import CORPUS_NOTE, DEMO_SCENARIOS, load_sample_corpus
from .schemas import (
    DeleteResponse,
    DocType,
    DocumentDetail,
    DocumentsResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    SampleLoadResponse,
    ScenariosResponse,
    UploadResponse,
)

VERSION = "0.1.0"
DOC_TYPES = set(get_args(DocType))


def _parse_date(value: str | None, field: str) -> date | None:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{field} must be an ISO date (YYYY-MM-DD)") from exc


def _parse_supersedes(value: str | None) -> list[str]:
    if not value:
        return []
    pieces: list[str] = []
    for line in value.replace(",", "\n").splitlines():
        item = line.strip()
        if item and item not in pieces:
            pieces.append(item)
    return pieces


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    db = database or Database(settings.db_path)
    db.init()

    app = FastAPI(
        title="TruthGuard",
        description=(
            "Adversarial verification for multi-agent document Q&A. Deterministic checks "
            "validate citations and conflict resolution; unresolved conflicts are reported "
            "instead of guessed."
        ),
        version=VERSION,
    )
    app.state.db = db
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "name": "TruthGuard API",
            "version": VERSION,
            "docs": "/docs",
            "health": "/api/health",
        }

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            mode=settings.mode,
            mode_note=settings.mode_note,
            llm_configured=settings.llm_configured,
            model=settings.llm_model,
            provider=settings.provider,
            document_count=len(db.list_documents()),
            version=VERSION,
        )

    @app.get("/api/documents", response_model=DocumentsResponse)
    def list_documents() -> DocumentsResponse:
        return DocumentsResponse(documents=db.summaries(), stats=db.stats())

    @app.get("/api/documents/{document_id}", response_model=DocumentDetail)
    def get_document(document_id: str) -> DocumentDetail:
        detail = db.get_document_detail(document_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return detail

    @app.delete("/api/documents/{document_id}", response_model=DeleteResponse)
    def delete_document(document_id: str) -> DeleteResponse:
        if not db.delete_document(document_id):
            raise HTTPException(status_code=404, detail="Document not found")
        return DeleteResponse(message="Document removed from the corpus.", deleted_id=document_id)

    @app.post("/api/documents/upload", response_model=UploadResponse)
    def upload_document(
        file: UploadFile = File(...),
        title: str | None = Form(None),
        doc_type: str | None = Form(None),
        version: str | None = Form(None),
        published_date: str | None = Form(None),
        effective_date: str | None = Form(None),
        supersedes: str | None = Form(None),
        authority_rank: int | None = Form(None),
        authority_label: str | None = Form(None),
        scope: str | None = Form(None),
    ) -> UploadResponse:
        if not file.filename:
            raise HTTPException(status_code=400, detail="An uploaded file with a filename is required")
        data = file.file.read()
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {settings.max_upload_mb} MB upload limit",
            )
        if doc_type and doc_type not in DOC_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"doc_type must be one of: {', '.join(sorted(DOC_TYPES))}",
            )
        if authority_rank is not None and not 0 <= authority_rank <= 100:
            raise HTTPException(status_code=422, detail="authority_rank must be between 0 and 100")
        try:
            document, passages = build_document(
                filename=file.filename,
                data=data,
                title=title,
                doc_type=doc_type or None,  # type: ignore[arg-type]
                version=version,
                published_date=_parse_date(published_date, "published_date"),
                effective_date=_parse_date(effective_date, "effective_date"),
                supersedes=_parse_supersedes(supersedes),
                authority_rank=authority_rank,
                authority_label=authority_label,
                scope=scope,
            )
        except IngestionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        db.add_document(document, passages)
        detail = db.get_document_detail(document.id)
        assert detail is not None
        return UploadResponse(
            document=detail,
            message=f"Indexed {len(passages)} passage(s) from {document.title}.",
        )

    @app.post("/api/demo/load-sample", response_model=SampleLoadResponse)
    def load_sample() -> SampleLoadResponse:
        loaded = load_sample_corpus(db)
        return SampleLoadResponse(
            message=(
                f"Loaded {loaded} fictional demonstration documents. Existing uploads were kept."
            ),
            loaded=loaded,
            documents=db.summaries(),
            stats=db.stats(),
        )

    @app.get("/api/demo/scenarios", response_model=ScenariosResponse)
    def scenarios() -> ScenariosResponse:
        return ScenariosResponse(scenarios=DEMO_SCENARIOS, corpus_note=CORPUS_NOTE)

    @app.post("/api/query", response_model=QueryResponse)
    def query(request: QueryRequest) -> QueryResponse:
        return run_query(
            db,
            settings,
            request.question,
            as_of=request.as_of,
            top_k=request.top_k,
        )

    return app


app = create_app()
