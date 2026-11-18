"""
TrunkHQ — Google Gemini LLM Service.

Integrates with Google Generative AI (Gemini 2.0 Flash / Gemini 1.5 Flash).
"""

from __future__ import annotations

import asyncio
import threading
from typing import Optional

from app.core.exceptions import InternalServerError
from app.core.logging import get_logger
from app.llm.base import BaseLLMService

logger = get_logger("google_llm")

_genai_lock = threading.Lock()
_configured_api_key: Optional[str] = None


class GoogleLLMService(BaseLLMService):
    """Google Gemini generation service."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash") -> None:
        self._api_key = api_key
        self._model_name = model_name

    def _ensure_configured(self) -> None:
        global _configured_api_key
        if _configured_api_key == self._api_key:
            return
        with _genai_lock:
            if _configured_api_key != self._api_key:
                import google.generativeai as genai

                genai.configure(api_key=self._api_key)
                _configured_api_key = self._api_key

    def _sync_generate(self, system_prompt: str, user_prompt: str, temperature: float) -> str:
        import google.generativeai as genai

        self._ensure_configured()
        model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
            ),
        )
        response = model.generate_content(user_prompt)

        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            raise RuntimeError("Gemini returned no candidate responses.")

        parts = getattr(candidates[0].content, "parts", None) or []
        text_chunks = [getattr(p, "text", "") for p in parts if getattr(p, "text", None)]
        if not text_chunks:
            finish_reason = getattr(candidates[0], "finish_reason", "unknown")
            raise RuntimeError(f"Gemini returned empty/blocked content (finish_reason={finish_reason}).")
        return "".join(text_chunks)

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        try:
            return await asyncio.to_thread(
                self._sync_generate, system_prompt, user_prompt, temperature
            )
        except Exception as exc:
            logger.error("Gemini API generation failed", error=str(exc))
            raise InternalServerError(
                "LLM generation failed due to an upstream provider error."
            ) from exc
