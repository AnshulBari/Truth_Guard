from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from app.config import Settings
from app.db import Database
from app.sample_corpus import load_sample_corpus
from app.schemas import DocType, SourceDocument, StoredPassage


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "truthguard-test.db")
    database.init()
    load_sample_corpus(database)
    return database


@pytest.fixture
def empty_db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "empty-test.db")
    database.init()
    return database


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(db_path=tmp_path / "truthguard-test.db", llm_api_key=None)


def make_document(
    *,
    document_id: str,
    title: str,
    text: str,
    doc_type: DocType = "policy",
    version: str = "1.0",
    published: date = date(2025, 1, 1),
    effective: date | None = date(2025, 1, 1),
    scope: str = "All employees",
    authority_rank: int | None = 70,
    authority_label: str = "Standing policy",
    supersedes: list[str] | None = None,
    page: int = 1,
) -> tuple[SourceDocument, list[StoredPassage]]:
    document = SourceDocument(
        id=document_id,
        title=title,
        doc_type=doc_type,
        version=version,
        published_date=published,
        effective_date=effective,
        supersedes=supersedes or [],
        authority_rank=authority_rank,
        authority_label=authority_label,
        scope=scope,
        source_filename=f"{document_id}.md",
        is_sample=False,
        page_count=max(1, page),
        created_at=datetime(2026, 1, 1),
    )
    passage = StoredPassage(
        id=f"{document_id}-p1",
        document_id=document_id,
        page=page,
        ordinal=1,
        text=text,
    )
    return document, [passage]


def add_document(db: Database, document: SourceDocument, passages: list[StoredPassage]) -> None:
    db.add_document(document, passages)
