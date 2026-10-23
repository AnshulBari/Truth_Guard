"""Document extraction and chunking for uploaded PDF, TXT and Markdown files."""

from __future__ import annotations

import re
import uuid
from datetime import date
from pathlib import Path

from .schemas import DocType, SourceDocument, StoredPassage, utc_now

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}
TARGET_CHUNK_CHARS = 900
MAX_CHUNK_CHARS = 1600


class IngestionError(ValueError):
    """User-facing extraction failure."""


def extract_segments(filename: str, data: bytes) -> tuple[list[tuple[int, str]], int]:
    """Return (page, text) segments and the page count."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise IngestionError(
            f"Unsupported file type '{suffix or 'none'}'. Upload a PDF, TXT or Markdown file."
        )
    if not data:
        raise IngestionError("The uploaded file is empty.")
    if suffix == ".pdf":
        return _extract_pdf(data)
    text = data.decode("utf-8-sig", errors="replace")
    pages = text.split("\f")
    segments = [(index + 1, page) for index, page in enumerate(pages) if page.strip()]
    if not segments:
        raise IngestionError("No readable text was found in the document.")
    return segments, max(1, len(pages))


def _extract_pdf(data: bytes) -> tuple[list[tuple[int, str]], int]:
    try:
        # PyMuPDF 1.24+ exposes the package as `pymupdf`; older installs use
        # `fitz`. Prefer the non-conflicting name because unrelated packages
        # on some systems also register a top-level `fitz` module.
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz  # type: ignore[no-redef]
        except ImportError as exc:  # pragma: no cover - dependency issue
            raise IngestionError(
                "PDF parsing requires PyMuPDF. Install backend requirements."
            ) from exc
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise IngestionError(f"Could not read the PDF: {exc}") from exc
    try:
        if document.needs_pass:
            raise IngestionError("The PDF is password-protected. Upload an unlocked copy.")
        segments = []
        for index, page in enumerate(document):
            text = page.get_text("text").strip()
            if text:
                segments.append((index + 1, text))
        page_count = document.page_count
    finally:
        document.close()
    if not segments:
        raise IngestionError(
            "No selectable text was found. Scanned PDFs need OCR before upload."
        )
    return segments, max(1, page_count)


def _split_long_text(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if not sentence:
            continue
        if len(current) + len(sentence) + 1 > TARGET_CHUNK_CHARS and current:
            chunks.append(current.strip())
            current = ""
        current = f"{current} {sentence}".strip()
        while len(current) > MAX_CHUNK_CHARS:
            chunks.append(current[:MAX_CHUNK_CHARS].strip())
            current = current[MAX_CHUNK_CHARS:].strip()
    if current:
        chunks.append(current.strip())
    return chunks or [text[:MAX_CHUNK_CHARS]]


def chunk_segments(
    document_id: str, segments: list[tuple[int, str]]
) -> list[StoredPassage]:
    """Group paragraphs into retrievable passages without crossing page boundaries."""
    chunks: list[tuple[int, str]] = []
    for page, text in segments:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]
        buffer = ""
        for paragraph in paragraphs:
            for piece in _split_long_text(paragraph):
                if not buffer:
                    buffer = piece
                elif len(buffer) + len(piece) + 2 <= TARGET_CHUNK_CHARS:
                    buffer = f"{buffer}\n\n{piece}"
                else:
                    chunks.append((page, buffer))
                    buffer = piece
        if buffer:
            chunks.append((page, buffer))
    passages: list[StoredPassage] = []
    seen: set[str] = set()
    ordinal = 0
    for page, text in chunks:
        cleaned = re.sub(r"[ \t]+", " ", text).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordinal += 1
        passages.append(
            StoredPassage(
                id=f"{document_id}-p{ordinal}",
                document_id=document_id,
                page=page,
                ordinal=ordinal,
                text=cleaned,
            )
        )
    if not passages:
        raise IngestionError("No readable passages could be extracted from the document.")
    return passages


def infer_doc_type(filename: str) -> DocType:
    name = filename.lower()
    for token, doc_type in (
        ("amendment", "amendment"),
        ("circular", "circular"),
        ("faq", "faq"),
        ("handbook", "handbook"),
        ("sop", "sop"),
        ("guideline", "guideline"),
        ("standard", "standard"),
        ("policy", "policy"),
    ):
        if token in name:
            return doc_type  # type: ignore[return-value]
    return "document"


def derive_title(filename: str) -> str:
    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    return re.sub(r"\s+", " ", stem).title() or "Untitled document"


def build_document(
    *,
    filename: str,
    data: bytes,
    title: str | None = None,
    doc_type: DocType | None = None,
    version: str | None = None,
    published_date: date | None = None,
    effective_date: date | None = None,
    supersedes: list[str] | None = None,
    authority_rank: int | None = None,
    authority_label: str | None = None,
    scope: str | None = None,
) -> tuple[SourceDocument, list[StoredPassage]]:
    segments, page_count = extract_segments(filename, data)
    document_id = f"doc-{uuid.uuid4().hex[:10]}"
    passages = chunk_segments(document_id, segments)
    document = SourceDocument(
        id=document_id,
        title=(title or derive_title(filename))[:200],
        doc_type=doc_type or infer_doc_type(filename),
        version=(version or "1.0").strip()[:40],
        published_date=published_date,
        effective_date=effective_date,
        supersedes=[s.strip() for s in (supersedes or []) if s.strip()],
        authority_rank=authority_rank,
        authority_label=(authority_label or "").strip() or None,
        scope=(scope or "").strip() or None,
        source_filename=filename[:200],
        is_sample=False,
        page_count=page_count,
        created_at=utc_now(),
    )
    return document, passages
