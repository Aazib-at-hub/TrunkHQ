"""
Cortex Engineering — Relationship Graph API Endpoints.

Provides workspace-isolated, repository-aware endpoints for graph slicing,
node inspection, 1-hop neighborhoods, path finding, search, and blast radius impact analysis.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.core.exceptions import NotFoundError, ValidationError
from app.database.session import get_db
from app.graph.engine import GraphExtractorEngine
from app.models.graph import GraphIndexRun
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.file_repo import FileRepository
from app.repositories.graph_repo import GraphRepository
from app.repositories.repository_repo import RepositoryRepository
from app.schemas.graph import (
    FindPathRequest,
    FindPathResponse,
    GraphEdgeSchema,
    GraphInsightsResponse,
    GraphNodeSchema,
    GraphSliceResponse,
    GraphStatusResponse,
    HubNodeInsight,
    ImpactRequest,
    ImpactResponse,
    KeyModuleInsight,
    NodeNeighborsResponse,
    PathStepSchema,
)

router = APIRouter(tags=["Graph"])


async def _verify_repo_access(
    repo_id: UUID, user_id: UUID, session: AsyncSession
) -> None:
    """Ensure repository exists and belongs to current user/workspace."""
    repo_dao = RepositoryRepository(session)
    repo = await repo_dao.get_by_id(repo_id, user_id)
    if not repo:
        raise NotFoundError("Repository not found")


@router.get(
    "/repositories/{repo_id}/graph",
    response_model=GraphSliceResponse,
    summary="Get bounded relationship graph for a repository",
)
async def get_repository_graph(
    repo_id: UUID,
    node_types: Optional[list[str]] = Query(None),
    limit: int = Query(default=300, ge=1, le=1000),
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> GraphSliceResponse:
    """Fetch nodes and connecting edges for a repository within limits."""
    await _verify_repo_access(repo_id, current_user_id, db)
    graph_dao = GraphRepository(db)

    nodes = await graph_dao.get_nodes_by_repository(
        workspace_id=current_user_id,
        repository_id=repo_id,
        node_types=node_types,
        limit=limit,
    )

    node_ids = {n.id for n in nodes}
    edges = await graph_dao.get_edges_by_repository(
        workspace_id=current_user_id,
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
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> GraphNodeSchema:
    """Fetch metadata and source details for a specific graph node."""
    await _verify_repo_access(repo_id, current_user_id, db)
    graph_dao = GraphRepository(db)

    node = await graph_dao.get_node(workspace_id=current_user_id, node_id=node_id)
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
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> NodeNeighborsResponse:
    """Fetch neighbors, outgoing edges, and incoming edges for an entity."""
    await _verify_repo_access(repo_id, current_user_id, db)
    graph_dao = GraphRepository(db)

    res = await graph_dao.get_neighbors(
        workspace_id=current_user_id,
        node_id=node_id,
        edge_types=edge_types,
        direction=direction,
        limit=limit,
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
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> FindPathResponse:
    """Compute shortest relationship path connecting source and target nodes."""
    await _verify_repo_access(repo_id, current_user_id, db)
    graph_dao = GraphRepository(db)

    steps_raw = await graph_dao.find_path(
        workspace_id=current_user_id,
        source_id=data.source_id,
        target_id=data.target_id,
        max_depth=data.max_depth,
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
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ImpactResponse:
    """Analyze blast radius, affected callers, and related test suites."""
    await _verify_repo_access(repo_id, current_user_id, db)
    graph_dao = GraphRepository(db)

    impact_data = await graph_dao.get_impact(
        workspace_id=current_user_id,
        node_id=data.node_id,
        max_depth=data.max_depth,
        edge_types=data.edge_types,
        include_tests=data.include_tests,
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
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[GraphNodeSchema]:
    """Search indexed entities matching query string."""
    await _verify_repo_access(repo_id, current_user_id, db)
    graph_dao = GraphRepository(db)

    nodes = await graph_dao.search_nodes(
        workspace_id=current_user_id,
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
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> GraphInsightsResponse:
    """Compute and return key hubs, entrypoints, and module clustering."""
    await _verify_repo_access(repo_id, current_user_id, db)
    graph_dao = GraphRepository(db)

    insights = await graph_dao.get_insights(
        workspace_id=current_user_id,
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
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> GraphStatusResponse:
    """Inspect latest graph indexing run metrics and status."""
    await _verify_repo_access(repo_id, current_user_id, db)
    graph_dao = GraphRepository(db)

    latest_run = await graph_dao.get_latest_index_run(
        workspace_id=current_user_id,
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
        nodes_deleted=latest_run.nodes_deleted,
        edges_deleted=latest_run.edges_deleted,
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
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> GraphStatusResponse:
    """Extract and index nodes and relationships from existing repository files."""
    await _verify_repo_access(repo_id, current_user_id, db)

    file_dao = FileRepository(db)
    chunk_dao = ChunkRepository(db)
    graph_dao = GraphRepository(db)

    files = await file_dao.list_by_repository(repo_id)
    if not files:
        raise ValidationError("Repository has no indexed files to extract graph from.")

    run_record = GraphIndexRun(
        workspace_id=current_user_id,
        repository_id=repo_id,
        status="RUNNING",
    )
    saved_run = await graph_dao.create_index_run(run_record)
    await db.commit()

    try:
        graph_files_payload: list[tuple[str, str, Optional[str]]] = []
        for f in files:
            chunks = await chunk_dao.list_by_file(f.id)
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
            workspace_id=current_user_id,
            files=graph_files_payload,
        )

        key_to_id = await graph_dao.upsert_nodes(
            workspace_id=current_user_id,
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
            workspace_id=current_user_id,
            repository_id=repo_id,
            edges=resolved_edges,
        )

        del_nodes, del_edges = await graph_dao.reconcile_deleted_entities(
            workspace_id=current_user_id,
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
        await graph_dao.update_index_run(
            run_id=saved_run.id,
            status="FAILED",
            error_summary=str(exc),
        )
        await db.commit()
        raise
