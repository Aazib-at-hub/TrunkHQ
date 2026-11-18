"""
Regression tests for production-readiness security & isolation fixes.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.responses import JSONResponse

from app.api.deps import TenantContext
from app.api.v1.health import liveness_check
from app.core.exceptions import ForbiddenError
from app.main import create_app, lifespan
from app.repositories.graph_repo import GraphRepository


def _run_coro(coro):
    """Drive an async coroutine without spawning a sandbox-blocked event loop."""
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_reindex_graph_rejects_non_owner() -> None:
    """Non-owners must receive ForbiddenError when attempting to reindex a repo graph."""
    from app.api.v1.graph import reindex_graph

    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    fake_repo = SimpleNamespace(id=repo_id, user_id=owner_id)
    mock_db = AsyncMock()

    async def _run() -> None:
        tenant = TenantContext(
            user_id=other_user_id,
            organization_id=uuid.uuid4(),
            role="developer",
        )
        with patch("app.api.v1.graph._verify_repo_access", new=AsyncMock(return_value=fake_repo)):
            with pytest.raises(ForbiddenError):
                await reindex_graph(repo_id=repo_id, tenant=tenant, db=mock_db)

    _run_coro(_run())


def test_graph_repo_rejects_cross_repository_nodes() -> None:
    """get_neighbors, find_path, and get_impact must reject nodes from another repository."""
    workspace_id = uuid.uuid4()
    requested_repo_id = uuid.uuid4()
    other_repo_id = uuid.uuid4()
    node_id = uuid.uuid4()
    target_id = uuid.uuid4()

    foreign_node = SimpleNamespace(id=node_id, repository_id=other_repo_id)
    mock_session = AsyncMock()
    repo = GraphRepository(mock_session)
    repo.get_node = AsyncMock(return_value=foreign_node)  # type: ignore[method-assign]

    async def _run() -> None:
        neighbors = await repo.get_neighbors(
            workspace_id=workspace_id,
            node_id=node_id,
            repository_id=requested_repo_id,
        )
        assert neighbors["node"] is None
        assert neighbors["neighbors"] == []

        path = await repo.find_path(
            workspace_id=workspace_id,
            source_id=node_id,
            target_id=target_id,
            repository_id=requested_repo_id,
        )
        assert path == []

        impact = await repo.get_impact(
            workspace_id=workspace_id,
            node_id=node_id,
            repository_id=requested_repo_id,
        )
        assert impact["root"] is None
        assert impact["impacted_nodes"] == []

    _run_coro(_run())


def test_lifespan_refuses_insecure_jwt_in_non_debug_mode() -> None:
    """Production/non-debug startup must abort if JWT_SECRET_KEY uses the insecure default."""
    fake_settings = SimpleNamespace(
        log_level="INFO",
        is_jwt_secret_insecure=True,
        debug=False,
        app_version="test",
        embedding_provider="local",
        llm_provider="google",
        jev_enabled=False,
    )
    app = MagicMock()

    async def _run() -> None:
        with patch("app.main.get_settings", return_value=fake_settings), patch(
            "app.main.setup_logging"
        ):
            with pytest.raises(RuntimeError, match="insecure default JWT_SECRET_KEY"):
                async with lifespan(app):
                    pass

    _run_coro(_run())


def test_liveness_endpoint_and_security_headers() -> None:
    """Unauthenticated /api/v1/live probe works and security headers middleware is wired."""
    assert _run_coro(liveness_check()) == {"status": "alive"}

    app = create_app()
    live_routes = [
        r for r in app.routes if getattr(r, "path", None) == "/api/v1/live"
    ]
    assert len(live_routes) == 1

    # Verify security headers middleware is registered on the app
    middleware_names = [m.cls.__name__ for m in app.user_middleware]
    assert "BaseHTTPMiddleware" in middleware_names
    assert "CORSMiddleware" in middleware_names

    # Invoke the registered BaseHTTPMiddleware dispatch directly
    sec_mw = next(m for m in app.user_middleware if m.cls.__name__ == "BaseHTTPMiddleware")
    dispatch_fn = sec_mw.kwargs["dispatch"]

    async def _fake_call_next(_req):
        return JSONResponse({"ok": True})

    resp = _run_coro(dispatch_fn(MagicMock(), _fake_call_next))
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
