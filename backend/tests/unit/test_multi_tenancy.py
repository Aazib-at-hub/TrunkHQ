"""
Unit tests for Phase 3 multi-tenancy, organization isolation, and onboarding.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.deps import get_tenant_context
from app.core.exceptions import ForbiddenError, NotFoundError
from app.repositories.repository_repo import RepositoryRepository
from app.services.auth_service import AuthService
from app.services.repository_service import RepositoryService


def _run_coro(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_get_tenant_context_rejects_non_member() -> None:
    """Passing X-Organization-Id for an org the user does not belong to raises ForbiddenError."""
    user_id = uuid.uuid4()
    foreign_org_id = uuid.uuid4()
    mock_db = AsyncMock()

    async def _run() -> None:
        with patch("app.api.deps.OrganizationRepository") as mock_org_cls:
            mock_org_cls.return_value.get_member = AsyncMock(return_value=None)
            with pytest.raises(ForbiddenError):
                await get_tenant_context(
                    current_user_id=user_id,
                    x_organization_id=str(foreign_org_id),
                    db=mock_db,
                )

    _run_coro(_run())


def test_repository_service_enforces_org_isolation() -> None:
    """RepositoryService.get_repository scoped by organization_id rejects foreign org repos."""
    org_a = uuid.uuid4()
    repo_in_org_b = uuid.uuid4()
    session = MagicMock()
    session_factory = MagicMock()

    service = RepositoryService(session, session_factory)
    service._repo_dao = MagicMock(spec=RepositoryRepository)
    service._repo_dao.get_by_id_in_org = AsyncMock(return_value=None)

    async def _run() -> None:
        with pytest.raises(NotFoundError):
            await service.get_repository(repo_in_org_b, organization_id=org_a)
        service._repo_dao.get_by_id_in_org.assert_awaited_once_with(repo_in_org_b, org_a)

    _run_coro(_run())


def test_register_auto_provisions_personal_organization() -> None:
    """Registering a user automatically creates their personal Organization + owner membership."""
    from app.schemas.auth import RegisterRequest

    mock_db = MagicMock()
    mock_db.commit = AsyncMock()
    created_user = SimpleNamespace(
        id=uuid.uuid4(),
        email="founder@startup.io",
        username="founder",
        account_type="individual",
        onboarding_completed=False,
        created_at="2026-11-17T00:00:00Z",
    )

    async def _run() -> None:
        svc = AuthService(mock_db)
        svc.user_repo = MagicMock()
        svc.user_repo.get_by_email = AsyncMock(return_value=None)
        svc.user_repo.get_by_username = AsyncMock(return_value=None)
        svc.user_repo.create = AsyncMock(return_value=created_user)

        with patch("app.services.auth_service.OrganizationRepository") as mock_org_cls:
            mock_org_cls.return_value.create_with_owner = AsyncMock()
            resp = await svc.register(
                RegisterRequest(
                    email="founder@startup.io",
                    username="founder",
                    password="StrongPassword123!",
                )
            )
            assert resp.username == "founder"
            mock_org_cls.return_value.create_with_owner.assert_awaited_once()

    _run_coro(_run())
