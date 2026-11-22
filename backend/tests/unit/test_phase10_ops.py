"""
Unit tests for Phase 10 Security Hardening & Production Ops:
- slowapi rate limiting middleware wired on FastAPI app
- X-Request-Id correlation header returned by middleware
- SQLAlchemy async engine pool hardening
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.responses import JSONResponse

from app.database.session import engine
from app.main import create_app


def _run_coro(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_rate_limiter_and_correlation_id_wired() -> None:
    app = create_app()
    middleware_names = [m.cls.__name__ for m in app.user_middleware]
    assert "SlowAPIMiddleware" in middleware_names
    assert hasattr(app.state, "limiter")

    sec_mw = next(m for m in app.user_middleware if m.cls.__name__ == "BaseHTTPMiddleware")
    dispatch_fn = sec_mw.kwargs["dispatch"]
    fake_req = MagicMock()
    fake_req.headers = {}

    async def _fake_call_next(_req):
        return JSONResponse({"ok": True})

    resp = _run_coro(dispatch_fn(fake_req, _fake_call_next))
    assert resp.headers.get("X-Request-Id")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"


def test_db_engine_pool_hardened() -> None:
    assert engine.pool._pre_ping is True  # type: ignore[attr-defined]
    assert 0 < engine.pool._recycle <= 1800  # type: ignore[attr-defined]
