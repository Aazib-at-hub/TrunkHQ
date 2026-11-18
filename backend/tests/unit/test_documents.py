"""
Unit tests for Phase 5 Document Intelligence parsing, validation, and isolation.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.api.deps import TenantContext
from app.api.router import api_router
from app.api.v1.documents import get_project_document
from app.core.exceptions import NotFoundError, ValidationError
from app.ingestion.doc_parser import (
    MAX_DOC_SIZE_BYTES,
    parse_document_segments,
    validate_document_upload,
)


def _run_coro(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_document_routes_registered() -> None:
    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/api/v1/projects/{project_id}/documents" in paths
    assert "/api/v1/projects/{project_id}/documents/{doc_id}" in paths


def test_validate_document_rejects_unsupported_and_oversized() -> None:
    with pytest.raises(ValidationError, match="Unsupported document type"):
        validate_document_upload("malware.exe", b"binary")

    with pytest.raises(ValidationError, match="empty"):
        validate_document_upload("notes.md", b"")

    with pytest.raises(ValidationError, match="10 MB"):
        validate_document_upload("huge.txt", b"x" * (MAX_DOC_SIZE_BYTES + 1))

    assert validate_document_upload("SRS.MD", b"# Architecture") == ".md"


def test_parse_markdown_document_segments() -> None:
    md = b"# System Design\n\nCortex uses PostgreSQL with pgvector for hybrid search.\n"
    chunks = parse_document_segments("architecture.md", md, chunk_size=500, chunk_overlap=50)
    assert len(chunks) == 1
    assert "pgvector" in chunks[0].content
    assert chunks[0].section_title == "architecture"


def test_get_project_document_enforces_org_isolation() -> None:
    tenant = TenantContext(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), role="developer")
    project_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    mock_db = AsyncMock()

    async def _run() -> None:
        with patch("app.api.v1.documents.DocumentRepository") as mock_dao_cls:
            mock_dao_cls.return_value.get_by_id_in_org = AsyncMock(return_value=None)
            with pytest.raises(NotFoundError):
                await get_project_document(
                    project_id=project_id,
                    doc_id=doc_id,
                    tenant=tenant,
                    db=mock_db,
                )

    _run_coro(_run())
