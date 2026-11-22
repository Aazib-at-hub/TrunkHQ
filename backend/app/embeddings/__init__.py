"""
TrunkHQ — Embedding Service Factory.
"""

from functools import lru_cache

from app.core.config import get_settings
from app.embeddings.base import BaseEmbeddingService
from app.embeddings.google_embeddings import (
    DEFAULT_GOOGLE_EMBEDDING_MODEL,
    GoogleEmbeddingService,
)
from app.embeddings.local_embeddings import LocalEmbeddingService
from app.embeddings.openai_embeddings import OpenAIEmbeddingService

__all__ = [
    "BaseEmbeddingService",
    "DEFAULT_GOOGLE_EMBEDDING_MODEL",
    "GoogleEmbeddingService",
    "LocalEmbeddingService",
    "OpenAIEmbeddingService",
    "get_embedding_service",
]


@lru_cache
def get_embedding_service() -> BaseEmbeddingService:
    """Return configured embedding service singleton."""
    settings = get_settings()
    provider = settings.embedding_provider.lower()
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY required when EMBEDDING_PROVIDER=openai")
        return OpenAIEmbeddingService(
            api_key=settings.openai_api_key,
            model_name=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )
    if provider == "google":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY required when EMBEDDING_PROVIDER=google")
        model_name = (
            DEFAULT_GOOGLE_EMBEDDING_MODEL
            if settings.embedding_model == "all-MiniLM-L6-v2"
            else settings.embedding_model
        )
        return GoogleEmbeddingService(
            api_key=settings.google_api_key,
            model_name=model_name,
            dimension=settings.embedding_dimension,
        )
    return LocalEmbeddingService(
        model_name=settings.embedding_model,
        dimension=settings.embedding_dimension,
    )
