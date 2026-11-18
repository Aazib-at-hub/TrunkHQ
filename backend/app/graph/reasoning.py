"""
TrunkHQ — Level 2 Graph Reasoning & Impact Intelligence Service.

Separates multi-hop graph traversal, query-aware reasoning, and evidence-backed
impact report generation from API/chat controllers.
"""

from __future__ import annotations

import re
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.repositories.document_repo import DocumentRepository
from app.repositories.file_repo import FileRepository
from app.repositories.graph_repo import GraphRepository
from app.schemas.graph import (
    AffectedComponentItem,
    ArchitectureDriftFinding,
    EngineeringIntelligenceResponse,
    GraphEdgeSchema,
    GraphNodeSchema,
    ImpactReportResponse,
    IntegrationRiskFinding,
    StaleDocFinding,
)

IMPACT_KEYWORDS = (
    "impact",
    "affect",
    "affected",
    "blast radius",
    "break",
    "depend",
    "caller",
    "callers",
    "downstream",
    "upstream",
)


def is_impact_or_dependency_query(question: str) -> bool:
    """Detect whether a user question requires multi-hop impact/dependency reasoning."""
    q_lower = question.lower()
    return any(kw in q_lower for kw in IMPACT_KEYWORDS)


class GraphReasoningService:
    """Dedicated Level 2 graph reasoning and Impact Intelligence engine."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._graph_dao = GraphRepository(db)

    async def build_impact_report(
        self,
        workspace_id: UUID,
        repository_id: UUID,
        node_id: UUID,
        max_depth: int = 3,
        change_description: Optional[str] = None,
        project_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
    ) -> ImpactReportResponse:
        """
        Trace multi-hop dependencies for a target entity and produce an
        evidence-backed impact report with related docs and breaking-change risks.
        """
        impact_data = await self._graph_dao.get_impact(
            workspace_id=workspace_id,
            node_id=node_id,
            max_depth=max_depth,
            include_tests=True,
            repository_id=repository_id,
        )
        root = impact_data["root"]
        if not root:
            raise NotFoundError("Target entity not found in this repository graph")

        root_schema = GraphNodeSchema.model_validate(root)
        edges_schema = [GraphEdgeSchema.model_validate(e) for e in impact_data["edges"]]
        depth_levels: dict[str, int] = impact_data["depth_levels"]

        # Map highest confidence & evidence_kind reaching each impacted node
        edge_evidence: dict[UUID, tuple[str, float]] = {}
        for e in impact_data["edges"]:
            edge_evidence[e.source_node_id] = (
                getattr(e, "evidence_kind", "static") or "static",
                float(getattr(e, "confidence", 1.0) or 1.0),
            )

        affected: list[AffectedComponentItem] = []
        affected_names: list[str] = [root.name]
        for n in impact_data["impacted_nodes"]:
            ev_kind, conf = edge_evidence.get(n.id, ("static", 1.0))
            affected.append(
                AffectedComponentItem(
                    node=GraphNodeSchema.model_validate(n),
                    depth=depth_levels.get(str(n.id), 1),
                    evidence_kind=ev_kind,
                    confidence=conf,
                )
            )
            affected_names.append(n.name)

        affected.sort(key=lambda item: (item.depth, item.node.name))

        # Find related project documents referencing root or impacted entities
        related_docs: list[str] = []
        if project_id and organization_id:
            doc_dao = DocumentRepository(self._db)
            docs = await doc_dao.list_by_project(project_id, organization_id)
            search_terms = {t.lower() for t in affected_names if len(t) >= 4}
            for doc in docs:
                chunks = await doc_dao.list_chunks(doc.id, organization_id)
                combined = "\n".join(c.content for c in chunks).lower()
                if any(term in combined for term in search_terms):
                    related_docs.append(f"{doc.title} ({doc.file_name})")

        # Derive deterministic risk signals from impacted node types
        risks: list[str] = []
        endpoint_hits = [a.node.name for a in affected if a.node.node_type == "api_endpoint"]
        table_hits = [a.node.name for a in affected if a.node.node_type == "table"]
        test_hits = [a.node.name for a in affected if a.node.node_type == "test"]

        if endpoint_hits:
            risks.append(f"API contract impact on {len(endpoint_hits)} endpoint(s): {', '.join(endpoint_hits[:5])}")
        if table_hits:
            risks.append(f"Database schema coupling with {len(table_hits)} table(s): {', '.join(table_hits[:5])}")
        if not test_hits:
            risks.append("No direct TEST edges detected for impacted callers — verify test coverage before merging.")
        else:
            risks.append(f"Re-run {len(test_hits)} linked test entity(s): {', '.join(test_hits[:5])}")

        change_note = f" Proposed change: {change_description.strip()}" if change_description else ""
        summary = (
            f"Modifying '{root.name}' ({root.node_type}) affects {len(affected)} directly or "
            f"transitively connected component(s) within {max_depth} hop(s) and "
            f"{len(related_docs)} project document(s).{change_note}"
        )

        return ImpactReportResponse(
            root=root_schema,
            summary=summary,
            affected_components=affected,
            related_documents=related_docs,
            potential_risks=risks,
            uncertainty_note=(
                "Static AST, manifest, and document-reference analysis does not capture "
                "dynamic runtime reflection, external message queues, or unindexed services."
            ),
            edges=edges_schema,
            total_impacted=len(affected),
        )

    async def build_query_graph_context(
        self,
        workspace_id: UUID,
        repository_id: UUID,
        question: str,
        entities: list[str],
    ) -> Optional[str]:
        """
        Build rich graph context for ChatService: uses multi-hop impact traversal
        for impact/dependency queries and 1-hop neighborhoods for general queries.
        """
        matched_nodes = []
        seen_ids: set[UUID] = set()
        for ent in entities[:4]:
            found = await self._graph_dao.search_nodes(
                workspace_id=workspace_id,
                repository_id=repository_id,
                query=ent,
                limit=2,
            )
            for fn in found:
                if fn.id not in seen_ids:
                    seen_ids.add(fn.id)
                    matched_nodes.append(fn)

        if not matched_nodes:
            return None

        use_impact = is_impact_or_dependency_query(question)
        lines: list[str] = []
        for node in matched_nodes[:3]:
            if use_impact:
                impact = await self._graph_dao.get_impact(
                    workspace_id=workspace_id,
                    node_id=node.id,
                    max_depth=2,
                    include_tests=True,
                    repository_id=repository_id,
                )
                lines.append(
                    f"Impact Root: {node.name} ({node.node_type}) at {node.source_uri or 'unknown'} "
                    f"-> {len(impact['impacted_nodes'])} impacted component(s)"
                )
                for imp in impact["impacted_nodes"][:6]:
                    depth = impact["depth_levels"].get(str(imp.id), 1)
                    lines.append(
                        f"  - [hop {depth}] {imp.name} ({imp.node_type}) at {imp.source_uri or 'unknown'}"
                    )
            else:
                nbrs = await self._graph_dao.get_neighbors(
                    workspace_id=workspace_id,
                    node_id=node.id,
                    limit=10,
                    repository_id=repository_id,
                )
                lines.append(
                    f"Entity: {node.name} ({node.node_type}) at {node.source_uri or 'unknown'}"
                )
                for out_e in nbrs["outgoing_edges"][:5]:
                    tgt_name = next(
                        (n.name for n in nbrs["neighbors"] if n.id == out_e.target_node_id),
                        str(out_e.target_node_id),
                    )
                    lines.append(
                        f"  - [{out_e.edge_type}] -> {tgt_name} (confidence={out_e.confidence})"
                    )
                for in_e in nbrs["incoming_edges"][:5]:
                    src_name = next(
                        (n.name for n in nbrs["neighbors"] if n.id == in_e.source_node_id),
                        str(in_e.source_node_id),
                    )
                    lines.append(
                        f"  - <- [{in_e.edge_type}] from {src_name} (confidence={in_e.confidence})"
                    )

        return "\n".join(lines) if lines else None

    async def build_engineering_intelligence_report(
        self,
        project_id: UUID,
        organization_id: UUID,
        repositories: list,
    ) -> EngineeringIntelligenceResponse:
        """
        Level 3 Engineering Intelligence:
        1. Stale-doc detection (broken file refs & doc older than latest repo index)
        2. Architecture drift (OpenAPI vs implemented endpoints)
        3. Proactive integration risk findings (untested hubs, failed/stale repos)
        """
        repo_ids = [r.id for r in repositories]
        file_dao = FileRepository(self._db)
        doc_dao = DocumentRepository(self._db)

        known_paths: set[str] = set()
        latest_repo_index = None
        integration_risks: list[IntegrationRiskFinding] = []

        for repo in repositories:
            if getattr(repo, "status", None) == "FAILED":
                integration_risks.append(
                    IntegrationRiskFinding(
                        severity="high",
                        title=f"Repository '{repo.name}' index failed",
                        detail="Code and graph intelligence for this repository may be incomplete until re-indexed.",
                    )
                )
            idx_at = getattr(repo, "last_indexed_at", None)
            if idx_at and (latest_repo_index is None or idx_at > latest_repo_index):
                latest_repo_index = idx_at
            repo_files = await file_dao.list_by_repository(repo.id)
            for f in repo_files:
                known_paths.add(f.path.replace("\\", "/").lower())

        # 1. Stale-doc detection
        stale_docs: list[StaleDocFinding] = []
        docs = await doc_dao.list_by_project(project_id, organization_id)
        path_ref_re = re.compile(
            r"\b([a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+\.(?:py|ts|tsx|js|jsx|sql|yaml|yml|json))\b"
        )
        for doc in docs:
            chunks = await doc_dao.list_chunks(doc.id, organization_id)
            combined = "\n".join(c.content for c in chunks)
            referenced = {m.lower() for m in path_ref_re.findall(combined)}
            missing = sorted(
                p for p in referenced if not any(kp.endswith(p) for kp in known_paths)
            )
            doc_updated = getattr(doc, "updated_at", None)
            is_older = bool(latest_repo_index and doc_updated and doc_updated < latest_repo_index)
            if missing or is_older:
                reasons = []
                if missing:
                    reasons.append(f"{len(missing)} referenced file path(s) not found in indexed repositories")
                if is_older:
                    reasons.append("document predates latest repository index")
                stale_docs.append(
                    StaleDocFinding(
                        document_id=doc.id,
                        document_title=doc.title,
                        file_name=doc.file_name,
                        reason="; ".join(reasons),
                        missing_references=missing[:10],
                    )
                )

        # 2. Architecture drift (OpenAPI spec endpoints vs code-implemented endpoints)
        architecture_drift: list[ArchitectureDriftFinding] = []
        nodes = await self._graph_dao.get_nodes_by_repositories(
            repository_ids=repo_ids, limit=1000
        )
        edges = await self._graph_dao.get_edges_by_repositories(
            repository_ids=repo_ids, limit=2000
        )

        spec_endpoints: set[str] = set()
        code_endpoints: set[str] = set()
        in_degree: dict[UUID, int] = {}
        tested_targets: set[UUID] = set()

        for e in edges:
            in_degree[e.target_node_id] = in_degree.get(e.target_node_id, 0) + 1
            if e.edge_type == "TESTS":
                tested_targets.add(e.target_node_id)

        for n in nodes:
            if n.node_type == "api_endpoint":
                props = getattr(n, "properties", None) or {}
                if props.get("framework") == "openapi":
                    spec_endpoints.add(n.name)
                else:
                    code_endpoints.add(n.name)

        if spec_endpoints and code_endpoints:
            for ep in sorted(spec_endpoints - code_endpoints)[:10]:
                architecture_drift.append(
                    ArchitectureDriftFinding(
                        kind="documented_not_implemented",
                        entity=ep,
                        detail="Endpoint appears in OpenAPI spec but was not detected in code extractors.",
                    )
                )
            for ep in sorted(code_endpoints - spec_endpoints)[:10]:
                architecture_drift.append(
                    ArchitectureDriftFinding(
                        kind="implemented_not_documented",
                        entity=ep,
                        detail="Endpoint exists in code but is missing from OpenAPI specification.",
                    )
                )

        # 3. Proactive integration risks (high-fan-in hubs without tests)
        untested_hubs = [
            n.name
            for n in nodes
            if in_degree.get(n.id, 0) >= 5 and n.id not in tested_targets
        ]
        if untested_hubs:
            integration_risks.append(
                IntegrationRiskFinding(
                    severity="medium",
                    title=f"{len(untested_hubs)} high-fan-in component(s) lack direct test edges",
                    detail=f"High-coupling entities without detected TEST links: {', '.join(untested_hubs[:5])}",
                )
            )

        summary = (
            f"Analyzed {len(repositories)} repository(s) and {len(docs)} document(s): "
            f"found {len(stale_docs)} stale-doc warning(s), "
            f"{len(architecture_drift)} architecture drift item(s), and "
            f"{len(integration_risks)} proactive integration risk(s)."
        )

        return EngineeringIntelligenceResponse(
            project_id=project_id,
            summary=summary,
            stale_docs=stale_docs,
            architecture_drift=architecture_drift,
            integration_risks=integration_risks,
            uncertainty_note=(
                "Findings are derived deterministically from indexed repository files, "
                "static AST/OpenAPI extractors, and uploaded project documents."
            ),
        )
