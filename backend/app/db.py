"""SQLite persistence. One short-lived connection per operation keeps this thread-safe."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from .schemas import (
    CorpusStats,
    DocumentDetail,
    DocumentRef,
    DocumentSummary,
    SourceDocument,
    StoredPassage,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    version TEXT NOT NULL,
    published_date TEXT,
    effective_date TEXT,
    supersedes TEXT NOT NULL DEFAULT '[]',
    authority_rank INTEGER,
    authority_label TEXT,
    scope TEXT,
    source_filename TEXT,
    is_sample INTEGER NOT NULL DEFAULT 0,
    page_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS passages (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_passages_document ON passages(document_id);
"""


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.utcnow()


def _row_to_document(row: sqlite3.Row) -> SourceDocument:
    import json

    try:
        supersedes = json.loads(row["supersedes"] or "[]")
    except (TypeError, ValueError):
        supersedes = []
    return SourceDocument(
        id=row["id"],
        title=row["title"],
        doc_type=row["doc_type"],
        version=row["version"],
        published_date=_parse_date(row["published_date"]),
        effective_date=_parse_date(row["effective_date"]),
        supersedes=[str(item) for item in supersedes if str(item).strip()],
        authority_rank=row["authority_rank"],
        authority_label=row["authority_label"],
        scope=row["scope"],
        source_filename=row["source_filename"],
        is_sample=bool(row["is_sample"]),
        page_count=row["page_count"] or 1,
        created_at=_parse_datetime(row["created_at"]),
    )


def _row_to_passage(row: sqlite3.Row) -> StoredPassage:
    return StoredPassage(
        id=row["id"],
        document_id=row["document_id"],
        page=row["page"],
        ordinal=row["ordinal"],
        text=row["text"],
    )


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path), timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        """Commit on success and always close the connection (Windows file locks)."""
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def init(self) -> None:
        with self._session() as conn:
            conn.executescript(SCHEMA)

    def add_document(self, document: SourceDocument, passages: list[StoredPassage]) -> None:
        import json

        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO documents
                (id, title, doc_type, version, published_date, effective_date, supersedes,
                 authority_rank, authority_label, scope, source_filename, is_sample,
                 page_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.id,
                    document.title,
                    document.doc_type,
                    document.version,
                    document.published_date.isoformat() if document.published_date else None,
                    document.effective_date.isoformat() if document.effective_date else None,
                    json.dumps(document.supersedes),
                    document.authority_rank,
                    document.authority_label,
                    document.scope,
                    document.source_filename,
                    1 if document.is_sample else 0,
                    document.page_count,
                    document.created_at.isoformat(),
                ),
            )
            conn.executemany(
                """
                INSERT INTO passages (id, document_id, page, ordinal, text)
                VALUES (?, ?, ?, ?, ?)
                """,
                [(p.id, p.document_id, p.page, p.ordinal, p.text) for p in passages],
            )

    def delete_document(self, document_id: str) -> bool:
        with self._session() as conn:
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            return cursor.rowcount > 0

    def delete_sample_documents(self) -> None:
        with self._session() as conn:
            conn.execute("DELETE FROM documents WHERE is_sample = 1")

    def get_document(self, document_id: str) -> SourceDocument | None:
        with self._session() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        return _row_to_document(row) if row else None

    def list_documents(self) -> list[SourceDocument]:
        with self._session() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY is_sample DESC, published_date DESC, title ASC"
            ).fetchall()
        return [_row_to_document(row) for row in rows]

    def passage_counts(self) -> dict[str, int]:
        with self._session() as conn:
            rows = conn.execute(
                "SELECT document_id, COUNT(*) AS count FROM passages GROUP BY document_id"
            ).fetchall()
        return {row["document_id"]: row["count"] for row in rows}

    def summaries(self) -> list[DocumentSummary]:
        documents = self.list_documents()
        counts = self.passage_counts()
        refs = {
            doc.id: DocumentRef(document_id=doc.id, title=doc.title, version=doc.version)
            for doc in documents
        }
        by_title = {doc.title.strip().lower(): doc.id for doc in documents}
        superseded: dict[str, list[DocumentRef]] = {doc.id: [] for doc in documents}
        for doc in documents:
            for target in doc.supersedes:
                target_id = target if target in refs else by_title.get(target.strip().lower())
                if target_id and target_id in superseded and target_id != doc.id:
                    superseded[target_id].append(refs[doc.id])
        summaries: list[DocumentSummary] = []
        for doc in documents:
            missing = []
            if not doc.published_date:
                missing.append("published_date")
            if not doc.effective_date:
                missing.append("effective_date")
            if not doc.scope:
                missing.append("scope")
            if doc.authority_rank is None:
                missing.append("authority_rank")
            summaries.append(
                DocumentSummary(
                    id=doc.id,
                    title=doc.title,
                    doc_type=doc.doc_type,
                    version=doc.version,
                    published_date=doc.published_date,
                    effective_date=doc.effective_date,
                    supersedes=doc.supersedes,
                    authority_rank=doc.authority_rank,
                    authority_label=doc.authority_label,
                    scope=doc.scope,
                    source_filename=doc.source_filename,
                    is_sample=doc.is_sample,
                    page_count=doc.page_count,
                    passage_count=counts.get(doc.id, 0),
                    created_at=doc.created_at,
                    superseded_by=superseded.get(doc.id, []),
                    missing_metadata=missing,
                )
            )
        return summaries

    def get_document_detail(self, document_id: str) -> DocumentDetail | None:
        summary = next((s for s in self.summaries() if s.id == document_id), None)
        if summary is None:
            return None
        return DocumentDetail(**summary.model_dump(), passages=self.passages_for(document_id))

    def passages_for(self, document_id: str) -> list[StoredPassage]:
        with self._session() as conn:
            rows = conn.execute(
                "SELECT * FROM passages WHERE document_id = ? ORDER BY ordinal", (document_id,)
            ).fetchall()
        return [_row_to_passage(row) for row in rows]

    def list_passages_with_documents(self) -> list[tuple[StoredPassage, SourceDocument]]:
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT p.* FROM passages p
                JOIN documents d ON d.id = p.document_id
                ORDER BY d.title, p.ordinal
                """
            ).fetchall()
        cache: dict[str, SourceDocument] = {}
        result: list[tuple[StoredPassage, SourceDocument]] = []
        for row in rows:
            passage = _row_to_passage(row)
            doc = cache.get(passage.document_id)
            if doc is None:
                doc = self.get_document(passage.document_id)
                if doc is None:
                    continue
                cache[doc.id] = doc
            result.append((passage, doc))
        return result

    def passage_lookup(self) -> dict[str, tuple[StoredPassage, SourceDocument]]:
        return {passage.id: (passage, doc) for passage, doc in self.list_passages_with_documents()}

    def stats(self) -> CorpusStats:
        documents = self.list_documents()
        counts = self.passage_counts()
        links: set[tuple[str, str]] = set()
        by_title = {doc.title.strip().lower(): doc.id for doc in documents}
        for doc in documents:
            for target in doc.supersedes:
                target_id = target if target in {d.id for d in documents} else by_title.get(
                    target.strip().lower()
                )
                if target_id:
                    links.add((doc.id, target_id))
        return CorpusStats(
            documents=len(documents),
            passages=sum(counts.values()),
            sample_documents=sum(1 for d in documents if d.is_sample),
            uploaded_documents=sum(1 for d in documents if not d.is_sample),
            supersession_links=len(links),
        )
