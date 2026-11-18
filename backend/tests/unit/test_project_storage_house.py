"""
Unit tests for shared Project Storage House behavior:
- Any authenticated user can list/read/browse any stored project
- Only the project owner can update, reindex, or delete a project
- Metadata schema validation and tag normalization
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.router import api_router
from app.core.exceptions import ForbiddenError
from app.models.repository import Repository
from app.schemas.repository import ImportRepositoryRequest, UpdateRepositoryRequest
from app.services.repository_service import RepositoryService


def _make_repo(owner_id: uuid.UUID) -> Repository:
    return Repository(
        id=uuid.uuid4(),
        user_id=owner_id,
        name="demo-project",
        github_url="https://github.com/acme/demo-project",
        branch="main",
        description="Shared project",
        tags=["backend", "rag"],
        status="READY",
        file_count=10,
        chunk_count=20,
    )


def test_tag_normalization_dedupes_and_lowercases() -> None:
    req = ImportRepositoryRequest(
        github_url="https://github.com/acme/demo",
        tags=[" Backend ", "RAG", "backend", "  ", "FastAPI"],
    )
    assert req.tags == ["backend", "rag", "fastapi"]

    upd = UpdateRepositoryRequest(tags=["AI", "ai", " Docs "])
    assert upd.tags == ["ai", "docs"]


def test_repository_patch_route_registered() -> None:
    patch_routes = [
        r for r in api_router.routes
        if getattr(r, "path", None) == "/api/v1/repositories/{repo_id}"
        and "PATCH" in getattr(r, "methods", set())
    ]
    assert len(patch_routes) == 1


def _run_coro(coro):
    """Drive an async coroutine to completion without spawning an event loop."""
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_non_owner_can_read_but_cannot_mutate() -> None:
    async def _run() -> None:
        owner_id = uuid.uuid4()
        other_user_id = uuid.uuid4()
        repo = _make_repo(owner_id)

        session = MagicMock()
        session.commit = AsyncMock()
        session_factory = MagicMock()

        service = RepositoryService(session, session_factory)
        service._repo_dao = MagicMock()
        service._repo_dao.get_by_id_shared = AsyncMock(return_value=repo)
        service._repo_dao.update_metadata = AsyncMock(return_value=repo)
        service._repo_dao.delete = AsyncMock(return_value=True)

        # Any authenticated user can read
        fetched = await service.get_repository(repo.id, other_user_id)
        assert fetched.id == repo.id

        # Non-owner cannot update, reindex, or delete
        with pytest.raises(ForbiddenError):
            await service.update_repository(repo.id, other_user_id, description="hijack")

        with pytest.raises(ForbiddenError):
            await service.reindex_repository(repo.id, other_user_id)

        with pytest.raises(ForbiddenError):
            await service.delete_repository(repo.id, other_user_id)

        # Owner can update
        updated = await service.update_repository(repo.id, owner_id, description="Updated")
        assert updated.id == repo.id
        service._repo_dao.update_metadata.assert_awaited_once()

    _run_coro(_run())
