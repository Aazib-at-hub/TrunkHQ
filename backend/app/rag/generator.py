"""
TrunkHQ — RAG Answer Generator.

Connects vector retrieval, prompt compilation, LLM inference, and source attribution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence
from uuid import UUID

from app.core.logging import get_logger
from app.llm.base import BaseLLMService
from app.rag.prompt import SYSTEM_PROMPT, build_user_prompt
from app.retrieval.retriever import RetrievedChunk

logger = get_logger("rag_generator")


@dataclass(frozen=True)
class GeneratedCitation:
    """Citation metadata for chunks included in LLM context."""

    chunk_id: UUID
    file_path: str
    start_line: int
    end_line: int
    similarity_score: float


@dataclass(frozen=True)
class RAGResult:
    """Answer text bundled with cited sources."""

    answer: str
    citations: list[GeneratedCitation]


class RAGGenerator:
    """Orchestrates generation of grounded answers with source citations."""

    def __init__(self, llm_service: BaseLLMService) -> None:
        self._llm = llm_service

    async def generate_answer(
        self,
        question: str,
        retrieved_chunks: Sequence[RetrievedChunk],
        temperature: float = 0.2,
        graph_context: Optional[str] = None,
        history: Optional[Sequence[tuple[str, str]]] = None,
        document_context: Optional[str] = None,
    ) -> RAGResult:
        """
        Build prompt from context chunks, project docs, graph relationships, and history;
        generate grounded response from LLM, and return with verified citations.
        """
        if (
            not retrieved_chunks
            and not (graph_context and graph_context.strip())
            and not (document_context and document_context.strip())
        ):
            return RAGResult(
                answer=(
                    "I could not find sufficient evidence in the indexed repository to answer "
                    "this question reliably. Try mentioning specific file names, symbols, or "
                    "re-indexing the repository if the code was recently added."
                ),
                citations=[],
            )

        user_prompt = build_user_prompt(
            question,
            retrieved_chunks,
            graph_context=graph_context,
            history=history,
            document_context=document_context,
        )

        logger.info(
            "Generating RAG answer",
            question_len=len(question),
            context_chunks=len(retrieved_chunks),
            has_graph_context=bool(graph_context),
            history_turns=len(history) if history else 0,
        )

        answer_text = await self._llm.generate_response(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=temperature,
        )

        # Record only chunks referenced in the answer (by Source #idx or file_path),
        # falling back to all retrieved chunks if no explicit reference pattern appears.
        referenced_indices = {
            int(m) for m in re.findall(r"\[Source\s*#(\d+)", answer_text, flags=re.IGNORECASE)
        }
        grounded_chunks = [
            c
            for idx, c in enumerate(retrieved_chunks, start=1)
            if idx in referenced_indices or c.file_path in answer_text
        ]
        if not grounded_chunks:
            grounded_chunks = list(retrieved_chunks)

        citations = [
            GeneratedCitation(
                chunk_id=c.chunk_id,
                file_path=c.file_path,
                start_line=c.start_line,
                end_line=c.end_line,
                similarity_score=c.similarity_score,
            )
            for c in grounded_chunks
        ]

        return RAGResult(answer=answer_text, citations=citations)
