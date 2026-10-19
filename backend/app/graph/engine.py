"""
Cortex Engineering — Graph Extractor Engine.

Orchestrates multi-language parsing, symbol resolution, architecture discovery,
and edge validation into an indexed relationship graph.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence
from uuid import UUID

from app.core.logging import get_logger
from app.graph.extractors.manifest import ManifestGraphExtractor
from app.graph.extractors.python import PythonGraphExtractor
from app.graph.extractors.typescript import TypeScriptGraphExtractor
from app.graph.types import ExtractedEdge, ExtractedNode, ExtractionResult
from app.models.graph import NodeType

logger = get_logger("graph_engine")


class GraphExtractorEngine:
    """Orchestrates extraction of code symbols, architecture, and knowledge entities."""

    def __init__(self) -> None:
        self._python_extractor = PythonGraphExtractor()
        self._typescript_extractor = TypeScriptGraphExtractor()
        self._manifest_extractor = ManifestGraphExtractor()

    def extract_repository_graph(
        self,
        repository_id: UUID,
        workspace_id: UUID,
        files: Sequence[tuple[str, str, Optional[str]]],  # (relative_path, content, content_hash)
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
        """
        Extract unified nodes and edges across all repository files.

        Returns:
            tuple[nodes_to_upsert, edges_to_upsert, active_stable_keys]
        """
        all_nodes: dict[str, ExtractedNode] = {}
        all_edges: list[ExtractedEdge] = []

        logger.info(
            "Starting relationship graph extraction",
            repo_id=str(repository_id),
            file_count=len(files),
        )

        ts_extensions = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

        for relative_path, content, content_hash in files:
            norm_path = relative_path.replace("\\", "/")

            # 1. Architecture & manifest extraction (markdown, docker, routes)
            arch_res = self._manifest_extractor.extract(
                repository_id=repository_id,
                relative_path=norm_path,
                content=content,
                content_hash=content_hash,
            )
            for node in arch_res.nodes:
                all_nodes[node.stable_key] = node
            all_edges.extend(arch_res.edges)

            # 2. Language-specific code parsing
            if norm_path.endswith(".py"):
                code_res = self._python_extractor.extract(
                    repository_id=repository_id,
                    relative_path=norm_path,
                    content=content,
                    content_hash=content_hash,
                )
                for node in code_res.nodes:
                    all_nodes[node.stable_key] = node
                all_edges.extend(code_res.edges)
            elif norm_path.endswith(ts_extensions):
                code_res = self._typescript_extractor.extract(
                    repository_id=repository_id,
                    relative_path=norm_path,
                    content=content,
                    content_hash=content_hash,
                )
                for node in code_res.nodes:
                    all_nodes[node.stable_key] = node
                all_edges.extend(code_res.edges)

        # Ensure all referenced target nodes exist or synthesize a placeholder node
        for edge in all_edges:
            if edge.target_key not in all_nodes:
                # Synthesize placeholder symbol or module
                target_key = edge.target_key
                parts = target_key.split(":")
                name = parts[-2] if len(parts) >= 2 else "external"
                node_type = parts[-1] if len(parts) >= 1 else NodeType.SYMBOL
                if node_type not in NodeType.ALL_CODE:
                    node_type = NodeType.SYMBOL

                all_nodes[target_key] = ExtractedNode(
                    node_type=node_type,
                    stable_key=target_key,
                    name=name,
                    qualified_name=name,
                    description="Inferred or external referenced entity",
                    properties={"is_external": True},
                    source_kind="code",
                )

        # Convert to dictionary payloads for repository upsert
        active_keys = set(all_nodes.keys())
        node_payloads: list[dict[str, Any]] = [
            {
                "node_type": n.node_type,
                "stable_key": n.stable_key,
                "name": n.name,
                "qualified_name": n.qualified_name,
                "description": n.description,
                "properties": n.properties,
                "source_kind": n.source_kind,
                "source_uri": n.source_uri,
                "content_hash": n.content_hash,
                "status": "active",
            }
            for n in all_nodes.values()
        ]

        edge_payloads: list[dict[str, Any]] = []
        for e in all_edges:
            if e.source_key in all_nodes and e.target_key in all_nodes and e.source_key != e.target_key:
                edge_payloads.append({
                    "source_key": e.source_key,
                    "target_key": e.target_key,
                    "edge_type": e.edge_type,
                    "properties": e.properties,
                    "confidence": e.confidence,
                    "evidence_kind": e.evidence_kind,
                    "source_uri": e.source_uri,
                    "content_hash": e.content_hash,
                })

        logger.info(
            "Graph extraction completed",
            repo_id=str(repository_id),
            nodes_count=len(node_payloads),
            edges_count=len(edge_payloads),
        )

        return node_payloads, edge_payloads, active_keys
