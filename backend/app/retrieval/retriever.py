"""
TrunkHQ — Vector Retrieval Service.

Performs semantic search against pgvector embeddings scoped strictly to a repository,
returning top-K relevant code chunks with similarity scores and source file paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.logging import get_logger
from app.embeddings.base import BaseEmbeddingService
from app.models.chunk import CodeChunk
from app.models.file import RepositoryFile

logger = get_logger("retriever")


@dataclass(frozen=True)
class RetrievedChunk:
    """Retrieved chunk along with similarity score and file path information."""

    chunk_id: UUID
    file_id: UUID
    file_path: str
    file_name: str
    language: str
    content: str
    start_line: int
    end_line: int
    similarity_score: float


def fuse_rrf(
    vector_chunks: Sequence[RetrievedChunk],
    fts_chunks: Sequence[RetrievedChunk],
    k: int = 60,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Fuse vector and full-text results using Reciprocal Rank Fusion (RRF)."""
    scores: dict[UUID, float] = {}
    by_id: dict[UUID, RetrievedChunk] = {}

    for rank, chunk in enumerate(vector_chunks, start=1):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank)
        by_id[chunk.chunk_id] = chunk

    for rank, chunk in enumerate(fts_chunks, start=1):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank)
        if chunk.chunk_id not in by_id:
            by_id[chunk.chunk_id] = chunk

    ranked_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
    return [by_id[cid] for cid in ranked_ids[:top_k]]


class RetrieverService:
    """Executes hybrid (vector + full-text) search over repository code chunks."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: BaseEmbeddingService,
    ) -> None:
        self._session = session
        self._embedding_service = embedding_service

    async def _vector_search(
        self,
        repository_id: UUID,
        query: str,
        limit: int,
        similarity_threshold: float,
    ) -> list[RetrievedChunk]:
        query_vector = await self._embedding_service.embed_query(query)
        cosine_dist = CodeChunk.embedding.cosine_distance(query_vector)
        stmt = (
            select(CodeChunk, cosine_dist.label("distance"))
            .options(joinedload(CodeChunk.file))
            .where(CodeChunk.repository_id == repository_id)
            .where(CodeChunk.embedding.is_not(None))
            .order_by(cosine_dist.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        chunks: list[RetrievedChunk] = []
        for chunk, dist in rows:
            score = max(0.0, 1.0 - float(dist)) if dist is not None else 0.0
            if score < similarity_threshold:
                continue
            file_obj: RepositoryFile = chunk.file
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    file_id=chunk.file_id,
                    file_path=file_obj.path if file_obj else "unknown",
                    file_name=file_obj.filename if file_obj else "unknown",
                    language=chunk.language or "plaintext",
                    content=chunk.content,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    similarity_score=round(score, 4),
                )
            )
        return chunks

    async def _fts_search(
        self,
        repository_id: UUID,
        query: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        if not query.strip():
            return []
        try:
            ts_vec = func.to_tsvector("simple", CodeChunk.content)
            ts_query = func.websearch_to_tsquery("simple", query)
            rank_expr = func.ts_rank_cd(ts_vec, ts_query)
            stmt = (
                select(CodeChunk, rank_expr.label("fts_rank"))
                .options(joinedload(CodeChunk.file))
                .where(CodeChunk.repository_id == repository_id)
                .where(ts_vec.op("@@")(ts_query))
                .order_by(rank_expr.desc())
                .limit(limit)
            )
            result = await self._session.execute(stmt)
            rows = result.all()
            chunks: list[RetrievedChunk] = []
            for chunk, fts_rank in rows:
                file_obj: RepositoryFile = chunk.file
                chunks.append(
                    RetrievedChunk(
                        chunk_id=chunk.id,
                        file_id=chunk.file_id,
                        file_path=file_obj.path if file_obj else "unknown",
                        file_name=file_obj.filename if file_obj else "unknown",
                        language=chunk.language or "plaintext",
                        content=chunk.content,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        similarity_score=round(min(1.0, float(fts_rank or 0.0)), 4),
                    )
                )
            return chunks
        except Exception as exc:
            logger.warning("Full-text search fallback to vector-only", error=str(exc))
            return []

    async def retrieve(
        self,
        repository_id: UUID,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> list[RetrievedChunk]:
        """
        Run hybrid retrieval (pgvector cosine + PostgreSQL FTS) fused with RRF.
        """
        candidate_limit = top_k * 3
        vector_chunks = await self._vector_search(
            repository_id, query, candidate_limit, similarity_threshold
        )
        fts_chunks = await self._fts_search(repository_id, query, candidate_limit)

        retrieved = fuse_rrf(vector_chunks, fts_chunks, top_k=top_k)

        logger.info(
            "Retrieved chunks for query",
            repo_id=str(repository_id),
            vector_count=len(vector_chunks),
            fts_count=len(fts_chunks),
            fused_count=len(retrieved),
            top_score=retrieved[0].similarity_score if retrieved else 0.0,
        )
        return retrieved
