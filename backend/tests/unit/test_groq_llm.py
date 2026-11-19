"""
Unit tests for Groq LLM provider integration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.core.exceptions import InternalServerError
from app.llm import DEFAULT_GROQ_MODEL, GroqLLMService, get_llm_service


def _run_coro(coro):
    """Drive an async coroutine without spawning a sandbox-blocked event loop."""
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_settings_effective_llm_api_key_for_groq() -> None:
    s = Settings(llm_provider="groq", groq_api_key="gsk_test_key")
    assert s.effective_llm_api_key == "gsk_test_key"


def test_get_llm_service_returns_groq_with_default_model() -> None:
    get_llm_service.cache_clear()
    fake_settings = Settings(
        llm_provider="groq",
        llm_model="gemini-2.0-flash",
        groq_api_key="gsk_test_key",
    )
    with patch("app.llm.get_settings", return_value=fake_settings):
        svc = get_llm_service()
    assert isinstance(svc, GroqLLMService)
    assert svc._model_name == DEFAULT_GROQ_MODEL
    get_llm_service.cache_clear()


def test_get_llm_service_groq_missing_key_raises() -> None:
    get_llm_service.cache_clear()
    fake_settings = Settings(llm_provider="groq", groq_api_key=None)
    with patch("app.llm.get_settings", return_value=fake_settings):
        with pytest.raises(ValueError, match="GROQ_API_KEY"):
            get_llm_service()
    get_llm_service.cache_clear()


def test_groq_llm_generate_response_success() -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Hello from Groq"}}]
    }

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    svc = GroqLLMService(api_key="gsk_test_key", model_name="llama-3.3-70b-versatile")
    with patch("app.llm.groq_llm.httpx.AsyncClient", return_value=mock_client):
        result = _run_coro(svc.generate_response("sys", "usr", temperature=0.1))

    assert result == "Hello from Groq"
    mock_client.post.assert_awaited_once()
    call_kwargs = mock_client.post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer gsk_test_key"
    assert call_kwargs["json"]["model"] == "llama-3.3-70b-versatile"


def test_groq_llm_generate_response_error_wraps_internal_error() -> None:
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=RuntimeError("network down"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    svc = GroqLLMService(api_key="gsk_test_key")
    with patch("app.llm.groq_llm.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(InternalServerError):
            _run_coro(svc.generate_response("sys", "usr"))
