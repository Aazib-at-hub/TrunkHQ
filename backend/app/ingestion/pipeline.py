"""
TrunkHQ — Ingestion Pipeline Orchestrator.

Coordinates cloning, file discovery, filtering, extraction, line-aware chunking,
embedding generation, and database persistence with status reporting.
"""

from __future__ import annotations

import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chunking.chunker import chunk_text
from app.core.config import Settings
from app.core.logging import get_logger
from app.embeddings.base import BaseEmbeddingService
from app.ingestion.cloner import clone_repository, force_rm_directory, get_head_commit_sha
from app.ingestion.discovery import discover_files
from app.ingestion.extractor import extract_content
from app.graph.engine import GraphExtractorEngine
from app.models.chunk import CodeChunk
from app.models.file import RepositoryFile
from app.models.graph import GraphIndexRun
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.file_repo import FileRepository
from app.repositories.graph_repo import GraphRepository
from app.repositories.repository_repo import RepositoryRepository

logger = get_logger("pipeline")


class IngestionPipeline:
    """Full repository ingestion and indexing workflow."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_service: BaseEmbeddingService,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_service = embedding_service
        self._settings = settings

    async def run(self, repository_id: UUID) -> None:
        """Execute complete ingestion pipeline for a repository."""
        logger.info("Starting repository ingestion", repo_id=str(repository_id))
        clone_dest: Path | None = None

        async with self._session_factory() as session:
            repo_dao = RepositoryRepository(session)
            repo = await repo_dao.get_by_id_unscoped(repository_id)
            if not repo:
                logger.error("Repository not found for ingestion", repo_id=str(repository_id))
                return

            user_id = repo.user_id
            github_url = repo.github_url
            branch = repo.branch or "main"

            # Transition status -> CLONING
            await repo_dao.update_status(repository_id, "CLONING")
            await session.commit()

        try:
            # 1. Clone repository
            clone_dest = Path(self._settings.repo_clone_dir) / str(repository_id)
            await clone_repository(
                github_url=github_url,
                target_dir=clone_dest,
                branch=branch,
                github_token=self._settings.github_token,
            )
            commit_sha = await get_head_commit_sha(clone_dest) or branch

            # 2. File discovery & filtering
            async with self._session_factory() as session:
                repo_dao = RepositoryRepository(session)
                await repo_dao.update_status(repository_id, "INDEXING")
                await session.commit()

            discovered = discover_files(
                repo_root=clone_dest,
                max_file_size_bytes=self._settings.max_file_size_bytes,
            )

            if not discovered:
                logger.warning("No indexable files discovered", repo_id=str(repository_id))
                async with self._session_factory() as session:
                    file_dao = FileRepository(session)
                    repo_dao = RepositoryRepository(session)
                    await file_dao.delete_by_repository(repository_id)
                    await repo_dao.update_status(
                        repository_id,
                        status="READY",
                        file_count=0,
                        chunk_count=0,
                        languages={},
                        last_indexed_at=datetime.now(timezone.utc),
                    )
                    await session.commit()
                return

            # Load existing files for incremental hashing
            async with self._session_factory() as session:
                existing_list = await FileRepository(session).list_by_repository(repository_id)
                existing_by_path = {f.path: f for f in existing_list}

            # Compute language distribution
            lang_counts = Counter(d.language for d in discovered)
            total_files = len(discovered)
            languages_stat = {
                lang: round((count / total_files) * 100, 1)
                for lang, count in lang_counts.most_common()
            }

            # 3. Extract content and create chunks only for new or modified files
            files_with_chunks: list[tuple[RepositoryFile, list[CodeChunk]]] = []
            all_chunks_to_embed: list[CodeChunk] = []
            graph_files_payload: list[tuple[str, str, Optional[str]]] = []
            current_paths: set[str] = set()
            ids_to_delete: list[UUID] = []
            unchanged_count = 0

            for d in discovered:
                extracted = extract_content(d.absolute_path)
                if not extracted or not extracted.content.strip():
                    continue

                current_paths.add(d.relative_path)
                graph_files_payload.append(
                    (d.relative_path, extracted.content, extracted.content_hash)
                )

                existing_rec = existing_by_path.get(d.relative_path)
                if existing_rec and existing_rec.content_hash == extracted.content_hash:
                    unchanged_count += 1
                    continue

                if existing_rec:
                    ids_to_delete.append(existing_rec.id)

                file_rec = RepositoryFile(
                    repository_id=repository_id,
                    path=d.relative_path,
                    filename=d.filename,
                    language=d.language,
                    size_bytes=d.size_bytes,
                    content_hash=extracted.content_hash,
                )

                raw_chunks = chunk_text(
                    content=extracted.content,
                    chunk_size=self._settings.chunk_size,
                    chunk_overlap=self._settings.chunk_overlap,
                )

                chunk_records: list[CodeChunk] = []
                for tc in raw_chunks:
                    chunk_rec = CodeChunk(
                        repository_id=repository_id,
                        chunk_index=tc.chunk_index,
                        content=tc.content,
                        start_line=tc.start_line,
                        end_line=tc.end_line,
                        language=d.language,
                    )
                    chunk_records.append(chunk_rec)
                    all_chunks_to_embed.append(chunk_rec)

                files_with_chunks.append((file_rec, chunk_records))

            # Mark deleted files for removal
            for path, old_rec in existing_by_path.items():
                if path not in current_paths:
                    ids_to_delete.append(old_rec.id)

            # 4. Generate embeddings in batches for new/modified chunks only
            if all_chunks_to_embed:
                batch_size = 64
                chunk_contents = [c.content for c in all_chunks_to_embed]
                logger.info(
                    "Generating embeddings for new/modified chunks",
                    chunk_count=len(all_chunks_to_embed),
                    unchanged_files=unchanged_count,
                    batch_size=batch_size,
                )

                all_embeddings: list[list[float]] = []
                for i in range(0, len(chunk_contents), batch_size):
                    batch_slice = chunk_contents[i : i + batch_size]
                    batch_embeddings = await self._embedding_service.embed_texts(batch_slice)
                    all_embeddings.extend(batch_embeddings)

                for chunk_obj, emb in zip(all_chunks_to_embed, all_embeddings):
                    chunk_obj.embedding = emb

            # 5. Persist incremental changes in DB
            async with self._session_factory() as session:
                file_dao = FileRepository(session)
                chunk_dao = ChunkRepository(session)
                repo_dao = RepositoryRepository(session)

                if ids_to_delete:
                    await file_dao.delete_by_ids(ids_to_delete)

                if files_with_chunks:
                    new_file_recs = [f for f, _ in files_with_chunks]
                    session.add_all(new_file_recs)
                    await session.flush()

                    chunks_to_insert: list[CodeChunk] = []
                    for file_rec, chunk_list in files_with_chunks:
                        for c in chunk_list:
                            c.file_id = file_rec.id
                            chunks_to_insert.append(c)
                    if chunks_to_insert:
                        await chunk_dao.create_batch(chunks_to_insert)

                total_persisted_files = unchanged_count + len(files_with_chunks)
                total_persisted_chunks = await chunk_dao.count_by_repository(repository_id)

                # Transition status -> READY
                await repo_dao.update_status(
                    repository_id,
                    status="READY",
                    file_count=total_persisted_files,
                    chunk_count=total_persisted_chunks,
                    languages=languages_stat,
                    last_indexed_at=datetime.now(timezone.utc),
                )
                await session.commit()

            logger.info(
                "Repository ingestion completed successfully",
                repo_id=str(repository_id),
                files=total_persisted_files,
                chunks=total_persisted_chunks,
                unchanged_files=unchanged_count,
            )

            # 6. Sidecar: Relationship Graph Extraction (Isolated from Vector Failure)
            run_record_id: Optional[UUID] = None
            try:
                async with self._session_factory() as session:
                    graph_dao = GraphRepository(session)
                    run_record = GraphIndexRun(
                        workspace_id=user_id,
                        repository_id=repository_id,
                        commit_sha=commit_sha,
                        status="RUNNING",
                    )
                    saved_run = await graph_dao.create_index_run(run_record)
                    run_record_id = saved_run.id
                    await session.commit()

                    engine = GraphExtractorEngine()
                    nodes_payload, edges_payload, active_keys = engine.extract_repository_graph(
                        repository_id=repository_id,
                        workspace_id=user_id,
                        files=graph_files_payload,
                        commit_sha=commit_sha,
                    )

                    key_to_id, nodes_created, nodes_updated = await graph_dao.upsert_nodes_with_stats(
                        workspace_id=user_id,
                        repository_id=repository_id,
                        nodes=nodes_payload,
                    )

                    resolved_edges: list[dict[str, Any]] = []
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

                    edges_count, edges_created, edges_updated = await graph_dao.upsert_edges_with_stats(
                        workspace_id=user_id,
                        repository_id=repository_id,
                        edges=resolved_edges,
                    )

                    del_nodes, del_edges = await graph_dao.reconcile_deleted_entities(
                        workspace_id=user_id,
                        repository_id=repository_id,
                        active_stable_keys=active_keys,
                    )

                    await graph_dao.update_index_run(
                        run_id=run_record_id,
                        status="READY",
                        nodes_created=nodes_created,
                        nodes_updated=nodes_updated,
                        edges_created=edges_created,
                        edges_updated=edges_updated,
                        nodes_deleted=del_nodes,
                        edges_deleted=del_edges,
                    )
                    await session.commit()

                    logger.info(
                        "Sidecar graph indexing completed",
                        repo_id=str(repository_id),
                        nodes=len(nodes_payload),
                        edges=edges_count,
                    )
            except Exception as graph_err:
                logger.error(
                    "Sidecar graph indexing failed (non-fatal)",
                    repo_id=str(repository_id),
                    error=str(graph_err),
                )
                if run_record_id:
                    try:
                        async with self._session_factory() as session:
                            graph_dao = GraphRepository(session)
                            await graph_dao.update_index_run(
                                run_id=run_record_id,
                                status="FAILED",
                                error_summary=str(graph_err),
                            )
                            await session.commit()
                    except Exception:
                        pass

        except Exception as exc:
            err_msg = f"{type(exc).__name__}: {str(exc)}"
            tb = traceback.format_exc()
            logger.error(
                "Ingestion pipeline failed",
                repo_id=str(repository_id),
                error=err_msg,
                traceback=tb,
            )
            async with self._session_factory() as session:
                repo_dao = RepositoryRepository(session)
                await repo_dao.update_status(
                    repository_id,
                    status="FAILED",
                    error_message=err_msg,
                )
                await session.commit()

        finally:
            # Clean up cloned local files
            if clone_dest and clone_dest.exists():
                logger.info("Cleaning clone directory", path=str(clone_dest))
                force_rm_directory(clone_dest)
