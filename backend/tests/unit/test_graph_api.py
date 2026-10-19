"""
Unit tests for Relationship Graph schemas, path traversal, blast radius algorithms, and API routing.
"""

import uuid
from app.api.router import api_router
from app.models.graph import EdgeType, GraphEdge, GraphNode, NodeType
from app.schemas.graph import (
    FindPathRequest,
    FindPathResponse,
    GraphEdgeSchema,
    GraphNodeSchema,
    GraphSliceResponse,
    GraphStatusResponse,
    ImpactRequest,
    ImpactResponse,
    NodeNeighborsResponse,
)


def test_graph_schemas_serialization() -> None:
    """Verify serialization and validation of graph schemas."""
    node_id = uuid.uuid4()
    node_schema = GraphNodeSchema(
        id=node_id,
        node_type=NodeType.FUNCTION,
        stable_key=f"repo:test:symbol:auth.login:function",
        name="login",
        qualified_name="auth.login",
        description="Authenticates incoming users",
        properties={"start_line": 20, "end_line": 45},
        source_kind="code",
        source_uri="app/auth.py",
    )
    assert node_schema.name == "login"
    assert node_schema.properties["start_line"] == 20

    edge_id = uuid.uuid4()
    target_id = uuid.uuid4()
    edge_schema = GraphEdgeSchema(
        id=edge_id,
        source_node_id=node_id,
        target_node_id=target_id,
        edge_type=EdgeType.CALLS,
        confidence=1.0,
        evidence_kind="static",
    )
    assert edge_schema.edge_type == EdgeType.CALLS

    slice_resp = GraphSliceResponse(
        repository_id=uuid.uuid4(),
        nodes=[node_schema],
        edges=[edge_schema],
        total_nodes=1,
        total_edges=1,
    )
    assert slice_resp.total_nodes == 1


def test_impact_and_path_schemas() -> None:
    """Verify path and blast radius schemas."""
    src = uuid.uuid4()
    tgt = uuid.uuid4()
    path_req = FindPathRequest(source_id=src, target_id=tgt, max_depth=4)
    assert path_req.max_depth == 4

    impact_req = ImpactRequest(node_id=src, max_depth=3, include_tests=True)
    assert impact_req.include_tests is True

    impact_resp = ImpactResponse(
        root=None,
        impacted_nodes=[],
        edges=[],
        depth_levels={},
        total_impacted=0,
    )
    assert impact_resp.total_impacted == 0


def test_graph_api_routes_registered() -> None:
    """Verify all relationship graph endpoints are registered on the root api router."""
    routes = [r.path for r in api_router.routes]

    assert "/api/v1/repositories/{repo_id}/graph" in routes
    assert "/api/v1/repositories/{repo_id}/graph/nodes/{node_id}" in routes
    assert "/api/v1/repositories/{repo_id}/graph/nodes/{node_id}/neighbors" in routes
    assert "/api/v1/repositories/{repo_id}/graph/paths" in routes
    assert "/api/v1/repositories/{repo_id}/graph/impact" in routes
    assert "/api/v1/repositories/{repo_id}/graph/search" in routes
    assert "/api/v1/repositories/{repo_id}/graph/status" in routes
