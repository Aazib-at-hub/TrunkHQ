# TrunkHQ — Customer Pilot Readiness Checklist

## 1. Pre-Pilot Gate Checklist

- [x] **Backend Unit Suite:** `51 passed, 1 skipped` (`python -m pytest backend\tests\unit -q`).
- [x] **Frontend Typecheck & Lint:** `npx tsc --noEmit` clean (`0` errors); `npm run lint` `0` errors (`1` pre-existing hook deps warning).
- [x] **Owner-Only Mutations:** `PATCH`/`DELETE`/re-index and `POST /repositories/{id}/graph/reindex` enforce `repo.user_id == current_user_id`.
- [x] **Repository-Scoped Graph Queries:** `neighbors`, `paths`, and `impact` enforce `repository_id == repo_id`.
- [x] **Admin-Only System Diagnostics:** `/api/v1/health` and `/system` gated by `ADMIN_EMAILS`; `/api/v1/live` available for container healthchecks.
- [x] **JWT Startup Guard:** Non-debug startup aborts if `JWT_SECRET_KEY` uses the insecure default.
- [ ] **Reverse-Proxy Rate Limiting:** Configure external rate limiting before exposing to untrusted traffic.
- [ ] **Isolated Single-Org Provisioning:** Provision one dedicated Cortex instance per customer organization (Project Storage House shares repositories across all authenticated users in the same DB).

---

## 2. Disclosed Limitations for Pilot Customers

1. **Single-Organization Workspace Model:** Authenticated users within a single Cortex instance share read access to imported repositories, files, and knowledge graphs (chat conversations remain private per user). Multi-tenant SaaS org isolation is not yet implemented.
2. **In-Process Background Ingestion:** Repository cloning/indexing runs in-process; server restarts during an active import mark in-flight jobs `FAILED` for manual retry rather than resuming automatically.
3. **Embedding Dimension Coupling:** `code_chunks.embedding` is fixed at `Vector(384)` (`all-MiniLM-L6-v2`). Switching to 1536-dim OpenAI embeddings requires a schema migration.
