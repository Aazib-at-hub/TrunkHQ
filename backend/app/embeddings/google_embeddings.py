"""
TrunkHQ — Google Gemini Embedding Service.

Uses Google's Gemini REST Embeddings API (`batchEmbedContents`) via httpx.
Requires zero local ML memory (ideal for 512MB cloud containers like Render Free tier)
and supports Matryoshka `outputDimensionality` (default 384) to match existing pgvector schemas.
"""

from __future__ import annotations

import httpx

from app.core.exceptions import InternalServerError
from app.core.logging import get_logger
from app.embeddings.base import BaseEmbeddingService

logger = get_logger("google_embeddings")

DEFAULT_GOOGLE_EMBEDDING_MODEL = "gemini-embedding-001"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
_MAX_BATCH_SIZE = 100


class GoogleEmbeddingService(BaseEmbeddingService):
    """Google Gemini API embedding provider (HTTP-only, low memory)."""

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

    async def _batch_embed(
        self,
        texts: list[str],
        task_type: str,
    ) -> list[list[float]]:
        if not texts:
            return []

        url = f"{GEMINI_API_BASE}/models/{self._model_name}:batchEmbedContents"
        all_vectors: list[list[float]] = []

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                for start in range(0, len(texts), _MAX_BATCH_SIZE):
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
                    response = await client.post(
                        url,
                        params={"key": self._api_key},
                        json={"requests": requests_payload},
                    )
                    response.raise_for_status()
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
