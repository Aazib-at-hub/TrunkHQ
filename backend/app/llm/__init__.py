"""
TrunkHQ — LLM Service Factory.
"""

from functools import lru_cache

from app.core.config import get_settings
from app.llm.base import BaseLLMService
from app.llm.google_llm import GoogleLLMService
from app.llm.groq_llm import DEFAULT_GROQ_MODEL, GroqLLMService
from app.llm.openai_llm import OpenAILLMService

__all__ = [
    "BaseLLMService",
    "GoogleLLMService",
    "GroqLLMService",
    "OpenAILLMService",
    "get_llm_service",
]


@lru_cache
def get_llm_service() -> BaseLLMService:
    """Return configured LLM service singleton."""
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY required when LLM_PROVIDER=openai")
        return OpenAILLMService(
            api_key=settings.openai_api_key,
            model_name=settings.llm_model,
        )
    if provider == "groq":
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY required when LLM_PROVIDER=groq")
        model_name = (
            DEFAULT_GROQ_MODEL
            if settings.llm_model == "gemini-2.0-flash"
            else settings.llm_model
        )
        return GroqLLMService(
            api_key=settings.groq_api_key,
            model_name=model_name,
        )
    # Default to Google Gemini
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY required when LLM_PROVIDER=google")
    return GoogleLLMService(
        api_key=settings.google_api_key,
        model_name=settings.llm_model,
    )
