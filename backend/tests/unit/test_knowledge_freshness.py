"""
Unit tests for Delta Knowledge Freshness (push commit diff + incremental chunks/graph).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.ingestion.delta_sync import apply_delta_update, extract_push_diff


def _run_coro(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_extract_push_diff_handles_added_modified_removed_and_unsafe_paths() -> None:
    payload = {
        "after": "abc123def456",
        "commits": [
            {
                "added": ["src/new.py", "../etc/passwd"],
                "modified": ["src/app.py"],
                "removed": ["src/old.py"],
            },
            {
                "added": ["src/old.py"],  # Re-added in later commit
                "modified": [],
                "removed": ["src/new.py"],  # Removed in later commit
            },
        ],
    }

    after_sha, changed, removed = extract_push_diff(payload)
    assert after_sha == "abc123def456"
    assert changed == {"src/app.py", "src/old.py"}
    assert removed == {"src/new.py"}


def test_apply_delta_update_only_processes_changed_files() -> None:
    repo_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one=MagicMock(return_value=1))
    )
    mock_session.commit = AsyncMock()

    old_file_id = uuid.uuid4()
    existing_files = [
        SimpleNamespace(id=old_file_id, path="app/auth.py"),
        SimpleNamespace(id=uuid.uuid4(), path="app/unchanged.py"),
    ]

    async def _run() -> None:
        with patch("app.ingestion.delta_sync.FileRepository") as mock_file_cls, patch(
            "app.ingestion.delta_sync.GraphRepository"
        ) as mock_graph_cls, patch(
            "app.ingestion.delta_sync.RepositoryRepository"
        ) as mock_repo_cls, patch(
            "app.ingestion.delta_sync.get_embedding_service"
        ) as mock_emb_fn:
            file_dao = mock_file_cls.return_value
            file_dao.list_by_repository = AsyncMock(return_value=existing_files)
            file_dao.delete_by_ids = AsyncMock(return_value=1)
            file_dao.save_files_and_chunks = AsyncMock()

            graph_dao = mock_graph_cls.return_value
            graph_dao.upsert_nodes = AsyncMock(return_value={})
            graph_dao.upsert_edges = AsyncMock(return_value=0)

            repo_dao = mock_repo_cls.return_value
            repo_dao.update_status = AsyncMock()
            repo_dao.get_by_id_unscoped = AsyncMock(return_value=SimpleNamespace())

            emb_svc = mock_emb_fn.return_value
            emb_svc.embed_texts = AsyncMock(return_value=[[0.1] * 384])

            files_updated, chunks_updated = await apply_delta_update(
                session=mock_session,
                repository_id=repo_id,
                owner_user_id=owner_id,
                after_sha="sha999",
                fetched_files={"app/auth.py": "def login():\n    return True\n"},
                removed_paths=set(),
            )
            assert files_updated == 1
            assert chunks_updated == 1
            file_dao.delete_by_ids.assert_awaited_once_with([old_file_id])

    _run_coro(_run())
