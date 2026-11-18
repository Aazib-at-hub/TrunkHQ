"""
TrunkHQ — FastAPI Application Factory.

Creates and configures the FastAPI application with:
- CORS middleware
- Structured exception handlers
- API router mounting
- Startup/shutdown lifecycle events
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import update

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import CortexError
from app.core.logging import get_logger, setup_logging
from app.database.session import async_session_factory
from app.models.graph import GraphIndexRun
from app.models.repository import Repository

logger = get_logger(__name__)

STALE_RECOVERY_MESSAGE = "Indexing interrupted by server restart. Please re-index this repository."


async def recover_stale_repositories(session_factory: Any = async_session_factory) -> int:
    """Mark repositories and graph runs stuck in in-progress states after an unexpected restart as FAILED."""
    async with session_factory() as session:
        repo_res = await session.execute(
            update(Repository)
            .where(Repository.status.in_(["PENDING", "CLONING", "INDEXING"]))
            .values(
                status="FAILED",
                error_message=STALE_RECOVERY_MESSAGE,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.execute(
            update(GraphIndexRun)
            .where(GraphIndexRun.status == "RUNNING")
            .values(
                status="FAILED",
                error_summary="Graph indexing interrupted by server restart.",
                completed_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
        return getattr(repo_res, "rowcount", 0) or 0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager — runs on startup and shutdown."""
    settings = get_settings()
    setup_logging(settings.log_level)
    if settings.is_jwt_secret_insecure:
        if not settings.debug:
            logger.critical(
                "SECURITY HAZARD: JWT_SECRET_KEY is using insecure default 'change-me-to-a-random-secret'. "
                "Must be configured with a high-entropy secret in production."
            )
            raise RuntimeError(
                "Refusing to start in non-debug mode with insecure default JWT_SECRET_KEY."
            )
        else:
            logger.warning(
                "SECURITY NOTICE: Running in debug mode with default JWT_SECRET_KEY."
            )

    logger.info(
        "cortex_starting",
        version=settings.app_version,
        embedding_provider=settings.embedding_provider,
        llm_provider=settings.llm_provider,
        jev_enabled=settings.jev_enabled,
    )
    try:
        recovered = await recover_stale_repositories()
        if recovered:
            logger.warning("recovered_stale_repositories", count=recovered)
    except Exception as exc:
        logger.warning("startup_recovery_skipped", error=str(exc))

    yield
    logger.info("cortex_shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-Powered Codebase Intelligence Platform",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── Rate Limiting (slowapi) ───────────────────────────────────────────
    limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    # ── CORS Middleware ──────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Security Headers & Correlation ID Middleware ─────────────────────
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or uuid4().hex
        response = await call_next(request)
        response.headers.setdefault("X-Request-Id", request_id)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    # ── Exception Handlers ───────────────────────────────────────────────

    @app.exception_handler(CortexError)
    async def cortex_exception_handler(request: Request, exc: CortexError) -> JSONResponse:
        """Handle all domain exceptions with consistent error format."""
        logger.warning(
            "cortex_error",
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for unhandled exceptions. Never expose stack traces to clients."""
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred. Please try again later.",
                    "details": None,
                }
            },
        )

    # ── Routes ───────────────────────────────────────────────────────────
    app.include_router(api_router)

    return app


# Application instance — used by uvicorn
app = create_app()
