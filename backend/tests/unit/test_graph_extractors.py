"""
Unit tests for Python AST and manifest graph extractors.
"""

from typing import Optional
import uuid
from app.graph.engine import GraphExtractorEngine
from app.graph.extractors.manifest import ManifestGraphExtractor
from app.graph.extractors.python import PythonGraphExtractor
from app.models.graph import EdgeType, NodeType


SAMPLE_PYTHON_CODE = '''
"""Authentication module."""
from app.database import db

class BaseAuth:
    pass

class UserAuth(BaseAuth):
    def authenticate(self, username: str, password: str) -> bool:
        return self._verify(password)

    def _verify(self, password: str) -> bool:
        return True

def login_user(username: str, password: str) -> bool:
    auth = UserAuth()
    return auth.authenticate(username, password)

def test_login() -> None:
    assert login_user("admin", "secret") is True
'''

SAMPLE_MARKDOWN = '''
# Cortex Architecture
Documentation detailing the authentication flow.
Reference [service.py](app/auth/service.py).
'''


def test_python_ast_extractor() -> None:
    """Verify class, function, method, inheritance, calls, and tests extracted."""
    repo_id = uuid.uuid4()
    extractor = PythonGraphExtractor()
    res = extractor.extract(
        repository_id=repo_id,
        relative_path="app/auth/service.py",
        content=SAMPLE_PYTHON_CODE,
        content_hash="hash123",
    )

    node_types = {n.node_type for n in res.nodes}
    assert NodeType.FILE in node_types
    assert NodeType.CLASS in node_types
    assert NodeType.METHOD in node_types
    assert NodeType.FUNCTION in node_types
    assert NodeType.TEST in node_types

    edge_types = {e.edge_type for e in res.edges}
    assert EdgeType.DEFINES in edge_types
    assert EdgeType.INHERITS in edge_types
    assert EdgeType.CALLS in edge_types
    assert EdgeType.TESTS in edge_types


def test_manifest_extractor_markdown() -> None:
    """Verify document node and documentation link edges extracted."""
    repo_id = uuid.uuid4()
    extractor = ManifestGraphExtractor()
    res = extractor.extract(
        repository_id=repo_id,
        relative_path="docs/ARCHITECTURE.md",
        content=SAMPLE_MARKDOWN,
    )

    doc_node = next(n for n in res.nodes if n.node_type == NodeType.DOCUMENT)
    assert doc_node.name == "Cortex Architecture"
    assert any(e.edge_type == EdgeType.DOCUMENTS for e in res.edges)


def test_graph_extractor_engine() -> None:
    """Verify multi-file aggregation and edge resolution."""
    repo_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    engine = GraphExtractorEngine()

    files: list[tuple[str, str, Optional[str]]] = [
        ("app/auth/service.py", SAMPLE_PYTHON_CODE, "hash1"),
        ("docs/ARCHITECTURE.md", SAMPLE_MARKDOWN, "hash2"),
    ]

    nodes, edges, active_keys = engine.extract_repository_graph(
        repository_id=repo_id,
        workspace_id=workspace_id,
        files=files,
    )

    assert len(nodes) >= 6
    assert len(edges) >= 4
    assert len(active_keys) == len(nodes)


SAMPLE_TSX_CODE = '''
/**
 * Cortex Graph Module.
 */
import React, { useState } from 'react';
import { graphApi } from '../lib/api/graph';
import type { GraphNode } from '../types/graph';

export interface GraphProps {
    repositoryId: string;
}

/**
 * Cortex Graph Visualizer Component.
 */
export function RelationshipGraph({ repositoryId }: GraphProps) {
    const [selected, setSelected] = useState<GraphNode | null>(null);
    return <div>Graph</div>;
}

export class GraphLayoutManager {
    computeLayout(nodes: any[]) {
        return nodes;
    }
}
'''


def test_typescript_ast_extractor() -> None:
    """Verify TypeScript components, interfaces, classes, and imports extracted."""
    from app.graph.extractors.typescript import TypeScriptGraphExtractor

    repo_id = uuid.uuid4()
    extractor = TypeScriptGraphExtractor()
    res = extractor.extract(
        repository_id=repo_id,
        relative_path="frontend/components/graph/RelationshipGraph.tsx",
        content=SAMPLE_TSX_CODE,
        content_hash="hash_tsx",
    )

    node_types = {n.node_type for n in res.nodes}
    assert NodeType.FILE in node_types
    assert NodeType.FUNCTION in node_types
    assert NodeType.CLASS in node_types
    assert NodeType.SYMBOL in node_types

    # Find RelationshipGraph function node
    comp_node = next(n for n in res.nodes if n.name == "RelationshipGraph")
    assert comp_node.properties.get("is_component") is True
    assert "Cortex Graph Visualizer Component" in (comp_node.description or "")

    edge_types = {e.edge_type for e in res.edges}
    assert EdgeType.IMPORTS in edge_types
    assert EdgeType.DEFINES in edge_types

