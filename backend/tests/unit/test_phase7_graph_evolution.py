"""
Unit tests for Phase 7 Knowledge Graph Evolution:
- PROJECT / DOCUMENT / BELONGS_TO / DOCUMENTS vocabulary
- Deterministic document-to-code reference linking (no random edges)
- /api/v1/projects/{project_id}/graph route registration & org isolation
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.api.deps import TenantContext
from app.api.router import api_router
from app.api.v1.graph import build_document_reference_links, get_project_graph
from app.core.exceptions import NotFoundError
from app.models.graph import EdgeType, NodeType
from app.schemas.graph import GraphNodeSchema


def _run_coro(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_graph_vocabulary_extensions() -> None:
    assert NodeType.PROJECT == "project"
    assert NodeType.DOCUMENT == "document"
    assert EdgeType.DOCUMENTS == "DOCUMENTS"
    assert EdgeType.BELONGS_TO == "BELONGS_TO"


def test_build_document_reference_links_is_deterministic() -> None:
    project_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    auth_node_id = uuid.uuid4()
    unrelated_node_id = uuid.uuid4()

    code_nodes = [
        GraphNodeSchema(
            id=auth_node_id,
            node_type="function",
            stable_key="repo:1:auth_service",
            name="authenticate_user",
            qualified_name="auth.authenticate_user",
            source_kind="code",
            source_uri="app/services/auth_service.py",
        ),
        GraphNodeSchema(
            id=unrelated_node_id,
            node_type="function",
            stable_key="repo:1:billing",
            name="calculate_invoice",
            qualified_name="billing.calculate_invoice",
            source_kind="code",
            source_uri="app/services/billing.py",
        ),
    ]

    docs_with_text = [
        (doc_id, "Auth Spec", "The login flow calls authenticate_user in auth_service.py.")
    ]
    doc_nodes, doc_edges = build_document_reference_links(docs_with_text, code_nodes, project_id)

    assert len(doc_nodes) == 1
    assert doc_nodes[0].node_type == "document"
    assert len(doc_edges) == 1
    assert doc_edges[0].source_node_id == doc_id
    assert doc_edges[0].target_node_id == auth_node_id
    assert doc_edges[0].evidence_kind == "doc_reference"


def test_project_graph_route_and_org_isolation() -> None:
    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/api/v1/projects/{project_id}/graph" in paths

    tenant = TenantContext(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), role="viewer")
    mock_db = AsyncMock()

    async def _run() -> None:
        with patch("app.repositories.project_repo.ProjectRepository.get_by_id_in_org", new=AsyncMock(return_value=None)):
            with pytest.raises(NotFoundError):
                await get_project_graph(project_id=uuid.uuid4(), tenant=tenant, db=mock_db)

    _run_coro(_run())
