"""
Unit tests for Phase 8 Team Collaboration, RBAC, and Audit Logs.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.router import api_router
from app.api.v1.organizations import (
    list_organization_audit_logs,
    update_organization_member_role,
)
from app.core.exceptions import ForbiddenError
from app.schemas.organization import UpdateMemberRoleRequest


def _run_coro(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_collaboration_routes_registered() -> None:
    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/api/v1/organizations/{org_id}/members/{member_user_id}" in paths
    assert "/api/v1/organizations/{org_id}/audit-logs" in paths


def test_developer_cannot_update_roles_or_view_audit_logs() -> None:
    org_id = uuid.uuid4()
    dev_id = uuid.uuid4()
    target_id = uuid.uuid4()
    mock_db = AsyncMock()
    dev_member = SimpleNamespace(role="developer")

    async def _run() -> None:
        with patch("app.api.v1.organizations.OrganizationRepository") as mock_dao_cls:
            mock_dao_cls.return_value.get_member = AsyncMock(return_value=dev_member)
            with pytest.raises(ForbiddenError):
                await update_organization_member_role(
                    org_id=org_id,
                    member_user_id=target_id,
                    request=UpdateMemberRoleRequest(role="admin"),
                    current_user_id=dev_id,
                    db=mock_db,
                )
            with pytest.raises(ForbiddenError):
                await list_organization_audit_logs(
                    org_id=org_id,
                    limit=50,
                    current_user_id=dev_id,
                    db=mock_db,
                )

    _run_coro(_run())


def test_cannot_demote_organization_owner() -> None:
    org_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    mock_db = AsyncMock()
    admin_member = SimpleNamespace(role="admin")
    owner_member = SimpleNamespace(role="owner")

    async def _run() -> None:
        with patch("app.api.v1.organizations.OrganizationRepository") as mock_dao_cls:
            mock_dao_cls.return_value.get_member = AsyncMock(
                side_effect=[admin_member, owner_member]
            )
            with pytest.raises(ForbiddenError, match="organization owner"):
                await update_organization_member_role(
                    org_id=org_id,
                    member_user_id=owner_id,
                    request=UpdateMemberRoleRequest(role="viewer"),
                    current_user_id=admin_id,
                    db=mock_db,
                )

    _run_coro(_run())
