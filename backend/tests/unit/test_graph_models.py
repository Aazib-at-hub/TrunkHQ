"""
Unit tests for Cortex Relationship Graph models, enums, and schema definitions.
"""

import uuid
from app.models.graph import (
    EdgeType,
    GraphEdge,
    GraphIndexRun,
    GraphNode,
    NodeType,
)


def test_node_and_edge_vocabularies() -> None:
    """Verify controlled vocabulary sets for graph nodes and relationships."""
    assert NodeType.FUNCTION in NodeType.ALL_CODE
    assert NodeType.CLASS in NodeType.ALL_CODE
    assert NodeType.SERVICE in NodeType.ALL_ARCHITECTURE
    assert NodeType.API_ENDPOINT in NodeType.ALL_ARCHITECTURE
    assert NodeType.DOCUMENT in NodeType.ALL_KNOWLEDGE
    assert NodeType.DECISION in NodeType.ALL_KNOWLEDGE

    assert EdgeType.CALLS == "CALLS"
    assert EdgeType.IMPORTS == "IMPORTS"
    assert EdgeType.DEPENDS_ON == "DEPENDS_ON"
    assert EdgeType.TESTS == "TESTS"


def test_graph_node_instantiation() -> None:
    """Verify GraphNode instantiation and property defaults."""
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    node = GraphNode(
        workspace_id=workspace_id,
        repository_id=repo_id,
        node_type=NodeType.FUNCTION,
        stable_key=f"repo:{repo_id}:symbol:auth.login:function",
        name="login",
        qualified_name="auth.login",
        description="Authenticates incoming credentials",
        properties={"start_line": 10, "end_line": 45},
    )

    assert node.node_type == NodeType.FUNCTION
    assert node.name == "login"
    assert node.status == "active"
    assert node.source_kind == "code"
    assert node.properties["start_line"] == 10
    assert repr(node).startswith("<GraphNode")


def test_graph_edge_instantiation() -> None:
    """Verify GraphEdge instantiation and constraints."""
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    src_id = uuid.uuid4()
    tgt_id = uuid.uuid4()

    edge = GraphEdge(
        workspace_id=workspace_id,
        repository_id=repo_id,
        source_node_id=src_id,
        target_node_id=tgt_id,
        edge_type=EdgeType.CALLS,
        confidence=0.95,
        evidence_kind="static",
    )

    assert edge.edge_type == EdgeType.CALLS
    assert edge.confidence == 0.95
    assert edge.evidence_kind == "static"
    assert repr(edge).startswith("<GraphEdge")


def test_graph_index_run_instantiation() -> None:
    """Verify GraphIndexRun instantiation and counters."""
    workspace_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    run = GraphIndexRun(
        workspace_id=workspace_id,
        repository_id=repo_id,
        commit_sha="abcdef123456",
        status="RUNNING",
    )

    assert run.status == "RUNNING"
    assert run.nodes_created == 0
    assert run.extractor_version == "1.0"
    assert repr(run).startswith("<GraphIndexRun")
