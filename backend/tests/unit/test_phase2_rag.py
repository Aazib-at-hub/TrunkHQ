"""
Unit tests for Phase 2 backend upgrades:
- Hybrid RRF fusion (vector + full-text)
- JEVDecisionService reranking and overlap deduplication
- Prompt history & token budget enforcement
- RAGGenerator empty-context uncertainty & grounded citation filtering
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

from app.decision.jev_decision import JEVDecisionService
from app.rag.generator import RAGGenerator
from app.rag.prompt import build_user_prompt
from app.retrieval.retriever import RetrievedChunk, fuse_rrf


def _run_coro(coro):
    """Drive an async coroutine synchronously without spawning an event loop."""
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def _chunk(
    path: str,
    content: str = "def fn(): pass",
    start_line: int = 1,
    end_line: int = 10,
    score: float = 0.7,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        file_id=uuid.uuid4(),
        file_path=path,
        file_name=path.split("/")[-1],
        language="python",
        content=content,
        start_line=start_line,
        end_line=end_line,
        similarity_score=score,
    )


def test_fuse_rrf_prioritizes_overlap_and_caps_top_k() -> None:
    c1 = _chunk("a.py")
    c2 = _chunk("b.py")
    c3 = _chunk("c.py")

    # c2 appears in both vector (rank 2) and fts (rank 1) -> highest RRF score
    fused = fuse_rrf([c1, c2], [c2, c3], top_k=2)
    assert [c.chunk_id for c in fused] == [c2.chunk_id, c1.chunk_id]


def test_jev_decision_reranks_and_deduplicates_overlapping_spans() -> None:
    c_generic = _chunk("utils.py", "helper = 1", start_line=1, end_line=10, score=0.75)
    c_exact = _chunk("auth_service.py", "def validate_token(): return True", start_line=1, end_line=15, score=0.70)
    c_overlap = _chunk("auth_service.py", "validate_token overlap", start_line=10, end_line=25, score=0.65)

    service = JEVDecisionService()
    ranked = _run_coro(service.filter_and_rank("validate_token", [c_generic, c_overlap, c_exact]))

    assert ranked[0].chunk_id == c_exact.chunk_id
    # c_overlap overlaps lines 1..15 in auth_service.py, so it should be deduplicated
    assert all(c.chunk_id != c_overlap.chunk_id for c in ranked)


def test_build_user_prompt_includes_history_and_enforces_budget() -> None:
    c1 = _chunk("one.py", "x" * 200)
    c2 = _chunk("two.py", "y" * 200)

    prompt = build_user_prompt(
        question="Follow up?",
        chunks=[c1, c2],
        history=[("user", "Initial question"), ("assistant", "Initial answer")],
        max_context_chars=260,
    )
    assert "CONVERSATION HISTORY:" in prompt
    assert "USER: Initial question" in prompt
    assert "one.py" in prompt
    assert "two.py" not in prompt


def test_rag_generator_uncertainty_and_grounded_citations() -> None:
    llm = MagicMock()
    llm.generate_response = AsyncMock(return_value="Explained using [Source #2] in target.py.")
    generator = RAGGenerator(llm)

    # Empty retrieval should not call LLM
    empty_res = _run_coro(generator.generate_answer("What is this?", []))
    assert empty_res.citations == []
    assert "could not find sufficient evidence" in empty_res.answer.lower()
    llm.generate_response.assert_not_called()

    # Grounded citations should filter to referenced chunk
    c1 = _chunk("unused.py")
    c2 = _chunk("target.py")
    res = _run_coro(generator.generate_answer("Explain target", [c1, c2]))
    assert len(res.citations) == 1
    assert res.citations[0].file_path == "target.py"


def test_extract_query_entities() -> None:
    from app.services.chat_service import extract_query_entities

    q = "How does `GraphRepository.search_nodes` work in app/services/chat_service.py?"
    entities = extract_query_entities(q)
    assert "GraphRepository.search_nodes" in entities
    assert "search_nodes" in entities
    assert "app/services/chat_service.py" in entities
    assert "does" not in [e.lower() for e in entities]
    assert "work" not in [e.lower() for e in entities]

