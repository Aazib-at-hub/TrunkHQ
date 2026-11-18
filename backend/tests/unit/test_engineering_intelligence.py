"""
Unit tests for Level 3 Engineering Intelligence:
- Stale-doc detection (missing file refs & doc older than repo index)
- Architecture drift (OpenAPI vs code endpoints)
- Proactive integration risks (failed repos & untested high-fan-in hubs)
- /api/v1/projects/{project_id}/intelligence route registration & org isolation
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.deps import TenantContext
from app.api.router import api_router
from app.api.v1.graph import get_project_engineering_intelligence
from app.core.exceptions import NotFoundError
from app.graph.reasoning import GraphReasoningService


def _run_coro(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_intelligence_route_and_org_isolation() -> None:
    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/api/v1/projects/{project_id}/intelligence" in paths

    tenant = TenantContext(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), role="viewer")
    mock_db = AsyncMock()

    async def _run() -> None:
        with patch("app.repositories.project_repo.ProjectRepository.get_by_id_in_org", new=AsyncMock(return_value=None)):
            with pytest.raises(NotFoundError):
                await get_project_engineering_intelligence(
                    project_id=uuid.uuid4(), tenant=tenant, db=mock_db
                )

    _run_coro(_run())


def test_build_engineering_intelligence_report() -> None:
    project_id = uuid.uuid4()
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    repo = SimpleNamespace(
        id=repo_id,
        name="core-api",
        status="READY",
        last_indexed_at=now,
    )
    doc = SimpleNamespace(
        id=uuid.uuid4(),
        title="Legacy Spec",
        file_name="spec.md",
        updated_at=now - timedelta(days=2),
    )

    spec_ep = SimpleNamespace(
        id=uuid.uuid4(),
        node_type="api_endpoint",
        name="DELETE /api/v1/legacy",
        properties={"framework": "openapi"},
    )
    code_ep = SimpleNamespace(
        id=uuid.uuid4(),
        node_type="api_endpoint",
        name="POST /api/v1/billing/webhook",
        properties={"framework": "fastapi"},
    )
    hub_id = uuid.uuid4()
    hub_node = SimpleNamespace(
        id=hub_id,
        node_type="function",
        name="get_tenant_context",
        properties={},
    )
    edges = [
        SimpleNamespace(target_node_id=hub_id, edge_type="CALLS") for _ in range(5)
    ]

    mock_db = MagicMock()

    async def _run() -> None:
        svc = GraphReasoningService(mock_db)
        svc._graph_dao.get_nodes_by_repositories = AsyncMock(  # type: ignore[method-assign]
            return_value=[spec_ep, code_ep, hub_node]
        )
        svc._graph_dao.get_edges_by_repositories = AsyncMock(  # type: ignore[method-assign]
            return_value=edges
        )
        with patch("app.graph.reasoning.FileRepository") as mock_file_cls, patch(
            "app.graph.reasoning.DocumentRepository"
        ) as mock_doc_cls:
            mock_file_cls.return_value.list_by_repository = AsyncMock(
                return_value=[SimpleNamespace(path="app/api/deps.py")]
            )
            doc_dao = mock_doc_cls.return_value
            doc_dao.list_by_project = AsyncMock(return_value=[doc])
            doc_dao.list_chunks = AsyncMock(
                return_value=[SimpleNamespace(content="See app/old_removed_auth.py for details.")]
            )

            report = await svc.build_engineering_intelligence_report(
                project_id=project_id,
                organization_id=org_id,
                repositories=[repo],
            )
            assert len(report.stale_docs) == 1
            assert "app/old_removed_auth.py" in report.stale_docs[0].missing_references
            drift_kinds = {d.kind for d in report.architecture_drift}
            assert drift_kinds == {"documented_not_implemented", "implemented_not_documented"}
            assert any("high-fan-in" in r.title for r in report.integration_risks)

    _run_coro(_run())
