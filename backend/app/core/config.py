"""
TrunkHQ — Application Configuration.

Centralizes all configuration via environment variables using pydantic-settings.
Every configurable value flows through this module. No secrets are hard-coded.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://cortex:cortex@localhost:5432/cortex"
    database_url_sync: str = "postgresql://cortex:cortex@localhost:5432/cortex"

    # ── Authentication ───────────────────────────────────────────────────────
    jwt_secret_key: str = "change-me-to-a-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440  # 24 hours

    # ── GitHub ───────────────────────────────────────────────────────────────
    github_token: Optional[str] = None

    # ── Embedding ────────────────────────────────────────────────────────────
    embedding_provider: str = "local"  # "local" | "openai" | "google"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_provider: str = "google"  # "google" | "openai" | "groq"
    llm_model: str = "gemini-2.5-flash"
    google_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    # ── RAG ──────────────────────────────────────────────────────────────────
    top_k: int = 5
    similarity_threshold: float = 0.3

    # ── Ingestion ────────────────────────────────────────────────────────────
    max_file_size_bytes: int = 1_048_576  # 1 MB
    chunk_size: int = 1500
    chunk_overlap: int = 200
    repo_clone_dir: str = "repos"  # Relative to backend working directory

    # ── JEV Decision Layer ───────────────────────────────────────────────────
    jev_enabled: bool = False

    # ── Application ──────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000"
    admin_emails: str = ""
    github_webhook_secret: Optional[str] = None
    billing_webhook_secret: Optional[str] = None
    log_level: str = "INFO"
    app_name: str = "TrunkHQ"
    app_version: str = "0.1.0"
    debug: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def admin_emails_set(self) -> set[str]:
        """Parse comma-separated admin email addresses into a lowercase set."""
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def is_jwt_secret_insecure(self) -> bool:
        """Check if JWT secret is using the default placeholder."""
        return self.jwt_secret_key == "change-me-to-a-random-secret"

    @property
    def effective_llm_api_key(self) -> Optional[str]:
        """Return the API key for the configured LLM provider."""
        provider = self.llm_provider.lower()
        if provider == "google":
            return self.google_api_key
        if provider == "openai":
            return self.openai_api_key
        if provider == "groq":
            return self.groq_api_key
        return None


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Call this instead of constructing Settings directly."""
    return Settings()
