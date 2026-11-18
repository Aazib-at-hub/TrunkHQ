# TrunkHQ — Security and Privacy Audit Report

**Audit Date:** November 14, 2026  
**Audit Scope:** Authentication, Authorization, IDOR, Command Injection, Data Isolation, Ingestion Hardening, Security Headers, Secrets Handling.

---

## 1. Control Verification Matrix

| Control / Vector | Implementation / Location | Status |
| :--- | :--- | :--- |
| **CLI Flag Injection** | Branch regex `^[a-zA-Z0-9._/-]+$` in `schemas/repository.py` + `--` terminator in `ingestion/cloner.py` | **VERIFIED** (`test_security_audit.py`) |
| **Symlink Directory Escape** | `resolved_target.is_relative_to(repo_root_resolved)` in `ingestion/discovery.py` | **VERIFIED** (`test_security_audit.py`) |
| **Production JWT Secret Enforcement** | `lifespan` in `app/main.py` raises `RuntimeError` when `is_jwt_secret_insecure` and `not settings.debug` | **VERIFIED** (`test_security_hardening.py`) |
| **Graph Reindex Ownership** | `reindex_graph` in `api/v1/graph.py` enforces `repo.user_id == current_user_id` (`ForbiddenError` 403) | **VERIFIED** (`test_security_hardening.py`) |
| **Graph Repository Scoping (IDOR)** | `get_neighbors`, `find_path`, `get_impact` in `graph_repo.py` & `graph.py` enforce `repository_id == repo_id` | **VERIFIED** (`test_security_hardening.py`) |
| **Admin Health Gating** | `GET /api/v1/health` requires `require_admin`; `/api/v1/live` returns minimal `{"status": "alive"}` | **VERIFIED** (`test_security_hardening.py`) |
| **CORS & Security Headers** | `PATCH` included in CORS `allow_methods`; `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` middleware | **VERIFIED** (`test_security_hardening.py`) |
| **SQL Injection** | SQLAlchemy 2.0 parameterized ORM / `bindparam` queries | **VERIFIED** (Code inspection) |
| **Multi-Tenant SaaS Isolation** | Project Storage House intentionally shares repos/files/chunks/graph reads across authenticated users | **SINGLE-ORG ONLY (NO-GO FOR MULTI-TENANT SAAS)** |

---

## 2. Remediated Findings (This Audit)

### SEC-AUD-01 (P1): Missing Owner Check on `POST /repositories/{repo_id}/graph/reindex`
* **Finding:** `reindex_graph` (`backend/app/api/v1/graph.py:356`) called `_verify_repo_access` (`get_by_id_shared`) without checking `repo.user_id == current_user_id`, allowing any authenticated user to overwrite or delete another user's graph nodes/edges.
* **Fix:** Added `if repo.user_id != current_user_id: raise ForbiddenError(...)` in `backend/app/api/v1/graph.py`.
* **Evidence:** `test_reindex_graph_rejects_non_owner` in `backend/tests/unit/test_security_hardening.py` passes.

### SEC-AUD-02 (P1): Cross-Repository Graph Node IDOR
* **Finding:** `get_node_neighbors`, `find_graph_path`, and `compute_graph_impact` (`backend/app/api/v1/graph.py`) passed `workspace_id=repo.user_id` without scoping `node_id` / edges to `repository_id=repo_id`.
* **Fix:** Added `repository_id: Optional[UUID] = None` filtering in `GraphRepository.get_neighbors`, `find_path`, and `get_impact` (`backend/app/repositories/graph_repo.py`) and passed `repository_id=repo_id` from `backend/app/api/v1/graph.py`.
* **Evidence:** `test_graph_repo_rejects_cross_repository_nodes` in `backend/tests/unit/test_security_hardening.py` passes.

### SEC-AUD-03 (P1): Non-Debug Startup Allowed Insecure Default `JWT_SECRET_KEY`
* **Finding:** `lifespan` (`backend/app/main.py:66-71`) logged `critical` when `not settings.debug` and `settings.is_jwt_secret_insecure`, but did not abort startup.
* **Fix:** `lifespan` now raises `RuntimeError` in non-debug mode if `JWT_SECRET_KEY` is still the insecure default.
* **Evidence:** `test_lifespan_refuses_insecure_jwt_in_non_debug_mode` passes.

### SEC-AUD-04 (P1): Missing `PATCH` in CORS `allow_methods` & Missing Security Headers
* **Finding:** `CORSMiddleware` in `backend/app/main.py` omitted `"PATCH"` despite `PATCH /repositories/{repo_id}` existing, and no HTTP security response headers were attached.
* **Fix:** Added `"PATCH"` to `allow_methods` and added `add_security_headers` HTTP middleware (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`).
* **Evidence:** `test_liveness_endpoint_and_security_headers` passes.

---

## 3. Remaining Security Risks (Unremediated / Architectural)

1. **Cross-User Repo Visibility (P1 for Multi-Tenant):** `RepositoryRepository.get_by_id_shared` and `list_all` expose all indexed repos/files/chunks to every authenticated user. Acceptable for a single-org internal deployment; **blocking** for multi-tenant SaaS.
2. **No Rate Limiting (P1):** Auth, import, chat, and graph reindex endpoints lack per-IP / per-user throttling.
3. **GitHub Token in Clone URL Args (P2):** `clone_repository` (`backend/app/ingestion/cloner.py`) embeds `github_token` in CLI URL arguments during `git clone`.
4. **Raw LLM Exception Leakage (P2):** `GoogleLLMService.generate_response` (`google_llm.py`) and `OpenAILLMService.generate_response` (`openai_llm.py`) wrap raw exceptions in `InternalServerError` returned to clients.
5. **Static Prompt Delimiters (P2):** `build_user_prompt` (`backend/app/rag/prompt.py`) uses static `====` separators around retrieved code chunks and conversation history.
