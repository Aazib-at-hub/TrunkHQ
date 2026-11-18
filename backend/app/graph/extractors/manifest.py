"""
TrunkHQ — Manifest & Architecture Graph Extractor.

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
    make_table_key,
    normalize_path,
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

            # ── 3b. SQLAlchemy / DB Model & READS_FROM / WRITES_TO ───────────
            tablename_matches = re.finditer(
                r"__tablename__\s*=\s*[\"']([a-zA-Z0-9_.-]+)[\"']",
                content,
            )
            for m in tablename_matches:
                table_name = m.group(1)
                table_key = make_table_key(repository_id, table_name)
                result.nodes.append(
                    ExtractedNode(
                        node_type=NodeType.TABLE,
                        stable_key=table_key,
                        name=table_name,
                        qualified_name=f"table:{table_name}",
                        description=f"Database table '{table_name}' defined in {relative_path}",
                        properties={"table": table_name, "source_file": relative_path},
                        source_kind="architecture",
                        source_uri=relative_path,
                        content_hash=content_hash,
                    )
                )
                result.edges.append(
                    ExtractedEdge(
                        source_key=file_key,
                        target_key=table_key,
                        edge_type=EdgeType.DEFINES,
                        confidence=1.0,
                        evidence_kind="static",
                        source_uri=relative_path,
                    )
                )

            # Detect READS_FROM: select(Model), session.query(Model), .get(Model, ...)
            read_models: set[str] = set()
            for m in re.finditer(r"\b(?:select|query)\(\s*([A-Z][A-Za-z0-9_]*)(?:\.[A-Za-z0-9_]+)?", content):
                read_models.add(m.group(1))
            for m in re.finditer(r"\.get\(\s*([A-Z][A-Za-z0-9_]*)\s*,", content):
                read_models.add(m.group(1))
            for model_name in read_models:
                table_key = make_table_key(repository_id, model_name)
                result.edges.append(
                    ExtractedEdge(
                        source_key=file_key,
                        target_key=table_key,
                        edge_type=EdgeType.READS_FROM,
                        properties={"model": model_name},
                        confidence=0.8,
                        evidence_kind="static",
                        source_uri=relative_path,
                    )
                )

            # Detect WRITES_TO: insert(Model), pg_insert(Model), update(Model), delete(Model), .add(Model(...))
            write_models: set[str] = set()
            for m in re.finditer(r"\b(?:pg_insert|insert|update|delete)\(\s*([A-Z][A-Za-z0-9_]*)\s*[\),]", content):
                write_models.add(m.group(1))
            for m in re.finditer(r"\.add\(\s*([A-Z][A-Za-z0-9_]*)\s*\(", content):
                write_models.add(m.group(1))
            for model_name in write_models:
                table_key = make_table_key(repository_id, model_name)
                result.edges.append(
                    ExtractedEdge(
                        source_key=file_key,
                        target_key=table_key,
                        edge_type=EdgeType.WRITES_TO,
                        properties={"model": model_name},
                        confidence=0.8,
                        evidence_kind="static",
                        source_uri=relative_path,
                    )
                )

        # ── 4. Next.js App Router & Pages API Route Handlers ─────────────────
        elif path_lower.endswith((".ts", ".tsx", ".js", ".jsx")):
            norm = normalize_path(relative_path)
            is_app_route = bool(re.search(r"(?:^|/)app/(.*/)?route\.(?:ts|tsx|js|jsx)$", norm))
            is_pages_api = bool(re.search(r"(?:^|/)pages/api/(.+)\.(?:ts|tsx|js|jsx)$", norm))

            if is_app_route:
                route_seg = re.sub(r"^.*?/app/", "/", f"/{norm}")
                route_path = re.sub(r"/route\.(?:ts|tsx|js|jsx)$", "", route_seg) or "/"
                # Strip Next.js route groups like /(auth)/
                route_path = re.sub(r"/\([^)]+\)", "", route_path) or "/"
                methods = set(
                    m.group(1).upper()
                    for m in re.finditer(
                        r"export\s+(?:async\s+)?(?:function|const)\s+(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\b",
                        content,
                    )
                )
                for http_method in sorted(methods):
                    ep_key = make_endpoint_key(repository_id, http_method, route_path)
                    ep_name = f"{http_method} {route_path}"
                    result.nodes.append(
                        ExtractedNode(
                            node_type=NodeType.API_ENDPOINT,
                            stable_key=ep_key,
                            name=ep_name,
                            qualified_name=ep_name,
                            description=f"Next.js App Router handler in {relative_path}",
                            properties={
                                "method": http_method,
                                "path": route_path,
                                "framework": "nextjs",
                                "source_file": relative_path,
                            },
                            source_kind="architecture",
                            source_uri=relative_path,
                            content_hash=content_hash,
                        )
                    )
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
            elif is_pages_api:
                m_api = re.search(r"(?:^|/)pages(/api/.+?)\.(?:ts|tsx|js|jsx)$", norm)
                if m_api:
                    route_path = re.sub(r"/index$", "", m_api.group(1))
                    ep_key = make_endpoint_key(repository_id, "ALL", route_path)
                    ep_name = f"ALL {route_path}"
                    result.nodes.append(
                        ExtractedNode(
                            node_type=NodeType.API_ENDPOINT,
                            stable_key=ep_key,
                            name=ep_name,
                            qualified_name=ep_name,
                            description=f"Next.js Pages API route in {relative_path}",
                            properties={
                                "method": "ALL",
                                "path": route_path,
                                "framework": "nextjs",
                                "source_file": relative_path,
                            },
                            source_kind="architecture",
                            source_uri=relative_path,
                            content_hash=content_hash,
                        )
                    )
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

        # ── 5. Architecture Decision Records (ADR) & Mermaid Diagrams ────────
        if path_lower.endswith(".md"):
            is_adr = (
                "/adr/" in path_lower
                or "/decisions/" in path_lower
                or bool(re.search(r"^#\s*ADR[-\s\d]|^##\s+Decision\b", content, re.MULTILINE))
            )
            if is_adr:
                title_m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                dec_title = title_m.group(1).strip() if title_m else filename
                dec_key = f"repo:{repository_id}:decision:{normalize_path(relative_path)}"
                result.nodes.append(
                    ExtractedNode(
                        node_type=NodeType.DECISION,
                        stable_key=dec_key,
                        name=dec_title,
                        qualified_name=relative_path,
                        description=content[:240].strip(),
                        properties={"path": relative_path, "kind": "adr"},
                        source_kind="knowledge",
                        source_uri=relative_path,
                        content_hash=content_hash,
                    )
                )
                result.edges.append(
                    ExtractedEdge(
                        source_key=file_key,
                        target_key=dec_key,
                        edge_type=EdgeType.DOCUMENTS,
                        confidence=0.95,
                        evidence_kind="documentation",
                        source_uri=relative_path,
                    )
                )

        if path_lower.endswith((".mmd", ".mermaid")) or "```mermaid" in content.lower():
            blocks = (
                [content]
                if path_lower.endswith((".mmd", ".mermaid"))
                else re.findall(r"```mermaid\s*\n(.*?)```", content, re.DOTALL | re.IGNORECASE)
            )
            seen_services: set[str] = set()
            edge_re = re.compile(
                r"\b([A-Za-z0-9_.-]+)(?:\[[^\]]*\]|\([^\)]*\))?\s*(?:-->|-\.->|==>)(?:\|[^|]*\|)?\s*([A-Za-z0-9_.-]+)"
            )
            for block in blocks:
                for src_id, tgt_id in edge_re.findall(block):
                    if src_id == tgt_id:
                        continue
                    for svc in (src_id, tgt_id):
                        svc_key = make_service_key(repository_id, svc.lower())
                        if svc_key not in seen_services:
                            seen_services.add(svc_key)
                            result.nodes.append(
                                ExtractedNode(
                                    node_type=NodeType.SERVICE,
                                    stable_key=svc_key,
                                    name=svc,
                                    qualified_name=f"diagram:{svc}",
                                    description=f"Architecture component from Mermaid diagram in {relative_path}",
                                    properties={"source": "mermaid"},
                                    source_kind="architecture",
                                    source_uri=relative_path,
                                    content_hash=content_hash,
                                )
                            )
                    result.edges.append(
                        ExtractedEdge(
                            source_key=make_service_key(repository_id, src_id.lower()),
                            target_key=make_service_key(repository_id, tgt_id.lower()),
                            edge_type=EdgeType.DEPENDS_ON,
                            confidence=0.85,
                            evidence_kind="diagram_mermaid",
                            source_uri=relative_path,
                        )
                    )

        # ── 6. SQL DDL Schemas (.sql) ────────────────────────────────────────
        if path_lower.endswith(".sql"):
            table_matches = re.findall(
                r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[a-zA-Z0-9_]+\.)?([a-zA-Z0-9_]+)",
                content,
                re.IGNORECASE,
            )
            defined_tables: set[str] = set()
            for tbl in table_matches:
                tbl_lower = tbl.lower()
                defined_tables.add(tbl_lower)
                tbl_key = make_table_key(repository_id, tbl_lower)
                result.nodes.append(
                    ExtractedNode(
                        node_type=NodeType.TABLE,
                        stable_key=tbl_key,
                        name=tbl_lower,
                        qualified_name=f"sql:{tbl_lower}",
                        description=f"Database table defined in {relative_path}",
                        properties={"source_file": relative_path},
                        source_kind="architecture",
                        source_uri=relative_path,
                        content_hash=content_hash,
                    )
                )
                result.edges.append(
                    ExtractedEdge(
                        source_key=file_key,
                        target_key=tbl_key,
                        edge_type=EdgeType.DEFINES,
                        confidence=1.0,
                        evidence_kind="static",
                        source_uri=relative_path,
                    )
                )
            ref_matches = re.findall(
                r"REFERENCES\s+(?:[a-zA-Z0-9_]+\.)?([a-zA-Z0-9_]+)",
                content,
                re.IGNORECASE,
            )
            for src_tbl in defined_tables:
                for ref_tbl in ref_matches:
                    ref_lower = ref_tbl.lower()
                    if ref_lower != src_tbl:
                        result.edges.append(
                            ExtractedEdge(
                                source_key=make_table_key(repository_id, src_tbl),
                                target_key=make_table_key(repository_id, ref_lower),
                                edge_type=EdgeType.DEPENDS_ON,
                                confidence=0.9,
                                evidence_kind="static",
                                source_uri=relative_path,
                            )
                        )

        # ── 7. OpenAPI / Swagger Specs (.yaml, .yml, .json) ─────────────────
        if path_lower.endswith((".yaml", ".yml", ".json")) and (
            "openapi" in content.lower() or "swagger" in content.lower()
        ):
            spec = None
            try:
                if path_lower.endswith(".json"):
                    import json

                    spec = json.loads(content)
                else:
                    import yaml

                    spec = yaml.safe_load(content)
            except Exception:
                spec = None

            if isinstance(spec, dict) and isinstance(spec.get("paths"), dict):
                http_methods = {"get", "post", "put", "patch", "delete", "options", "head"}
                for route_path, methods_obj in spec["paths"].items():
                    if not isinstance(methods_obj, dict):
                        continue
                    for method_name in methods_obj.keys():
                        if str(method_name).lower() not in http_methods:
                            continue
                        m_upper = str(method_name).upper()
                        ep_key = make_endpoint_key(repository_id, m_upper, str(route_path))
                        ep_name = f"{m_upper} {route_path}"
                        result.nodes.append(
                            ExtractedNode(
                                node_type=NodeType.API_ENDPOINT,
                                stable_key=ep_key,
                                name=ep_name,
                                qualified_name=ep_name,
                                description=f"OpenAPI endpoint in {relative_path}",
                                properties={"method": m_upper, "path": str(route_path), "framework": "openapi"},
                                source_kind="architecture",
                                source_uri=relative_path,
                                content_hash=content_hash,
                            )
                        )
                        result.edges.append(
                            ExtractedEdge(
                                source_key=file_key,
                                target_key=ep_key,
                                edge_type=EdgeType.EXPOSES,
                                confidence=1.0,
                                evidence_kind="documentation",
                                source_uri=relative_path,
                            )
                        )

        return result
