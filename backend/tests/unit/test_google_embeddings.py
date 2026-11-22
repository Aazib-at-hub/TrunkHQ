"""
Unit tests for Google Gemini HTTP Embedding Service (low-memory cloud provider).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.core.exceptions import InternalServerError
from app.embeddings import (
    DEFAULT_GOOGLE_EMBEDDING_MODEL,
    GoogleEmbeddingService,
    get_embedding_service,
)


def _run_coro(coro):
    """Drive an async coroutine without spawning a sandbox-blocked event loop."""
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_get_embedding_service_returns_google_with_default_model() -> None:
    get_embedding_service.cache_clear()
    fake_settings = Settings(
        embedding_provider="google",
        embedding_model="all-MiniLM-L6-v2",
        embedding_dimension=384,
        google_api_key="AIza_test_key",
    )
    with patch("app.embeddings.get_settings", return_value=fake_settings):
        svc = get_embedding_service()
    assert isinstance(svc, GoogleEmbeddingService)
    assert svc._model_name == DEFAULT_GOOGLE_EMBEDDING_MODEL
    assert svc.dimension == 384
    get_embedding_service.cache_clear()


def test_get_embedding_service_google_missing_key_raises() -> None:
    get_embedding_service.cache_clear()
    fake_settings = Settings(embedding_provider="google", google_api_key=None)
    with patch("app.embeddings.get_settings", return_value=fake_settings):
        with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
            get_embedding_service()
    get_embedding_service.cache_clear()


def test_google_embeddings_embed_texts_and_query_success() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "embeddings": [
            {"values": [0.1, 0.2, 0.3]},
            {"values": [0.4, 0.5, 0.6]},
        ]
    }

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    svc = GoogleEmbeddingService(api_key="AIza_test", dimension=3)
    with patch("app.embeddings.google_embeddings.httpx.AsyncClient", return_value=mock_client):
        vectors = _run_coro(svc.embed_texts(["hello", "world"]))

    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    call_kwargs = mock_client.post.call_args.kwargs
    assert call_kwargs["headers"]["x-goog-api-key"] == "AIza_test"
    assert "params" not in call_kwargs
    assert call_kwargs["json"]["requests"][0]["outputDimensionality"] == 3
    assert call_kwargs["json"]["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT"


def test_google_embeddings_retries_on_429() -> None:
    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.headers = {"retry-after": "0.01"}

    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.headers = {}
    ok_resp.raise_for_status = MagicMock()
    ok_resp.json.return_value = {"embeddings": [{"values": [0.9, 0.8, 0.7]}]}

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=[rate_limited, ok_resp])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    svc = GoogleEmbeddingService(api_key="AIza_test", dimension=3)
    with (
        patch("app.embeddings.google_embeddings.httpx.AsyncClient", return_value=mock_client),
        patch("app.embeddings.google_embeddings.asyncio.sleep", new_callable=AsyncMock) as sleep_mock,
    ):
        vector = _run_coro(svc.embed_query("test retry"))

    assert vector == [0.9, 0.8, 0.7]
    assert mock_client.post.await_count == 2
    sleep_mock.assert_awaited_once()


def test_google_embeddings_error_wraps_internal_error() -> None:
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=RuntimeError("boom"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    svc = GoogleEmbeddingService(api_key="AIza_test", dimension=384)
    with patch("app.embeddings.google_embeddings.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(InternalServerError):
            _run_coro(svc.embed_query("test query"))
