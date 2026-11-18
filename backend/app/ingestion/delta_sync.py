"""
TrunkHQ — Delta Knowledge Freshness Service.

Updates only affected files, chunks, embeddings, and graph entities on
GitHub push events instead of cloning and re-indexing the entire repository.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chunking.chunker import chunk_text
from app.core.config import get_settings
from app.core.logging import get_logger
from app.embeddings import get_embedding_service
from app.graph.engine import GraphExtractorEngine
from app.ingestion.cloner import validate_github_url
from app.models.chunk import CodeChunk
from app.models.file import RepositoryFile
from app.models.graph import GraphNode
from app.repositories.file_repo import FileRepository
from app.repositories.graph_repo import GraphRepository
from app.repositories.repository_repo import RepositoryRepository

logger = get_logger("delta_sync")

MAX_DELTA_FILES = 50


def _is_safe_rel_path(rel_path: str) -> bool:
    if not rel_path or rel_path.startswith("/") or "\\" in rel_path:
        return False
    parts = Path(rel_path).parts
    return ".." not in parts and ".git" not in parts


def extract_push_diff(payload: dict) -> tuple[Optional[str], set[str], set[str]]:
    """
    Parse GitHub push webhook commits into (after_sha, changed_paths, removed_paths).
    """
    after_sha: Optional[str] = payload.get("after")
    changed: set[str] = set()
    removed: set[str] = set()

    for commit in payload.get("commits") or []:
        for p in commit.get("added") or []:
            if _is_safe_rel_path(p):
                changed.add(p)
                removed.discard(p)
        for p in commit.get("modified") or []:
            if _is_safe_rel_path(p):
                changed.add(p)
                removed.discard(p)
        for p in commit.get("removed") or []:
            if _is_safe_rel_path(p):
                changed.discard(p)
                removed.add(p)

    return after_sha, changed, removed


async def fetch_github_files(
    owner: str,
    repo_name: str,
    paths: set[str],
    ref: str,
    github_token: Optional[str] = None,
) -> dict[str, str]:
    """Fetch raw text content for changed files directly from GitHub."""
    results: dict[str, str] = {}
    if not paths:
        return results

    headers = {"Accept": "application/vnd.github.v3.raw"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        for rel_path in sorted(paths):
            url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{rel_path}?ref={ref}"
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and "\x00" not in resp.text:
                    results[rel_path] = resp.text
            except Exception as exc:
                logger.warning("Delta fetch skipped for file", path=rel_path, error=str(exc))
    return results


async def apply_delta_update(
    session: AsyncSession,
    repository_id: UUID,
    owner_user_id: UUID,
    after_sha: Optional[str],
    fetched_files: dict[str, str],
    removed_paths: set[str],
) -> tuple[int, int]:
    """
    Incrementally replace chunks, embeddings, and graph nodes for changed/removed paths.
    Returns (updated_file_count, updated_chunk_count).
    """
    settings = get_settings()
    affected_paths = set(fetched_files.keys()) | removed_paths
    if not affected_paths:
        return 0, 0

    file_dao = FileRepository(session)
    existing_files = await file_dao.list_by_repository(repository_id)
    ids_to_delete = [f.id for f in existing_files if f.path in affected_paths]
    if ids_to_delete:
        await file_dao.delete_by_ids(ids_to_delete)

    # Delete stale graph nodes whose source_uri is in affected_paths (edges cascade)
    await session.execute(
        delete(GraphNode).where(
            GraphNode.repository_id == repository_id,
            GraphNode.source_uri.in_(affected_paths),
        )
    )

    files_with_chunks: list[tuple[RepositoryFile, list[CodeChunk]]] = []
    chunks_to_embed: list[CodeChunk] = []
    graph_payload: list[tuple[str, str, Optional[str]]] = []

    for rel_path, content in fetched_files.items():
        if not content.strip():
            continue
        content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
        lang = Path(rel_path).suffix.lstrip(".") or "text"
        file_rec = RepositoryFile(
            repository_id=repository_id,
            path=rel_path,
            filename=Path(rel_path).name,
            language=lang,
            size_bytes=len(content.encode("utf-8", errors="replace")),
            content_hash=content_hash,
        )
        raw_chunks = chunk_text(
            content=content,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        chunk_recs = [
            CodeChunk(
                repository_id=repository_id,
                chunk_index=tc.chunk_index,
                content=tc.content,
                start_line=tc.start_line,
                end_line=tc.end_line,
                language=lang,
            )
            for tc in raw_chunks
        ]
        chunks_to_embed.extend(chunk_recs)
        files_with_chunks.append((file_rec, chunk_recs))
        graph_payload.append((rel_path, content, content_hash))

    if chunks_to_embed:
        embeddings = await get_embedding_service().embed_texts([c.content for c in chunks_to_embed])
        for chunk_obj, emb in zip(chunks_to_embed, embeddings):
            chunk_obj.embedding = emb

    if files_with_chunks:
        await file_dao.save_files_and_chunks(files_with_chunks)

    if graph_payload:
        engine = GraphExtractorEngine()
        nodes_payload, edges_payload, _ = engine.extract_repository_graph(
            repository_id=repository_id,
            workspace_id=owner_user_id,
            files=graph_payload,
        )
        graph_dao = GraphRepository(session)
        key_to_id = await graph_dao.upsert_nodes(
            workspace_id=owner_user_id,
            repository_id=repository_id,
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
        if resolved_edges:
            await graph_dao.upsert_edges(
                workspace_id=owner_user_id,
                repository_id=repository_id,
                edges=resolved_edges,
            )

    # Recompute totals
    total_files = (
        await session.execute(
            select(func.count()).select_from(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        )
    ).scalar_one()
    total_chunks = (
        await session.execute(
            select(func.count()).select_from(CodeChunk).where(CodeChunk.repository_id == repository_id)
        )
    ).scalar_one()

    repo_dao = RepositoryRepository(session)
    await repo_dao.update_status(
        repository_id,
        "READY",
        file_count=int(total_files),
        chunk_count=int(total_chunks),
        last_indexed_at=datetime.now(timezone.utc),
    )
    repo = await repo_dao.get_by_id_unscoped(repository_id)
    if repo and after_sha:
        repo.last_indexed_commit_sha = after_sha
    await session.commit()
    return len(files_with_chunks), len(chunks_to_embed)


async def run_delta_sync(
    session_factory: async_sessionmaker[AsyncSession],
    repository_id: UUID,
    after_sha: Optional[str],
    changed_paths: set[str],
    removed_paths: set[str],
) -> None:
    """Background task wrapper for delta knowledge freshness."""
    async with session_factory() as session:
        repo = await RepositoryRepository(session).get_by_id_unscoped(repository_id)
        if not repo:
            return
        owner, repo_name = validate_github_url(repo.github_url)
        ref = after_sha or repo.branch or "main"
        fetched = await fetch_github_files(owner, repo_name, changed_paths, ref=ref)
        await apply_delta_update(
            session=session,
            repository_id=repo.id,
            owner_user_id=repo.user_id,
            after_sha=after_sha,
            fetched_files=fetched,
            removed_paths=removed_paths,
        )
