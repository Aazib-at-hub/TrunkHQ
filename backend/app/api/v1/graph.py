"""
TrunkHQ — Relationship Graph API Endpoints.

Provides workspace-isolated, repository-aware endpoints for graph slicing,
node inspection, 1-hop neighborhoods, path finding, search, and blast radius impact analysis.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_tenant_context
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.database.session import get_db
from app.graph.engine import GraphExtractorEngine
from app.models.graph import GraphIndexRun
from app.models.repository import Repository
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.file_repo import FileRepository
from app.repositories.graph_repo import GraphRepository
from app.repositories.repository_repo import RepositoryRepository
from app.schemas.graph import (
    EngineeringIntelligenceResponse,
    FindPathRequest,
    FindPathResponse,
    GraphEdgeSchema,
    GraphInsightsResponse,
    GraphNodeSchema,
    GraphSliceResponse,
    GraphStatusResponse,
    HubNodeInsight,
    ImpactReportRequest,
    ImpactReportResponse,
    ImpactRequest,
    ImpactResponse,
    KeyModuleInsight,
    NodeNeighborsResponse,
    PathStepSchema,
)

router = APIRouter(tags=["Graph"])


async def _verify_repo_access(
    repo_id: UUID,
    user_id: UUID,
    session: AsyncSession,
    organization_id: Optional[UUID] = None,
) -> Repository:
    """Ensure repository exists within the active organization workspace."""
    repo_dao = RepositoryRepository(session)
    repo = (
        await repo_dao.get_by_id_in_org(repo_id, organization_id)
        if organization_id is not None
        else await repo_dao.get_by_id_shared(repo_id)
    )
    if not repo:
        raise NotFoundError("Repository not found")
    return repo


@router.get(
    "/repositories/{repo_id}/graph",
    response_model=GraphSliceResponse,
    summary="Get bounded relationship graph for a repository",
)
async def get_repository_graph(
    repo_id: UUID,
    node_types: Optional[list[str]] = Query(None),
    limit: int = Query(default=300, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> GraphSliceResponse:
    """Fetch bounded, paginated nodes and connecting edges for a repository."""
    repo = await _verify_repo_access(
        repo_id, tenant.user_id, db, organization_id=tenant.organization_id
    )
    graph_dao = GraphRepository(db)

    nodes = await graph_dao.get_nodes_by_repository(
        workspace_id=repo.user_id,
        repository_id=repo_id,
        node_types=node_types,
        limit=limit,
        offset=offset,
    )

    node_ids = {n.id for n in nodes}
    edges = await graph_dao.get_edges_by_repository(
        workspace_id=repo.user_id,
        repository_id=repo_id,
        node_ids=node_ids,
        limit=limit * 2,
    )

    return GraphSliceResponse(
        repository_id=repo_id,
        nodes=[GraphNodeSchema.model_validate(n) for n in nodes],
        edges=[GraphEdgeSchema.model_validate(e) for e in edges],
        total_nodes=len(nodes),
        total_edges=len(edges),
    )


@router.get(
    "/repositories/{repo_id}/graph/nodes/{node_id}",
    response_model=GraphNodeSchema,
    summary="Get single graph node details",
)
async def get_graph_node(
    repo_id: UUID,
    node_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> GraphNodeSchema:
    """Fetch metadata and source details for a specific graph node."""
    repo = await _verify_repo_access(
        repo_id, tenant.user_id, db, organization_id=tenant.organization_id
    )
    graph_dao = GraphRepository(db)

    node = await graph_dao.get_node(workspace_id=repo.user_id, node_id=node_id)
    if not node or node.repository_id != repo_id:
        raise NotFoundError("Graph node not found")

    return GraphNodeSchema.model_validate(node)


@router.get(
    "/repositories/{repo_id}/graph/nodes/{node_id}/neighbors",
    response_model=NodeNeighborsResponse,
    summary="Get 1-hop neighborhood of a graph node",
)
async def get_node_neighbors(
    repo_id: UUID,
    node_id: UUID,
    direction: str = Query(default="both", pattern="^(in|out|both)$"),
    edge_types: Optional[list[str]] = Query(None),
    limit: int = Query(default=100, ge=1, le=500),
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> NodeNeighborsResponse:
    """Fetch neighbors, outgoing edges, and incoming edges for an entity."""
    repo = await _verify_repo_access(
        repo_id, tenant.user_id, db, organization_id=tenant.organization_id
    )
    graph_dao = GraphRepository(db)

    res = await graph_dao.get_neighbors(
        workspace_id=repo.user_id,
        node_id=node_id,
        edge_types=edge_types,
        direction=direction,
        limit=limit,
        repository_id=repo_id,
    )
    if not res["node"]:
        raise NotFoundError("Graph node not found")

    return NodeNeighborsResponse(
        node=GraphNodeSchema.model_validate(res["node"]),
        outgoing_edges=[GraphEdgeSchema.model_validate(e) for e in res["outgoing_edges"]],
        incoming_edges=[GraphEdgeSchema.model_validate(e) for e in res["incoming_edges"]],
        neighbors=[GraphNodeSchema.model_validate(n) for n in res["neighbors"]],
    )


@router.post(
    "/repositories/{repo_id}/graph/paths",
    response_model=FindPathResponse,
    summary="Find relationship path between two nodes",
)
async def find_graph_path(
    repo_id: UUID,
    data: FindPathRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> FindPathResponse:
    """Compute shortest relationship path connecting source and target nodes."""
    repo = await _verify_repo_access(
        repo_id, tenant.user_id, db, organization_id=tenant.organization_id
    )
    graph_dao = GraphRepository(db)

    steps_raw = await graph_dao.find_path(
        workspace_id=repo.user_id,
        source_id=data.source_id,
        target_id=data.target_id,
        max_depth=data.max_depth,
        repository_id=repo_id,
    )

    steps: list[PathStepSchema] = []
    for step in steps_raw:
        n = GraphNodeSchema.model_validate(step["node"]) if step.get("node") else None
        e = GraphEdgeSchema.model_validate(step["edge"]) if step.get("edge") else None
        steps.append(PathStepSchema(node=n, edge=e))

    return FindPathResponse(
        found=len(steps) > 0,
        length=max(0, len(steps) - 1),
        steps=steps,
    )


@router.post(
    "/repositories/{repo_id}/graph/impact",
    response_model=ImpactResponse,
    summary="Compute blast radius and affected callers",
)
async def compute_graph_impact(
    repo_id: UUID,
    data: ImpactRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> ImpactResponse:
    """Analyze blast radius, affected callers, and related test suites."""
    repo = await _verify_repo_access(
        repo_id, tenant.user_id, db, organization_id=tenant.organization_id
    )
    graph_dao = GraphRepository(db)

    impact_data = await graph_dao.get_impact(
        workspace_id=repo.user_id,
        node_id=data.node_id,
        max_depth=data.max_depth,
        edge_types=data.edge_types,
        include_tests=data.include_tests,
        repository_id=repo_id,
    )

    if not impact_data["root"]:
        raise NotFoundError("Root node for impact analysis not found")

    return ImpactResponse(
        root=GraphNodeSchema.model_validate(impact_data["root"]),
        impacted_nodes=[GraphNodeSchema.model_validate(n) for n in impact_data["impacted_nodes"]],
        edges=[GraphEdgeSchema.model_validate(e) for e in impact_data["edges"]],
        depth_levels=impact_data["depth_levels"],
        total_impacted=len(impact_data["impacted_nodes"]),
    )


@router.post(
    "/repositories/{repo_id}/graph/impact-report",
    response_model=ImpactReportResponse,
    summary="Generate Cortex Impact Intelligence report for a target entity",
)
async def generate_impact_report(
    repo_id: UUID,
    data: ImpactReportRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> ImpactReportResponse:
    """Produce an evidence-backed impact report with risks and related documentation."""
    from app.graph.reasoning import GraphReasoningService

    repo = await _verify_repo_access(
        repo_id, tenant.user_id, db, organization_id=tenant.organization_id
    )
    return await GraphReasoningService(db).build_impact_report(
        workspace_id=repo.user_id,
        repository_id=repo_id,
        node_id=data.node_id,
        max_depth=data.max_depth,
        change_description=data.change_description,
        project_id=getattr(repo, "project_id", None),
        organization_id=tenant.organization_id,
    )


@router.get(
    "/repositories/{repo_id}/graph/search",
    response_model=list[GraphNodeSchema],
    summary="Search graph nodes by name or qualified name",
)
async def search_graph_nodes(
    repo_id: UUID,
    q: str = Query(..., min_length=1),
    node_type: Optional[str] = Query(None),
    limit: int = Query(default=20, ge=1, le=100),
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> list[GraphNodeSchema]:
    """Search indexed entities matching query string."""
    repo = await _verify_repo_access(
        repo_id, tenant.user_id, db, organization_id=tenant.organization_id
    )
    graph_dao = GraphRepository(db)

    nodes = await graph_dao.search_nodes(
        workspace_id=repo.user_id,
        repository_id=repo_id,
        query=q,
        node_type=node_type,
        limit=limit,
    )
    return [GraphNodeSchema.model_validate(n) for n in nodes]


@router.get(
    "/repositories/{repo_id}/graph/insights",
    response_model=GraphInsightsResponse,
    summary="Get architectural hubs, entrypoints, and domain breakdown",
)
async def get_graph_insights(
    repo_id: UUID,
    top_k: int = Query(default=10, ge=1, le=50),
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> GraphInsightsResponse:
    """Compute and return key hubs, entrypoints, and module clustering."""
    repo = await _verify_repo_access(
        repo_id, tenant.user_id, db, organization_id=tenant.organization_id
    )
    graph_dao = GraphRepository(db)

    insights = await graph_dao.get_insights(
        workspace_id=repo.user_id,
        repository_id=repo_id,
        top_k=top_k,
    )

    hub_nodes = [
        HubNodeInsight(
            node=GraphNodeSchema.model_validate(h["node"]),
            in_degree=h["in_degree"],
            out_degree=h["out_degree"],
            total_degree=h["total_degree"],
            role=h["role"],
        )
        for h in insights["hub_nodes"]
    ]

    entrypoints = [
        HubNodeInsight(
            node=GraphNodeSchema.model_validate(e["node"]),
            in_degree=e["in_degree"],
            out_degree=e["out_degree"],
            total_degree=e["total_degree"],
            role=e["role"],
        )
        for e in insights["entrypoints"]
    ]

    key_modules = [
        KeyModuleInsight(module=m["module"], entity_count=m["entity_count"])
        for m in insights["key_modules"]
    ]

    return GraphInsightsResponse(
        repository_id=repo_id,
        total_nodes=insights["total_nodes"],
        total_edges=insights["total_edges"],
        domains=insights["domains"],
        hub_nodes=hub_nodes,
        entrypoints=entrypoints,
        key_modules=key_modules,
    )


@router.get(
    "/repositories/{repo_id}/graph/status",
    response_model=GraphStatusResponse,
    summary="Get relationship graph index status",
)
async def get_graph_status(
    repo_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> GraphStatusResponse:
    """Inspect latest graph indexing run metrics and status."""
    repo = await _verify_repo_access(
        repo_id, tenant.user_id, db, organization_id=tenant.organization_id
    )
    graph_dao = GraphRepository(db)

    latest_run = await graph_dao.get_latest_index_run(
        workspace_id=repo.user_id,
        repository_id=repo_id,
    )

    if not latest_run:
        return GraphStatusResponse(
            repository_id=repo_id,
            status="NOT_INDEXED",
        )

    return GraphStatusResponse(
        repository_id=repo_id,
        status=latest_run.status,
        nodes_count=latest_run.nodes_created,
        edges_count=latest_run.edges_created,
        nodes_created=latest_run.nodes_created,
        edges_created=latest_run.edges_created,
        nodes_deleted=latest_run.nodes_deleted,
        edges_deleted=latest_run.edges_deleted,
        extractor_version=latest_run.extractor_version,
        error_summary=latest_run.error_summary,
        started_at=latest_run.started_at,
        completed_at=latest_run.completed_at,
    )


@router.post(
    "/repositories/{repo_id}/graph/reindex",
    response_model=GraphStatusResponse,
    summary="Index or re-index relationship graph from repository files",
)
async def reindex_graph(
    repo_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> GraphStatusResponse:
    """Extract and index nodes and relationships from existing repository files."""
    repo = await _verify_repo_access(
        repo_id, tenant.user_id, db, organization_id=tenant.organization_id
    )
    if repo.user_id != tenant.user_id:
        raise ForbiddenError("Only the project owner can reindex the knowledge graph")

    file_dao = FileRepository(db)
    chunk_dao = ChunkRepository(db)
    graph_dao = GraphRepository(db)

    files = await file_dao.list_by_repository(repo_id)
    if not files:
        raise ValidationError("Repository has no indexed files to extract graph from.")

    run_record = GraphIndexRun(
        workspace_id=repo.user_id,
        repository_id=repo_id,
        status="RUNNING",
    )
    saved_run = await graph_dao.create_index_run(run_record)
    await db.commit()

    try:
        all_chunks = await chunk_dao.list_by_repository(repo_id)
        chunks_by_file: dict[UUID, list] = {}
        for chunk in all_chunks:
            chunks_by_file.setdefault(chunk.file_id, []).append(chunk)

        graph_files_payload: list[tuple[str, str, Optional[str]]] = []
        for f in files:
            chunks = chunks_by_file.get(f.id, [])
            lines: dict[int, str] = {}
            for chunk in chunks:
                for offset, text in enumerate(chunk.content.split("\n")):
                    lines.setdefault(chunk.start_line + offset, text)
            max_line = max(lines) if lines else 0
            content = "\n".join(lines.get(i, "") for i in range(1, max_line + 1))
            graph_files_payload.append((f.path, content, f.content_hash))

        engine = GraphExtractorEngine()
        nodes_payload, edges_payload, active_keys = engine.extract_repository_graph(
            repository_id=repo_id,
            workspace_id=repo.user_id,
            files=graph_files_payload,
        )

        key_to_id = await graph_dao.upsert_nodes(
            workspace_id=repo.user_id,
            repository_id=repo_id,
            nodes=nodes_payload,
        )

        resolved_edges = []
        for e in edges_payload:
            src_id = key_to_id.get(e["source_key"])
            tgt_id = key_to_id.get(e["target_key"])
            if src_id and tgt_id and src_id != tgt_id:
                e_copy = dict(e)
                e_copy["source_node_id"] = src_id
                e_copy["target_node_id"] = tgt_id
                del e_copy["source_key"]
                del e_copy["target_key"]
                resolved_edges.append(e_copy)

        edges_count = await graph_dao.upsert_edges(
            workspace_id=repo.user_id,
            repository_id=repo_id,
            edges=resolved_edges,
        )

        del_nodes, del_edges = await graph_dao.reconcile_deleted_entities(
            workspace_id=repo.user_id,
            repository_id=repo_id,
            active_stable_keys=active_keys,
        )

        updated_run = await graph_dao.update_index_run(
            run_id=saved_run.id,
            status="READY",
            nodes_created=len(nodes_payload),
            edges_created=edges_count,
            nodes_deleted=del_nodes,
            edges_deleted=del_edges,
        )
        await db.commit()

        return GraphStatusResponse(
            repository_id=repo_id,
            status="READY",
            nodes_count=len(nodes_payload),
            edges_count=edges_count,
            nodes_deleted=del_nodes,
            edges_deleted=del_edges,
            started_at=saved_run.started_at,
            completed_at=updated_run.completed_at if updated_run else None,
        )
    except Exception as exc:
        await db.rollback()
        await graph_dao.update_index_run(
            run_id=saved_run.id,
            status="FAILED",
            error_summary=str(exc),
        )
        await db.commit()
        raise


def build_document_reference_links(
    docs_with_text: list[tuple[UUID, str, str]],
    code_nodes: list[GraphNodeSchema],
    project_id: UUID,
) -> tuple[list[GraphNodeSchema], list[GraphEdgeSchema]]:
    """
    Create deterministic DOCUMENT nodes and DOCUMENTS edges only when a project
    document explicitly mentions a code node's name (>= 4 chars) or source_uri.
    """
    import uuid as _uuid

    doc_nodes: list[GraphNodeSchema] = []
    doc_edges: list[GraphEdgeSchema] = []
    for doc_id, title, combined_text in docs_with_text:
        text_lower = combined_text.lower()
        doc_node = GraphNodeSchema(
            id=doc_id,
            node_type="document",
            stable_key=f"project:{project_id}:document:{doc_id}",
            name=title,
            qualified_name=title,
            description="Uploaded project documentation",
            properties={"document_id": str(doc_id)},
            source_kind="documentation",
            source_uri=title,
        )
        doc_nodes.append(doc_node)
        for cn in code_nodes:
            matched = False
            if cn.source_uri and len(cn.source_uri) >= 4 and cn.source_uri.lower() in text_lower:
                matched = True
            elif len(cn.name) >= 4 and cn.name.lower() in text_lower:
                matched = True
            if matched:
                edge_uuid = _uuid.uuid5(_uuid.NAMESPACE_URL, f"{doc_id}:DOCUMENTS:{cn.id}")
                doc_edges.append(
                    GraphEdgeSchema(
                        id=edge_uuid,
                        source_node_id=doc_id,
                        target_node_id=cn.id,
                        edge_type="DOCUMENTS",
                        confidence=0.75,
                        evidence_kind="doc_reference",
                    )
                )
    return doc_nodes, doc_edges


@router.get(
    "/projects/{project_id}/graph",
    response_model=GraphSliceResponse,
    summary="Get cross-repository and document knowledge graph for a project",
)
async def get_project_graph(
    project_id: UUID,
    node_types: Optional[list[str]] = Query(None),
    limit: int = Query(default=300, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> GraphSliceResponse:
    """Fetch bounded subgraph across all repositories and documents in a project."""
    from app.repositories.document_repo import DocumentRepository
    from app.repositories.project_repo import ProjectRepository

    project = await ProjectRepository(db).get_by_id_in_org(
        project_id, tenant.organization_id
    )
    if not project:
        raise NotFoundError("Project not found")

    repo_ids = [r.id for r in (getattr(project, "repositories", None) or [])]
    graph_dao = GraphRepository(db)
    raw_nodes = await graph_dao.get_nodes_by_repositories(
        repository_ids=repo_ids,
        node_types=node_types,
        limit=limit,
        offset=offset,
    )
    node_ids = {n.id for n in raw_nodes}
    raw_edges = await graph_dao.get_edges_by_repositories(
        repository_ids=repo_ids,
        node_ids=node_ids,
        limit=limit * 2,
    )

    code_node_schemas = [GraphNodeSchema.model_validate(n) for n in raw_nodes]
    edge_schemas = [GraphEdgeSchema.model_validate(e) for e in raw_edges]

    doc_dao = DocumentRepository(db)
    docs = await doc_dao.list_by_project(project_id, tenant.organization_id)
    docs_with_text: list[tuple[UUID, str, str]] = []
    for doc in docs:
        chunks = await doc_dao.list_chunks(doc.id, tenant.organization_id)
        docs_with_text.append((doc.id, doc.title, "\n".join(c.content for c in chunks)))

    doc_nodes, doc_edges = build_document_reference_links(
        docs_with_text, code_node_schemas, project_id
    )
    all_nodes = code_node_schemas + doc_nodes
    all_edges = edge_schemas + doc_edges

    return GraphSliceResponse(
        repository_id=repo_ids[0] if repo_ids else project_id,
        nodes=all_nodes,
        edges=all_edges,
        total_nodes=len(all_nodes),
        total_edges=len(all_edges),
    )


@router.get(
    "/projects/{project_id}/intelligence",
    response_model=EngineeringIntelligenceResponse,
    summary="Level 3 Engineering Intelligence: stale-doc, drift, and integration risk report",
)
async def get_project_engineering_intelligence(
    project_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> EngineeringIntelligenceResponse:
    """Detect stale documentation, OpenAPI/code drift, and proactive integration risks."""
    from app.graph.reasoning import GraphReasoningService
    from app.repositories.project_repo import ProjectRepository

    project = await ProjectRepository(db).get_by_id_in_org(
        project_id, tenant.organization_id
    )
    if not project:
        raise NotFoundError("Project not found")

    repos = list(getattr(project, "repositories", None) or [])
    return await GraphReasoningService(db).build_engineering_intelligence_report(
        project_id=project_id,
        organization_id=tenant.organization_id,
        repositories=repos,
    )
