"""
Cortex Engineering — Manifest & Architecture Graph Extractor.

Extracts architecture components (services, containers, API endpoints)
and knowledge components (documents, requirements, decisions) from configuration
and markdown files.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from uuid import UUID

from app.graph.stable_key import (
    make_document_key,
    make_endpoint_key,
    make_file_key,
    make_service_key,
)
from app.graph.types import ExtractedEdge, ExtractedNode, ExtractionResult
from app.models.graph import EdgeType, NodeType


class ManifestGraphExtractor:
    """Extracts architecture entities and documentation links from project files."""

    def extract(
        self,
        repository_id: UUID,
        relative_path: str,
        content: str,
        content_hash: Optional[str] = None,
    ) -> ExtractionResult:
        """Extract architecture or documentation entities based on file kind."""
        result = ExtractionResult()
        path_lower = relative_path.lower()
        file_key = make_file_key(repository_id, relative_path)
        filename = Path(relative_path).name

        # ── 1. Markdown Documents ────────────────────────────────────────────
        if path_lower.endswith(".md"):
            doc_key = make_document_key(repository_id, relative_path)
            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else filename

            result.nodes.append(
                ExtractedNode(
                    node_type=NodeType.DOCUMENT,
                    stable_key=doc_key,
                    name=title,
                    qualified_name=relative_path,
                    description=content[:200].strip(),
                    properties={"path": relative_path, "type": "markdown"},
                    source_kind="knowledge",
                    source_uri=relative_path,
                    content_hash=content_hash,
                )
            )

            # Link file to document
            result.edges.append(
                ExtractedEdge(
                    source_key=file_key,
                    target_key=doc_key,
                    edge_type=EdgeType.DOCUMENTS,
                    confidence=1.0,
                    evidence_kind="documentation",
                    source_uri=relative_path,
                )
            )

            # Heuristic: find referenced files in markdown links or backticks
            referenced_files = set(re.findall(r"\[.*?\]\(([\w\.\-/]+\.(?:py|ts|tsx|js|json|yml|yaml))\)", content))
            for ref in referenced_files:
                target_key = make_file_key(repository_id, ref)
                result.edges.append(
                    ExtractedEdge(
                        source_key=doc_key,
                        target_key=target_key,
                        edge_type=EdgeType.DOCUMENTS,
                        properties={"reference_kind": "link"},
                        confidence=0.8,
                        evidence_kind="documentation",
                        source_uri=relative_path,
                    )
                )

        # ── 2. Docker / Service Manifests ────────────────────────────────────
        elif "docker-compose" in path_lower or filename.lower().startswith("dockerfile"):
            service_name = filename.replace("Dockerfile.", "").replace("Dockerfile", "").strip(".") or "app"
            service_key = make_service_key(repository_id, service_name)

            result.nodes.append(
                ExtractedNode(
                    node_type=NodeType.SERVICE,
                    stable_key=service_key,
                    name=service_name,
                    qualified_name=f"service:{service_name}",
                    description=f"Containerized service defined in {relative_path}",
                    properties={"config_file": relative_path},
                    source_kind="architecture",
                    source_uri=relative_path,
                    content_hash=content_hash,
                )
            )

            result.edges.append(
                ExtractedEdge(
                    source_key=service_key,
                    target_key=file_key,
                    edge_type=EdgeType.DEPENDS_ON,
                    confidence=1.0,
                    evidence_kind="configuration",
                    source_uri=relative_path,
                )
            )

        # ── 3. FastAPI Route Annotations ─────────────────────────────────────
        if path_lower.endswith(".py"):
            # Scan for @router.get("/...", ...) or @app.post("/...", ...)
            route_matches = re.finditer(
                r"@(?:router|app)\.(get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']",
                content,
                re.IGNORECASE,
            )
            for m in route_matches:
                http_method = m.group(1).upper()
                route_path = m.group(2)
                ep_key = make_endpoint_key(repository_id, http_method, route_path)
                ep_name = f"{http_method} {route_path}"

                result.nodes.append(
                    ExtractedNode(
                        node_type=NodeType.API_ENDPOINT,
                        stable_key=ep_key,
                        name=ep_name,
                        qualified_name=ep_name,
                        description=f"HTTP endpoint declared in {relative_path}",
                        properties={
                            "method": http_method,
                            "path": route_path,
                            "source_file": relative_path,
                        },
                        source_kind="architecture",
                        source_uri=relative_path,
                        content_hash=content_hash,
                    )
                )

                # EXPOSES edge from file to endpoint
                result.edges.append(
                    ExtractedEdge(
                        source_key=file_key,
                        target_key=ep_key,
                        edge_type=EdgeType.EXPOSES,
                        confidence=1.0,
                        evidence_kind="configuration",
                        source_uri=relative_path,
                    )
                )

        return result
