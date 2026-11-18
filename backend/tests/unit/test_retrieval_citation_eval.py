"""
Phase 5 evaluation suite: hybrid ranking, empty-context uncertainty,
citation accuracy, and startup stale-repository recovery.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from app.main import STALE_RECOVERY_MESSAGE, recover_stale_repositories
from app.rag.generator import RAGGenerator
from app.retrieval.retriever import RetrievedChunk, fuse_rrf


def _run_coro(coro):
    """Drive an async coroutine synchronously without spawning an event loop."""
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def _make_chunk(
    file_path: str,
    start_line: int = 1,
    end_line: int = 10,
    score: float = 0.7,
    content: str = "def fn(): pass",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        file_id=uuid.uuid4(),
        file_path=file_path,
        file_name=file_path.split("/")[-1],
        language="python",
        start_line=start_line,
        end_line=end_line,
        content=content,
        similarity_score=score,
    )


def test_hybrid_rrf_ranking_prefers_dual_source_hits() -> None:
    """Chunks matched by both vector and FTS should rank above single-source top hits."""
    shared = _make_chunk("shared.py", score=0.72)
    vec_only = _make_chunk("vec_only.py", score=0.95)
    fts_only = _make_chunk("fts_only.py", score=0.80)

    # shared appears at rank 2 in vector and rank 2 in FTS -> higher combined RRF than single rank-1
    fused = fuse_rrf([vec_only, shared], [fts_only, shared], top_k=3)
    assert [c.file_path for c in fused] == ["shared.py", "vec_only.py", "fts_only.py"]


def test_empty_context_uncertainty_skips_llm() -> None:
    """When retrieval returns no chunks, generator returns uncertainty without calling LLM."""
    llm = MagicMock()
    llm.generate_response = AsyncMock(return_value="Hallucinated answer")
    generator = RAGGenerator(llm)

    res = _run_coro(generator.generate_answer("How does billing work?", []))
    assert res.citations == []
    assert "could not find sufficient evidence" in res.answer.lower()
    llm.generate_response.assert_not_called()


def test_citation_accuracy_filters_uncited_and_out_of_range() -> None:
    """Only valid [Source #N] markers referenced in the answer become citations."""
    c1 = _make_chunk("auth/login.py", start_line=10, end_line=25)
    c2 = _make_chunk("auth/unused.py", start_line=1, end_line=5)
    c3 = _make_chunk("auth/tokens.py", start_line=30, end_line=45)

    llm = MagicMock()
    llm.generate_response = AsyncMock(
        return_value="Login delegates to [Source #1] and validates JWTs in [Source #3] (ignore [Source #99])."
    )
    generator = RAGGenerator(llm)

    res = _run_coro(generator.generate_answer("Explain login flow", [c1, c2, c3]))
    cited_paths = [c.file_path for c in res.citations]
    assert cited_paths == ["auth/login.py", "auth/tokens.py"]
    assert res.citations[0].start_line == 10
    assert res.citations[0].end_line == 25
    assert res.citations[1].start_line == 30


def test_startup_recovery_marks_stale_repositories_failed() -> None:
    """recover_stale_repositories updates in-progress repos and running graph runs."""
    mock_session = MagicMock()
    repo_res = MagicMock()
    repo_res.rowcount = 2
    graph_res = MagicMock()
    graph_res.rowcount = 1
    mock_session.execute = AsyncMock(side_effect=[repo_res, graph_res])
    mock_session.commit = AsyncMock()

    @asynccontextmanager
    async def _fake_factory():
        yield mock_session

    recovered = _run_coro(recover_stale_repositories(_fake_factory))
    assert recovered == 2
    assert mock_session.execute.await_count == 2
    mock_session.commit.assert_awaited_once()
    assert "restart" in STALE_RECOVERY_MESSAGE.lower()


def test_require_admin_enforces_admin_emails(monkeypatch) -> None:
    """require_admin allows configured admin emails and rejects non-admins with ForbiddenError."""
    import pytest
    from app.api.deps import require_admin
    from app.core.config import get_settings
    from app.core.exceptions import ForbiddenError

    monkeypatch.setenv("ADMIN_EMAILS", "admin@cortex.dev")
    get_settings.cache_clear()
    try:
        admin_id = uuid.uuid4()
        user_id = uuid.uuid4()
        admin_user = MagicMock(email="Admin@Cortex.dev")
        regular_user = MagicMock(email="dev@cortex.dev")

        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(side_effect=[admin_user, regular_user])

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.api.deps.UserRepository", lambda _db: mock_repo)
            assert _run_coro(require_admin(current_user_id=admin_id, db=MagicMock())) == admin_id
            with pytest.raises(ForbiddenError):
                _run_coro(require_admin(current_user_id=user_id, db=MagicMock()))
    finally:
        get_settings.cache_clear()
