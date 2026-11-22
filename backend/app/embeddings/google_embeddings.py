"""
TrunkHQ — Google Gemini Embedding Service.

Uses Google's Gemini REST Embeddings API (`batchEmbedContents`) via httpx.
Requires zero local ML memory (ideal for 512MB cloud containers like Render Free tier)
and supports Matryoshka `outputDimensionality` (default 384) to match existing pgvector schemas.
"""

from __future__ import annotations

import asyncio

import httpx

from app.core.exceptions import InternalServerError
from app.core.logging import get_logger
from app.embeddings.base import BaseEmbeddingService

logger = get_logger("google_embeddings")

DEFAULT_GOOGLE_EMBEDDING_MODEL = "gemini-embedding-001"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
_MAX_BATCH_SIZE = 50
_MAX_RETRIES = 6
_BASE_RETRY_DELAY = 2.0
_INTER_BATCH_DELAY = 0.5


class GoogleEmbeddingService(BaseEmbeddingService):
    """Google Gemini API embedding provider (HTTP-only, low memory, rate-limit aware)."""

    def __init__(
        self,
        api_key: str,
        model_name: str = DEFAULT_GOOGLE_EMBEDDING_MODEL,
        dimension: int = 384,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name.removeprefix("models/")
        self._dimension = dimension
        self._timeout_seconds = timeout_seconds

    @property
    def dimension(self) -> int:
        return self._dimension

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        payload: dict,
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code not in (429, 500, 502, 503, 504):
                response.raise_for_status()
                return response

            if attempt >= _MAX_RETRIES:
                response.raise_for_status()

            retry_after = response.headers.get("retry-after")
            try:
                delay = float(retry_after) if retry_after else _BASE_RETRY_DELAY * (2**attempt)
            except ValueError:
                delay = _BASE_RETRY_DELAY * (2**attempt)
            delay = min(delay, 60.0)
            logger.warning(
                "Google Gemini embedding rate-limited; retrying",
                status_code=response.status_code,
                attempt=attempt + 1,
                delay_seconds=delay,
            )
            await asyncio.sleep(delay)

        if last_exc:
            raise last_exc
        raise RuntimeError("Exceeded max retries for Google Gemini embeddings")

    async def _batch_embed(
        self,
        texts: list[str],
        task_type: str,
    ) -> list[list[float]]:
        if not texts:
            return []

        url = f"{GEMINI_API_BASE}/models/{self._model_name}:batchEmbedContents"
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        all_vectors: list[list[float]] = []

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                total_batches = (len(texts) + _MAX_BATCH_SIZE - 1) // _MAX_BATCH_SIZE
                for batch_idx, start in enumerate(range(0, len(texts), _MAX_BATCH_SIZE)):
                    if batch_idx > 0 and total_batches > 1:
                        await asyncio.sleep(_INTER_BATCH_DELAY)
                    chunk = texts[start : start + _MAX_BATCH_SIZE]
                    requests_payload = [
                        {
                            "model": f"models/{self._model_name}",
                            "content": {"parts": [{"text": text or " "}]},
                            "taskType": task_type,
                            "outputDimensionality": self._dimension,
                        }
                        for text in chunk
                    ]
                    response = await self._post_with_retry(
                        client,
                        url,
                        headers,
                        {"requests": requests_payload},
                    )
                    data = response.json()
                    embeddings = data.get("embeddings") or []
                    if len(embeddings) != len(chunk):
                        raise ValueError(
                            f"Expected {len(chunk)} embeddings, got {len(embeddings)}"
                        )
                    for item in embeddings:
                        all_vectors.append(item["values"])
            return all_vectors
        except Exception as exc:
            logger.error("Google Gemini embedding failed", error=str(exc))
            raise InternalServerError(
                "Embedding generation failed due to an upstream provider error."
            ) from exc

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return await self._batch_embed(texts, task_type="RETRIEVAL_DOCUMENT")

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self._batch_embed([query], task_type="RETRIEVAL_QUERY")
        return vectors[0]
