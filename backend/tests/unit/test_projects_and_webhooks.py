"""
Unit tests for Phase 4 multi-repo projects and GitHub webhook verification.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.router import api_router
from app.api.v1.projects import attach_repository_to_project
from app.api.v1.repositories import verify_github_signature
from app.api.deps import TenantContext
from app.core.exceptions import NotFoundError
from app.repositories.project_repo import ProjectRepository


def _run_coro(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_projects_routes_registered() -> None:
    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/api/v1/projects" in paths
    assert "/api/v1/projects/{project_id}" in paths
    assert "/api/v1/projects/{project_id}/repositories/{repo_id}" in paths
    assert "/api/v1/repositories/webhook/github" in paths


def test_verify_github_signature() -> None:
    secret = "super-webhook-secret"
    payload = b'{"ref":"refs/heads/main"}'
    sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    assert verify_github_signature(payload, sig, secret) is True
    assert verify_github_signature(payload, "sha256=deadbeef", secret) is False
    assert verify_github_signature(payload, None, secret) is False
    assert verify_github_signature(payload, sig, "wrong-secret") is False


def test_attach_repository_rejects_foreign_org_repo() -> None:
    """Attaching a repo that does not belong to the caller's org raises NotFoundError."""
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()
    foreign_repo_id = uuid.uuid4()
    tenant = TenantContext(user_id=uuid.uuid4(), organization_id=org_id, role="owner")
    mock_db = AsyncMock()

    async def _run() -> None:
        from unittest.mock import patch

        with patch("app.api.v1.projects.ProjectRepository") as mock_dao_cls:
            dao = mock_dao_cls.return_value
            dao.get_by_id_in_org = AsyncMock(return_value=MagicMock(id=project_id))
            dao.attach_repository = AsyncMock(return_value=None)
            with pytest.raises(NotFoundError):
                await attach_repository_to_project(
                    project_id=project_id,
                    repo_id=foreign_repo_id,
                    tenant=tenant,
                    db=mock_db,
                )

    _run_coro(_run())
