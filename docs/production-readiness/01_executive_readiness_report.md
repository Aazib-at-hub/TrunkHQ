# TrunkHQ — Executive Production Readiness Report

**Audit Date:** November 14, 2026  
**System Version:** V2 (Phases 1–5 + Project Storage House + Admin Diagnostics + Day/Night UI)  
**Target Segments:** Controlled Single-Org / Agency / Startup Pilots vs. Multi-Tenant Enterprise SaaS  

---

## 1. Executive Release Decision

| Target Deployment Model | Decision | Rationale |
| :--- | :--- | :--- |
| **Single-Tenant / Dedicated Team Pilot** (Startups, Agencies, Freelance Teams) | **CONDITIONAL GO — CONTROLLED PILOT** | Core ingestion, hybrid RAG, AST/TS graph, auth, admin-gated `/health`, and P1 security/lint fixes verified. Requires production env vars (`DEBUG=False`, high-entropy `JWT_SECRET_KEY`, `ADMIN_EMAILS`). |
| **Multi-Tenant Public SaaS / External Enterprise** | **NO-GO** | **Project Storage House** shares repositories, files, chunks, chat RAG queries, and graph reads across all authenticated users (`get_by_id_shared`, `list_all`). Missing workspace/org tenancy isolation, API rate limiting, persistent job queue, and CI/CD. |

---

## 2. Baseline vs. Remediated Verification Summary

| Gate | Baseline (Pre-Remediation) | Post-Remediation (Verified) |
| :--- | :--- | :--- |
| **Backend Unit Tests** (`python -m pytest backend\tests\unit -q`) | `47 passed, 1 skipped` (1.86s) | **`51 passed, 1 skipped` (2.02s)** |
| **Frontend TypeScript** (`cd frontend; npx tsc --noEmit`) | Exit code `0` | **Exit code `0` (Clean)** |
| **Frontend ESLint** (`cd frontend; npm run lint`) | Failed (`10 problems: 8 errors, 2 warnings`) | **Exit code `0` (`0 errors, 1 warning`)** |
| **Graph Reindex Owner Check** (`POST /repositories/{id}/graph/reindex`) | Any authenticated user could mutate/delete another user's graph | **Fixed (`403 ForbiddenError` for non-owners)** |
| **Graph Repository Scoping** (`neighbors`, `paths`, `impact`) | Cross-repository `node_id` IDOR within same owner workspace | **Fixed (`repository_id` enforced in `graph_repo.py` & `graph.py`)** |
| **Production JWT Fail-Fast** (`backend/app/main.py`) | Logged `critical` but continued booting with default secret | **Fixed (`RuntimeError` aborts startup when `not debug` and default secret)** |
| **CORS & Security Headers** (`backend/app/main.py`) | `PATCH` missing from CORS `allow_methods`; no security headers | **Fixed (`PATCH` added; `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`)** |
| **Docker Healthcheck** (`docker-compose.yml`) | Hit admin-only `/api/v1/health` (401/403) without status check | **Fixed (Unauthenticated `/api/v1/live` probe + `.raise_for_status()`)** |

---

## 3. Remaining Open Risks & Remediation Backlog

### P1 (Required Before Multi-Tenant / External Enterprise GA)
1. **Workspace / Tenant Isolation:** Current `Project Storage House` design (`RepositoryRepository.get_by_id_shared`, `list_all`) exposes all repositories and codebases to any authenticated user in the instance. Deploy one isolated instance per organization until workspace membership scoping is implemented.
2. **Rate Limiting & Abuse Protection:** No rate limiting on `/api/v1/auth/login`, `/api/v1/auth/register`, `/api/v1/repositories/import`, `/api/v1/chat`, or `/graph/reindex`. Enforce at reverse proxy (Nginx/Cloudflare) or add `slowapi` middleware.
3. **Migration `004_hybrid_search_indexes.py` Downgrade Bug:** `downgrade()` drops `ix_code_chunks_embedding_hnsw` originally created in `001_initial_schema.py`, and `upgrade()` creates HNSW/GIN indexes without `CONCURRENTLY`.

### P2 (Operational Hardening)
1. **Background Job Durability:** Ingestion runs via in-process `asyncio.create_task` (mitigated on restart by `recover_stale_repositories` marking stale jobs `FAILED`, but no automatic retry or external worker queue like Celery/ARQ).
2. **Database & Provider Timeouts:** `backend/app/database/session.py` lacks `pool_recycle`, `pool_timeout`, and `statement_timeout`; `GoogleLLMService` / `OpenAILLMService` wrap raw exceptions in `InternalServerError` returned to clients.
3. **Git Token Exposure in Process Args:** `backend/app/ingestion/cloner.py` embeds `github_token` in clone URL CLI arguments (`ps` visibility during clone).
4. **Prompt Injection Hardening:** `backend/app/rag/prompt.py` uses static `====` delimiters around retrieved chunks and history.
5. **Container & Dependency Hardening:** `backend/Dockerfile` runs as `root` with `--reload`; `requirements.txt` uses unpinned `>=`; no `.github/` CI/CD workflows exist.

---

## 4. Unverified Scope (Not Executed in Local Audit)
- Live load/stress testing on staging infrastructure.
- End-to-end migration execution from scratch against an empty PostgreSQL instance (`alembic upgrade head` -> `downgrade` -> `upgrade`).
- Live external provider outage/rate-limit chaos tests (Google Gemini / OpenAI / GitHub private repo tokens).
- Automated browser E2E suite (Playwright/Cypress) — none exists in the repository.
