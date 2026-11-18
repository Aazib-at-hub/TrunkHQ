"""
TrunkHQ — JEV Decision & Reranking Service.

Reranks retrieved chunks using lexical/symbol overlap with the query combined
with vector/RRF similarity, and deduplicates overlapping line spans.
"""

from __future__ import annotations

import re
from typing import Sequence

from app.decision.base import BaseDecisionService
from app.retrieval.retriever import RetrievedChunk

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]{2,}")


class JEVDecisionService(BaseDecisionService):
    """Symbol-aware reranking and overlap deduplication decision service."""

    async def filter_and_rank(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
    ) -> Sequence[RetrievedChunk]:
        if not chunks:
            return []

        query_terms = {t.lower() for t in _TOKEN_RE.findall(query)}

        scored: list[tuple[float, RetrievedChunk]] = []
        for chunk in chunks:
            content_lower = chunk.content.lower()
            path_lower = chunk.file_path.lower()

            term_hits = sum(1 for t in query_terms if t in content_lower)
            path_hits = sum(1 for t in query_terms if t in path_lower)

            lexical_boost = (term_hits / max(len(query_terms), 1)) * 0.35
            path_boost = (path_hits / max(len(query_terms), 1)) * 0.25
            combined = chunk.similarity_score + lexical_boost + path_boost
            scored.append((combined, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)

        # Deduplicate overlapping line ranges within the same file
        deduped: list[RetrievedChunk] = []
        seen_spans: dict[str, list[tuple[int, int]]] = {}
        for _, chunk in scored:
            spans = seen_spans.setdefault(chunk.file_path, [])
            overlaps = any(
                not (chunk.end_line < s_start or chunk.start_line > s_end)
                for s_start, s_end in spans
            )
            if overlaps:
                continue
            spans.append((chunk.start_line, chunk.end_line))
            deduped.append(chunk)

        return deduped

