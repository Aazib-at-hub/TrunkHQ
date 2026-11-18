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
    assert NodeType.METHOD in node_types
    assert EdgeType.CONTAINS in edge_types
    method_node = next(n for n in res.nodes if n.node_type == NodeType.METHOD)
    assert method_node.name == "computeLayout"


def test_python_cross_file_alias_resolution_and_commit_sha() -> None:
    """Verify Python import aliases resolve cross-file CALLS/IMPORTS and commit_sha propagates."""
    from app.graph.stable_key import make_file_key, make_symbol_key

    repo_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    engine = GraphExtractorEngine()

    files: list[tuple[str, str, Optional[str]]] = [
        ("pkg/utils.py", "def helper(x: int) -> int:\n    return x + 1\n", "h1"),
        (
            "pkg/service.py",
            "from .utils import helper as h\n\ndef run() -> int:\n    return h(1)\n",
            "h2",
        ),
    ]

    nodes, edges, _ = engine.extract_repository_graph(
        repository_id=repo_id,
        workspace_id=workspace_id,
        files=files,
        commit_sha="deadbeef1234",
    )

    assert all(n["source_commit"] == "deadbeef1234" for n in nodes)
    assert all(e["source_commit"] == "deadbeef1234" for e in edges)

    service_file_key = make_file_key(repo_id, "pkg/service.py")
    utils_file_key = make_file_key(repo_id, "pkg/utils.py")
    run_key = make_symbol_key(repo_id, "pkg/service.py", "run", "function")
    helper_key = make_symbol_key(repo_id, "pkg/utils.py", "helper", "function")

    assert any(
        e["edge_type"] == EdgeType.IMPORTS
        and e["source_key"] == service_file_key
        and e["target_key"] == utils_file_key
        for e in edges
    )
    assert any(
        e["edge_type"] == EdgeType.CALLS
        and e["source_key"] == run_key
        and e["target_key"] == helper_key
        for e in edges
    )


def test_typescript_relative_import_and_cross_file_call() -> None:
    """Verify TS relative imports resolve to .ts/.tsx files and cross-file calls link."""
    from app.graph.stable_key import make_file_key, make_symbol_key

    repo_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    engine = GraphExtractorEngine()

    files: list[tuple[str, str, Optional[str]]] = [
        ("frontend/lib/math.ts", "export function add(a: number, b: number) { return a + b; }", "m1"),
        (
            "frontend/components/Calc.tsx",
            "import { add as sum } from '../lib/math';\nexport function Calc() { return sum(1, 2); }",
            "c1",
        ),
    ]

    _, edges, _ = engine.extract_repository_graph(
        repository_id=repo_id,
        workspace_id=workspace_id,
        files=files,
    )

    calc_file_key = make_file_key(repo_id, "frontend/components/Calc.tsx")
    math_file_key = make_file_key(repo_id, "frontend/lib/math.ts")
    add_key = make_symbol_key(repo_id, "frontend/lib/math.ts", "add", "function")

    assert any(
        e["edge_type"] == EdgeType.IMPORTS
        and e["source_key"] == calc_file_key
        and e["target_key"] == math_file_key
        for e in edges
    )
    assert any(
        e["edge_type"] == EdgeType.CALLS
        and e["source_key"] == calc_file_key
        and e["target_key"] == add_key
        for e in edges
    )


def test_manifest_nextjs_and_sqlalchemy_extraction() -> None:
    """Verify Next.js route handlers and SQLAlchemy table/READS_FROM/WRITES_TO edges."""
    repo_id = uuid.uuid4()
    extractor = ManifestGraphExtractor()

    next_res = extractor.extract(
        repository_id=repo_id,
        relative_path="frontend/app/api/projects/[id]/route.ts",
        content="export async function GET() {}\nexport const POST = async () => {};",
    )
    ep_names = {n.name for n in next_res.nodes if n.node_type == NodeType.API_ENDPOINT}
    assert "GET /api/projects/[id]" in ep_names
    assert "POST /api/projects/[id]" in ep_names
    assert any(e.edge_type == EdgeType.EXPOSES for e in next_res.edges)

    sa_res = extractor.extract(
        repository_id=repo_id,
        relative_path="backend/app/repositories/repo.py",
        content=(
            'class Repo(Base):\n    __tablename__ = "repositories"\n\n'
            "def get_one(s):\n    return s.execute(select(Repo))\n\n"
            "def save_one(s):\n    s.execute(insert(Repo))\n"
        ),
    )
    assert any(n.node_type == NodeType.TABLE and n.name == "repositories" for n in sa_res.nodes)
    assert any(e.edge_type == EdgeType.READS_FROM for e in sa_res.edges)
    assert any(e.edge_type == EdgeType.WRITES_TO for e in sa_res.edges)

