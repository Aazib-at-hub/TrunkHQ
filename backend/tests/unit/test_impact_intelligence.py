"""
Unit tests for Level 2 Graph Reasoning & Cortex Impact Intelligence.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.router import api_router
from app.graph.reasoning import GraphReasoningService, is_impact_or_dependency_query


def _run_coro(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_impact_report_route_registered() -> None:
    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/api/v1/repositories/{repo_id}/graph/impact-report" in paths


def test_is_impact_or_dependency_query() -> None:
    assert is_impact_or_dependency_query("What components are affected if I change AuthService?") is True
    assert is_impact_or_dependency_query("What is the blast radius of users table?") is True
    assert is_impact_or_dependency_query("Explain how chunk_text splits lines") is False


def test_build_impact_report_collects_components_docs_and_risks() -> None:
    repo_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    project_id = uuid.uuid4()
    org_id = uuid.uuid4()
    root_id = uuid.uuid4()
    ep_id = uuid.uuid4()

    root_node = SimpleNamespace(
        id=root_id,
        node_type="service",
        stable_key="repo:1:service:auth",
        name="AuthService",
        qualified_name="app.services.auth.AuthService",
        description="Core auth service",
        properties={},
        source_kind="code",
        source_uri="app/services/auth.py",
    )
    ep_node = SimpleNamespace(
        id=ep_id,
        node_type="api_endpoint",
        stable_key="repo:1:endpoint:POST:/login",
        name="POST /api/v1/auth/login",
        qualified_name="POST /api/v1/auth/login",
        description="Login endpoint",
        properties={},
        source_kind="architecture",
        source_uri="app/api/v1/auth.py",
    )
    edge = SimpleNamespace(
        id=uuid.uuid4(),
        source_node_id=ep_id,
        target_node_id=root_id,
        edge_type="CALLS",
        confidence=1.0,
        evidence_kind="static",
    )

    mock_db = MagicMock()

    async def _run() -> None:
        svc = GraphReasoningService(mock_db)
        svc._graph_dao.get_impact = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "root": root_node,
                "impacted_nodes": [ep_node],
                "edges": [edge],
                "depth_levels": {str(root_id): 0, str(ep_id): 1},
            }
        )
        with patch("app.graph.reasoning.DocumentRepository") as mock_doc_cls:
            doc_dao = mock_doc_cls.return_value
            doc_dao.list_by_project = AsyncMock(
                return_value=[SimpleNamespace(id=uuid.uuid4(), title="Auth Spec", file_name="auth.md")]
            )
            doc_dao.list_chunks = AsyncMock(
                return_value=[SimpleNamespace(content="AuthService handles JWT tokens.")]
            )

            report = await svc.build_impact_report(
                workspace_id=ws_id,
                repository_id=repo_id,
                node_id=root_id,
                max_depth=3,
                change_description="Rotate token signing algorithm",
                project_id=project_id,
                organization_id=org_id,
            )

            assert report.total_impacted == 1
            assert report.affected_components[0].node.name == "POST /api/v1/auth/login"
            assert report.related_documents == ["Auth Spec (auth.md)"]
            assert any("API contract impact" in r for r in report.potential_risks)
            assert "Static AST" in report.uncertainty_note

    _run_coro(_run())
