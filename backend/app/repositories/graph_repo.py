"""
Cortex Engineering — Relationship Graph Data Access Object.

Provides high-performance, workspace-isolated access to nodes, edges,
index runs, neighborhood traversals, impact analysis, and paths.
"""

from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional, Sequence
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import EdgeType, GraphEdge, GraphIndexRun, GraphNode, NodeType


class GraphRepository:
    """PostgreSQL data access operations for the relationship graph."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Index Runs ───────────────────────────────────────────────────────────

    async def create_index_run(self, run: GraphIndexRun) -> GraphIndexRun:
        """Record the start of a graph indexing run."""
        self._session.add(run)
        await self._session.flush()
        await self._session.refresh(run)
        return run

    async def update_index_run(
        self,
        run_id: UUID,
        **kwargs: Any,
    ) -> Optional[GraphIndexRun]:
        """Update metrics, status, or timestamps of an index run."""
        if "completed_at" not in kwargs and kwargs.get("status") in {"READY", "FAILED"}:
            kwargs["completed_at"] = datetime.now(timezone.utc)

        await self._session.execute(
            update(GraphIndexRun)
            .where(GraphIndexRun.id == run_id)
            .values(**kwargs)
        )
        await self._session.flush()
        result = await self._session.execute(
            select(GraphIndexRun).where(GraphIndexRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_index_run(
        self, workspace_id: UUID, repository_id: UUID
    ) -> Optional[GraphIndexRun]:
        """Fetch the most recent indexing run for repository."""
        stmt = (
            select(GraphIndexRun)
            .where(
                GraphIndexRun.workspace_id == workspace_id,
                GraphIndexRun.repository_id == repository_id,
            )
            .order_by(GraphIndexRun.started_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # ── Upserts & Reconciliation ─────────────────────────────────────────────

    async def upsert_nodes(
        self,
        workspace_id: UUID,
        repository_id: UUID,
        nodes: list[dict[str, Any]],
    ) -> dict[str, UUID]:
        """
        Idempotently insert or update graph nodes by stable_key.

        Returns:
            dict mapping stable_key -> node UUID
        """
        if not nodes:
            return {}

        key_to_id: dict[str, UUID] = {}

        for item in nodes:
            node_id = item.get("id") or uuid.uuid4()
            stmt = (
                pg_insert(GraphNode)
                .values(
                    id=node_id,
                    workspace_id=workspace_id,
                    repository_id=repository_id,
                    node_type=item["node_type"],
                    stable_key=item["stable_key"],
                    name=item["name"],
                    qualified_name=item.get("qualified_name"),
                    description=item.get("description"),
                    properties=item.get("properties", {}),
                    status=item.get("status", "active"),
                    source_kind=item.get("source_kind", "code"),
                    source_uri=item.get("source_uri"),
                    source_commit=item.get("source_commit"),
                    content_hash=item.get("content_hash"),
                )
                .on_conflict_do_update(
                    constraint="uq_graph_nodes_workspace_stable_key",
                    set_={
                        "name": item["name"],
                        "qualified_name": item.get("qualified_name"),
                        "description": item.get("description"),
                        "properties": item.get("properties", {}),
                        "status": item.get("status", "active"),
                        "source_uri": item.get("source_uri"),
                        "source_commit": item.get("source_commit"),
                        "content_hash": item.get("content_hash"),
                        "updated_at": func.now(),
                    },
                )
                .returning(GraphNode.id, GraphNode.stable_key)
            )
            res = await self._session.execute(stmt)
            row = res.one()
            key_to_id[row.stable_key] = row.id

        await self._session.flush()
        return key_to_id

    async def upsert_edges(
        self,
        workspace_id: UUID,
        repository_id: UUID,
        edges: list[dict[str, Any]],
    ) -> int:
        """
        Idempotently insert or update graph edges.

        Returns:
            Number of successfully upserted edges
        """
        if not edges:
            return 0

        count = 0
        for item in edges:
            edge_id = item.get("id") or uuid.uuid4()
            stmt = (
                pg_insert(GraphEdge)
                .values(
                    id=edge_id,
                    workspace_id=workspace_id,
                    repository_id=repository_id,
                    source_node_id=item["source_node_id"],
                    target_node_id=item["target_node_id"],
                    edge_type=item["edge_type"],
                    properties=item.get("properties", {}),
                    confidence=item.get("confidence", 1.0),
                    evidence_kind=item.get("evidence_kind", "static"),
                    source_uri=item.get("source_uri"),
                    source_commit=item.get("source_commit"),
                    content_hash=item.get("content_hash"),
                )
                .on_conflict_do_update(
                    constraint="uq_graph_edges_unique_relation",
                    set_={
                        "properties": item.get("properties", {}),
                        "confidence": item.get("confidence", 1.0),
                        "evidence_kind": item.get("evidence_kind", "static"),
                        "source_uri": item.get("source_uri"),
                        "source_commit": item.get("source_commit"),
                        "content_hash": item.get("content_hash"),
                        "updated_at": func.now(),
                    },
                )
            )
            await self._session.execute(stmt)
            count += 1

        await self._session.flush()
        return count

    async def reconcile_deleted_entities(
        self,
        workspace_id: UUID,
        repository_id: UUID,
        active_stable_keys: set[str],
    ) -> tuple[int, int]:
        """
        Remove nodes and edges whose source code entities no longer exist.

        Only purges source_kind='code' entities so docs and decisions are preserved.
        """
        # Find stale code nodes
        stmt = (
            select(GraphNode.id)
            .where(
                GraphNode.workspace_id == workspace_id,
                GraphNode.repository_id == repository_id,
                GraphNode.source_kind == "code",
                GraphNode.stable_key.not_in(active_stable_keys),
            )
        )
        res = await self._session.execute(stmt)
        stale_ids = res.scalars().all()

        if not stale_ids:
            return 0, 0

        # Delete edges touching stale nodes
        del_edges = (
            delete(GraphEdge)
            .where(
                GraphEdge.workspace_id == workspace_id,
                GraphEdge.repository_id == repository_id,
                or_(
                    GraphEdge.source_node_id.in_(stale_ids),
                    GraphEdge.target_node_id.in_(stale_ids),
                ),
            )
        )
        edge_res = await self._session.execute(del_edges)
        deleted_edges_count: int = getattr(edge_res, "rowcount", 0) or 0

        # Delete stale nodes
        del_nodes = (
            delete(GraphNode)
            .where(
                GraphNode.workspace_id == workspace_id,
                GraphNode.id.in_(stale_ids),
            )
        )
        node_res = await self._session.execute(del_nodes)
        deleted_nodes_count: int = getattr(node_res, "rowcount", 0) or 0

        await self._session.flush()
        return deleted_nodes_count, deleted_edges_count

    # ── Node and Neighborhood Reads ──────────────────────────────────────────

    async def get_node(self, workspace_id: UUID, node_id: UUID) -> Optional[GraphNode]:
        """Fetch node with workspace isolation."""
        stmt = select(GraphNode).where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.id == node_id,
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_node_by_stable_key(
        self, workspace_id: UUID, stable_key: str
    ) -> Optional[GraphNode]:
        """Fetch node by deterministic natural key."""
        stmt = select(GraphNode).where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.stable_key == stable_key,
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_nodes_by_repository(
        self,
        workspace_id: UUID,
        repository_id: UUID,
        node_types: Optional[list[str]] = None,
        limit: int = 300,
    ) -> Sequence[GraphNode]:
        """Fetch bounded list of nodes in a repository."""
        stmt = select(GraphNode).where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.repository_id == repository_id,
        )
        if node_types:
            stmt = stmt.where(GraphNode.node_type.in_(node_types))
        stmt = stmt.limit(limit)
        res = await self._session.execute(stmt)
        return res.scalars().all()

    async def get_edges_by_repository(
        self,
        workspace_id: UUID,
        repository_id: UUID,
        node_ids: Optional[set[UUID]] = None,
        limit: int = 600,
    ) -> Sequence[GraphEdge]:
        """Fetch bounded edges in a repository, optionally restricted to node set."""
        stmt = select(GraphEdge).where(
            GraphEdge.workspace_id == workspace_id,
            GraphEdge.repository_id == repository_id,
        )
        if node_ids:
            stmt = stmt.where(
                GraphEdge.source_node_id.in_(node_ids),
                GraphEdge.target_node_id.in_(node_ids),
            )
        stmt = stmt.limit(limit)
        res = await self._session.execute(stmt)
        return res.scalars().all()

    async def get_neighbors(
        self,
        workspace_id: UUID,
        node_id: UUID,
        edge_types: Optional[list[str]] = None,
        direction: str = "both",
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Retrieve 1-hop neighborhood of a node.

        Returns:
            dict containing node, outgoing_edges, incoming_edges, and neighbor nodes.
        """
        node = await self.get_node(workspace_id, node_id)
        if not node:
            return {"node": None, "outgoing_edges": [], "incoming_edges": [], "neighbors": []}

        outgoing: list[GraphEdge] = []
        incoming: list[GraphEdge] = []
        neighbor_ids: set[UUID] = set()

        if direction in ("out", "both"):
            stmt_out = select(GraphEdge).where(
                GraphEdge.workspace_id == workspace_id,
                GraphEdge.source_node_id == node_id,
            )
            if edge_types:
                stmt_out = stmt_out.where(GraphEdge.edge_type.in_(edge_types))
            stmt_out = stmt_out.limit(limit)
            res_out = await self._session.execute(stmt_out)
            outgoing = list(res_out.scalars().all())
            neighbor_ids.update(e.target_node_id for e in outgoing)

        if direction in ("in", "both"):
            stmt_in = select(GraphEdge).where(
                GraphEdge.workspace_id == workspace_id,
                GraphEdge.target_node_id == node_id,
            )
            if edge_types:
                stmt_in = stmt_in.where(GraphEdge.edge_type.in_(edge_types))
            stmt_in = stmt_in.limit(limit)
            res_in = await self._session.execute(stmt_in)
            incoming = list(res_in.scalars().all())
            neighbor_ids.update(e.source_node_id for e in incoming)

        neighbors: list[GraphNode] = []
        if neighbor_ids:
            stmt_n = select(GraphNode).where(
                GraphNode.workspace_id == workspace_id,
                GraphNode.id.in_(neighbor_ids),
            )
            res_n = await self._session.execute(stmt_n)
            neighbors = list(res_n.scalars().all())

        return {
            "node": node,
            "outgoing_edges": outgoing,
            "incoming_edges": incoming,
            "neighbors": neighbors,
        }

    # ── Path Finding ─────────────────────────────────────────────────────────

    async def find_path(
        self,
        workspace_id: UUID,
        source_id: UUID,
        target_id: UUID,
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Find shortest path between source and target nodes via BFS.

        Returns:
            List of path step dictionaries [{"node": ..., "edge": ...}]
        """
        if source_id == target_id:
            node = await self.get_node(workspace_id, source_id)
            return [{"node": node, "edge": None}] if node else []

        # Queue contains paths: list of (current_node_id, edge_that_led_here)
        queue: deque[list[tuple[UUID, Optional[GraphEdge]]]] = deque()
        queue.append([(source_id, None)])
        visited: set[UUID] = {source_id}

        found_path_tuples: Optional[list[tuple[UUID, Optional[GraphEdge]]]] = None

        while queue:
            current_path = queue.popleft()
            if len(current_path) > max_depth + 1:
                break

            curr_node_id, _ = current_path[-1]

            # Fetch outgoing edges
            stmt = (
                select(GraphEdge)
                .where(
                    GraphEdge.workspace_id == workspace_id,
                    GraphEdge.source_node_id == curr_node_id,
                )
                .limit(50)
            )
            res = await self._session.execute(stmt)
            edges = res.scalars().all()

            for edge in edges:
                nxt_id = edge.target_node_id
                if nxt_id == target_id:
                    found_path_tuples = current_path + [(nxt_id, edge)]
                    break
                if nxt_id not in visited:
                    visited.add(nxt_id)
                    queue.append(current_path + [(nxt_id, edge)])

            if found_path_tuples:
                break

        if not found_path_tuples:
            return []

        # Hydrate nodes
        node_ids = [nid for nid, _ in found_path_tuples]
        stmt_nodes = select(GraphNode).where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.id.in_(node_ids),
        )
        res_nodes = await self._session.execute(stmt_nodes)
        node_map = {n.id: n for n in res_nodes.scalars().all()}

        path_result: list[dict[str, Any]] = []
        for nid, edge in found_path_tuples:
            path_result.append({
                "node": node_map.get(nid),
                "edge": edge,
            })

        return path_result

    # ── Impact Analysis ──────────────────────────────────────────────────────

    async def get_impact(
        self,
        workspace_id: UUID,
        node_id: UUID,
        max_depth: int = 3,
        edge_types: Optional[list[str]] = None,
        include_tests: bool = True,
    ) -> dict[str, Any]:
        """
        Compute bounded blast radius / upstream callers and dependent entities.

        Explores incoming edges (who calls / imports / depends on this entity)
        and associated test nodes.
        """
        root_node = await self.get_node(workspace_id, node_id)
        if not root_node:
            return {"root": None, "impacted_nodes": [], "edges": [], "depth_levels": {}}

        if edge_types is None:
            edge_types = [EdgeType.CALLS, EdgeType.IMPORTS, EdgeType.DEPENDS_ON]

        visited_nodes: dict[UUID, int] = {node_id: 0}  # node_id -> depth
        all_edges: list[GraphEdge] = []
        current_layer: set[UUID] = {node_id}

        for current_depth in range(1, max_depth + 1):
            if not current_layer:
                break

            # Find callers / dependents: incoming edges to current_layer
            stmt = select(GraphEdge).where(
                GraphEdge.workspace_id == workspace_id,
                GraphEdge.target_node_id.in_(current_layer),
                GraphEdge.edge_type.in_(edge_types),
            ).limit(200)
            res = await self._session.execute(stmt)
            edges = res.scalars().all()

            next_layer: set[UUID] = set()
            for e in edges:
                all_edges.append(e)
                src = e.source_node_id
                if src not in visited_nodes:
                    visited_nodes[src] = current_depth
                    next_layer.add(src)

            current_layer = next_layer

        # Include directly associated tests if requested
        if include_tests:
            stmt_tests = select(GraphEdge).where(
                GraphEdge.workspace_id == workspace_id,
                GraphEdge.target_node_id.in_(visited_nodes.keys()),
                GraphEdge.edge_type == EdgeType.TESTS,
            ).limit(100)
            res_tests = await self._session.execute(stmt_tests)
            test_edges = res_tests.scalars().all()
            for te in test_edges:
                all_edges.append(te)
                if te.source_node_id not in visited_nodes:
                    visited_nodes[te.source_node_id] = visited_nodes[te.target_node_id] + 1

        # Hydrate all impacted nodes
        stmt_all = select(GraphNode).where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.id.in_(visited_nodes.keys()),
        )
        res_all = await self._session.execute(stmt_all)
        hydrated_nodes = {n.id: n for n in res_all.scalars().all()}

        impacted_nodes = [
            hydrated_nodes[nid]
            for nid in visited_nodes.keys()
            if nid != node_id and nid in hydrated_nodes
        ]

        depth_levels = {
            str(nid): depth for nid, depth in visited_nodes.items() if nid in hydrated_nodes
        }

        return {
            "root": root_node,
            "impacted_nodes": impacted_nodes,
            "edges": all_edges,
            "depth_levels": depth_levels,
        }

    # ── Search ───────────────────────────────────────────────────────────────

    async def search_nodes(
        self,
        workspace_id: UUID,
        repository_id: UUID,
        query: str,
        node_type: Optional[str] = None,
        limit: int = 20,
    ) -> Sequence[GraphNode]:
        """Search nodes by case-insensitive name, qualified name, or description."""
        q = f"%{query.strip()}%"
        stmt = (
            select(GraphNode)
            .where(
                GraphNode.workspace_id == workspace_id,
                GraphNode.repository_id == repository_id,
                or_(
                    GraphNode.name.ilike(q),
                    GraphNode.qualified_name.ilike(q),
                    GraphNode.description.ilike(q),
                ),
            )
        )
        if node_type:
            stmt = stmt.where(GraphNode.node_type == node_type)
        stmt = stmt.limit(limit)
        res = await self._session.execute(stmt)
        return res.scalars().all()

    # ── Knowledge Insights ────────────────────────────────────────────────────

    async def get_insights(
        self,
        workspace_id: UUID,
        repository_id: UUID,
        top_k: int = 10,
    ) -> dict[str, Any]:
        """Compute architectural centrality, hub symbols, entrypoints, and domain breakdown."""
        # 1. Total counts & domain distribution
        domain_stmt = (
            select(GraphNode.source_kind, func.count(GraphNode.id))
            .where(
                GraphNode.workspace_id == workspace_id,
                GraphNode.repository_id == repository_id,
                GraphNode.status == "active",
            )
            .group_by(GraphNode.source_kind)
        )
        domain_res = await self._session.execute(domain_stmt)
        domains = {row[0]: row[1] for row in domain_res.all()}
        total_nodes = sum(domains.values())

        edge_cnt_stmt = select(func.count(GraphEdge.id)).where(
            GraphEdge.workspace_id == workspace_id,
            GraphEdge.repository_id == repository_id,
        )
        total_edges = (await self._session.execute(edge_cnt_stmt)).scalar() or 0

        # 2. Fetch active nodes and degree counts
        nodes_stmt = select(GraphNode).where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.repository_id == repository_id,
            GraphNode.status == "active",
        )
        all_nodes = (await self._session.execute(nodes_stmt)).scalars().all()
        node_map = {n.id: n for n in all_nodes}

        edges_stmt = select(
            GraphEdge.source_node_id, GraphEdge.target_node_id
        ).where(
            GraphEdge.workspace_id == workspace_id,
            GraphEdge.repository_id == repository_id,
        )
        edge_rows = (await self._session.execute(edges_stmt)).all()

        in_degrees: dict[UUID, int] = {}
        out_degrees: dict[UUID, int] = {}
        for src, tgt in edge_rows:
            out_degrees[src] = out_degrees.get(src, 0) + 1
            in_degrees[tgt] = in_degrees.get(tgt, 0) + 1

        scored_nodes = []
        entrypoints = []
        module_counts: dict[str, int] = {}

        for nid, node in node_map.items():
            in_d = in_degrees.get(nid, 0)
            out_d = out_degrees.get(nid, 0)
            tot_d = in_d + out_d

            # Module extraction
            if node.source_uri:
                top_dir = node.source_uri.split("/")[0] if "/" in node.source_uri else "root"
                module_counts[top_dir] = module_counts.get(top_dir, 0) + 1

            role = "standard"
            if tot_d >= 5:
                role = "hub"
            elif in_d == 0 and out_d > 0:
                role = "entrypoint"
            elif tot_d == 0:
                role = "isolated"

            node_item = {
                "node": node,
                "in_degree": in_d,
                "out_degree": out_d,
                "total_degree": tot_d,
                "role": role,
            }
            scored_nodes.append(node_item)

            if (
                node.node_type in {NodeType.API_ENDPOINT, NodeType.SERVICE}
                or (in_d == 0 and out_d > 0 and node.node_type in {NodeType.FUNCTION, NodeType.FILE})
            ):
                entrypoints.append(node_item)

        # Sort hubs by total degree
        scored_nodes.sort(key=lambda x: x["total_degree"], reverse=True)
        entrypoints.sort(key=lambda x: x["out_degree"], reverse=True)

        key_modules = [
            {"module": mod, "entity_count": cnt}
            for mod, cnt in sorted(module_counts.items(), key=lambda x: x[1], reverse=True)[:8]
        ]

        return {
            "repository_id": repository_id,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "domains": domains,
            "hub_nodes": scored_nodes[:top_k],
            "entrypoints": entrypoints[:top_k],
            "key_modules": key_modules,
        }

