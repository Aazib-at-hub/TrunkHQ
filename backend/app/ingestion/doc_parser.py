"""
TrunkHQ — Document Parser & Chunker.

Extracts structured text segments from engineering documentation
(.pdf, .docx, .md, .txt, .csv, .json, .yaml, .yml, .sql) with strict
extension and size validation.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.chunking.chunker import chunk_text
from app.core.exceptions import ValidationError

ALLOWED_DOC_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".md",
    ".txt",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".sql",
}
MAX_DOC_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@dataclass
class ParsedDocChunk:
    chunk_index: int
    content: str
    section_title: Optional[str] = None
    page_number: Optional[int] = None


def validate_document_upload(filename: str, content_bytes: bytes) -> str:
    """Validate file extension and size; return normalized lowercase extension."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        raise ValidationError(
            f"Unsupported document type '{ext or 'none'}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_DOC_EXTENSIONS))}"
        )
    if not content_bytes:
        raise ValidationError("Uploaded document is empty.")
    if len(content_bytes) > MAX_DOC_SIZE_BYTES:
        raise ValidationError("Document exceeds maximum allowed size of 10 MB.")
    return ext


def compute_sha256(content_bytes: bytes) -> str:
    return hashlib.sha256(content_bytes).hexdigest()


def parse_document_segments(
    filename: str,
    content_bytes: bytes,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> list[ParsedDocChunk]:
    """Extract text segments from an uploaded document and split into chunks."""
    ext = validate_document_upload(filename, content_bytes)
    raw_segments: list[tuple[str, Optional[int], Optional[str]]] = []

    if ext == ".pdf":
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise ValidationError("PDF parsing support (PyMuPDF) is not installed.") from exc
        with fitz.open(stream=content_bytes, filetype="pdf") as pdf_doc:
            for page_idx, page in enumerate(pdf_doc, start=1):
                txt = (page.get_text("text") or "").strip()
                if txt:
                    raw_segments.append((txt, page_idx, f"Page {page_idx}"))

    elif ext == ".docx":
        try:
            import docx
        except ImportError as exc:
            raise ValidationError("DOCX parsing support (python-docx) is not installed.") from exc
        doc = docx.Document(io.BytesIO(content_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        if paragraphs:
            raw_segments.append(("\n".join(paragraphs), None, Path(filename).stem))

    else:
        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = content_bytes.decode("latin-1", errors="replace")
        text = text.strip()
        if text:
            raw_segments.append((text, None, Path(filename).stem))

    if not raw_segments:
        raise ValidationError("No extractable text found in uploaded document.")

    chunks: list[ParsedDocChunk] = []
    idx = 0
    for seg_text, page_num, section in raw_segments:
        for c in chunk_text(seg_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap):
            if c.content.strip():
                chunks.append(
                    ParsedDocChunk(
                        chunk_index=idx,
                        content=c.content,
                        section_title=section,
                        page_number=page_num,
                    )
                )
                idx += 1

    if not chunks:
        raise ValidationError("Document produced zero indexable text chunks.")
    return chunks
