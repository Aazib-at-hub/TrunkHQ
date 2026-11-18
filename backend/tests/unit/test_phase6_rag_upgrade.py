"""
Unit tests for Phase 6 RAG & AI Chat Upgrade:
- Symmetric encryption for BYOK/OAuth secrets
- Randomized prompt-injection boundary tags & project doc context
- Sanitized LLM error responses (no raw provider trace leaks)
- SSE chat/stream route registration
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.router import api_router
from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.core.exceptions import InternalServerError
from app.llm.google_llm import GoogleLLMService
from app.llm.openai_llm import OpenAILLMService
from app.rag.prompt import build_user_prompt


def _run_coro(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_crypto_roundtrip_and_masking() -> None:
    raw_key = "sk-proj-secret1234567890"
    encrypted = encrypt_secret(raw_key)
    assert encrypted != raw_key
    assert decrypt_secret(encrypted) == raw_key
    assert mask_secret(raw_key) == "sk-p...7890"
    assert mask_secret("short") == "****"


def test_prompt_uses_randomized_boundary_tags_and_doc_context() -> None:
    p1 = build_user_prompt("How does auth work?", [], document_context="SRS: JWT RS256")
    p2 = build_user_prompt("How does auth work?", [], document_context="SRS: JWT RS256")
    assert "<untrusted_context_" in p1
    assert "PROJECT DOCUMENTATION CONTEXT" in p1
    assert "SRS: JWT RS256" in p1
    assert p1 != p2  # Randomized nonce per call prevents static delimiter breakout


def test_llm_errors_do_not_leak_raw_exceptions() -> None:
    google_svc = GoogleLLMService(api_key="AIzaSyFakeKey", model_name="gemini-2.0-flash")
    openai_svc = OpenAILLMService(api_key="sk-fake", model_name="gpt-4o-mini")

    async def _run() -> None:
        with patch.object(google_svc, "_sync_generate", side_effect=RuntimeError("RAW_SECRET_TRACE")):
            with pytest.raises(InternalServerError) as exc_info:
                await google_svc.generate_response("sys", "usr")
            assert "RAW_SECRET_TRACE" not in exc_info.value.message

        fake_client = MagicMock()
        fake_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("RAW_OPENAI_TRACE"))
        with patch.object(openai_svc, "_get_client", return_value=fake_client):
            with pytest.raises(InternalServerError) as exc_info2:
                await openai_svc.generate_response("sys", "usr")
            assert "RAW_OPENAI_TRACE" not in exc_info2.value.message

    _run_coro(_run())


def test_chat_stream_route_registered() -> None:
    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/api/v1/repositories/{repo_id}/chat/stream" in paths
