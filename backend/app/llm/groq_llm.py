"""
TrunkHQ — Groq LLM Service.

Integrates with Groq's OpenAI-compatible Chat Completions API
(e.g. llama-3.3-70b-versatile, llama-3.1-8b-instant, mixtral-8x7b-32768).
"""

from __future__ import annotations

import httpx

from app.core.exceptions import InternalServerError
from app.core.logging import get_logger
from app.llm.base import BaseLLMService

logger = get_logger("groq_llm")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


class GroqLLMService(BaseLLMService):
    """Groq generation service via OpenAI-compatible HTTP endpoint."""

    def __init__(
        self,
        api_key: str,
        model_name: str = DEFAULT_GROQ_MODEL,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        payload = {
            "model": self._model_name,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    GROQ_API_URL,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                choices = data.get("choices") or []
                if not choices:
                    return ""
                return (choices[0].get("message") or {}).get("content") or ""
        except Exception as exc:
            logger.error("Groq chat completion failed", error=str(exc))
            raise InternalServerError(
                "LLM generation failed due to an upstream provider error."
            ) from exc
