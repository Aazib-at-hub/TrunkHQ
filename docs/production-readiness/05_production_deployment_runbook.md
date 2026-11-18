# TrunkHQ — Production Deployment Runbook

## 1. Prerequisites & Environment Dependencies

- **Runtime:** Python 3.12+, Node.js 20+ (LTS)
- **Database:** PostgreSQL 16+ with `pgvector` extension enabled (`CREATE EXTENSION IF NOT EXISTS vector;`)
- **Git:** Git CLI 2.30+ installed on system PATH
- **Reverse Proxy (Recommended):** Nginx, Caddy, or cloud ALB/Cloudflare providing TLS termination and rate limiting on `/api/v1/auth/*`, `/api/v1/repositories/import`, `/api/v1/chat`, and `/graph/reindex`.

---

## 2. Mandatory Production Environment Matrix

```env
# Database
DATABASE_URL=postgresql+asyncpg://cortex_user:secure_password@postgres-host:5432/cortex_prod
DATABASE_URL_SYNC=postgresql://cortex_user:secure_password@postgres-host:5432/cortex_prod

# Authentication (MANDATORY: non-default high-entropy key; startup aborts in non-debug mode otherwise)
JWT_SECRET_KEY=<64-char-random-hex>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440

# Admin Access (Required for /api/v1/health and /system UI)
ADMIN_EMAILS=admin@your-org.com

# LLM & Embedding Providers
LLM_PROVIDER=google
LLM_MODEL=gemini-2.0-flash
GOOGLE_API_KEY=<secret>

EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Production Security
DEBUG=False
LOG_LEVEL=INFO
CORS_ORIGINS=https://app.your-domain.com
```

---

## 3. Database Migration Sequence

```bash
cd backend
alembic current
alembic upgrade head
```

> **Warning:** Do not run `alembic downgrade` past `004_hybrid_search_indexes` in production without recreating `ix_code_chunks_embedding_hnsw` afterward (`004`'s `downgrade()` drops that index from `001`).

---

## 4. Docker Compose & Container Notes

- `docker-compose.yml` backend healthcheck probes `GET http://localhost:8000/api/v1/live` (unauthenticated liveness probe) with `.raise_for_status()`.
- Before public production container deployment, harden `backend/Dockerfile` to run as a non-root user and remove `--reload`.

---

## 5. Post-Deployment Smoke Verification

1. **Liveness Probe (Public):**
   ```bash
   curl -fsS http://localhost:8000/api/v1/live
   # Expected: {"status":"alive"}
   ```
2. **Admin Health Probe (Authenticated Admin JWT Required):**
   ```bash
   curl -fsS -H "Authorization: Bearer <ADMIN_JWT>" http://localhost:8000/api/v1/health
   # Expected: {"status":"healthy","database":"connected",...}
   ```
3. **Repository Import & Graph Check:**
   - Import a public repository (e.g. `https://github.com/pallets/flask`, branch `main`).
   - Verify status transitions `PENDING` -> `CLONING` -> `INDEXING` -> `READY`.
   - Verify `/system` diagnostics page is visible to `ADMIN_EMAILS` users and hidden/403 for standard users.
