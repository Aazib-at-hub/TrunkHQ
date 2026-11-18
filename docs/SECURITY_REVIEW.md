# TrunkHQ — Phase 0 Security Review

**Date:** November 17, 2026  

---

## 1. Verified Security Controls (Already Active)

1. **Git Command Option Injection Defense:** Branch regex `^[a-zA-Z0-9._/-]+$` in `schemas/repository.py` + `--` terminator in `ingestion/cloner.py`.
2. **Symlink Traversal Protection:** `resolved_target.is_relative_to(repo_root_resolved)` in `ingestion/discovery.py`.
3. **JWT Fail-Fast in Non-Debug Mode:** `lifespan` in `app/main.py` raises `RuntimeError` if `is_jwt_secret_insecure` and `not settings.debug`.
4. **Graph Endpoint Hardening:** `reindex_graph` requires `repo.user_id == current_user_id` (`403 ForbiddenError`); `neighbors`, `paths`, and `impact` enforce `repository_id == repo_id`.
5. **Admin Health Gating & Security Headers:** `/api/v1/health` requires `require_admin`; `/api/v1/live` is minimal; `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy` attached.

---

## 2. Critical Security Risks Blocking Multi-Tenant SaaS

| Risk | Severity | Location / Cause | Required Remediation |
| :--- | :---: | :--- | :--- |
| **Cross-Tenant Data Exposure** | **P0** | `RepositoryRepository.list_all` & `get_by_id_shared` return all users' repos, files, chunks, and graph reads | Replace with `organization_id` + `OrganizationMember` enforcement in every repository/service/SQL query |
| **No API Rate Limiting** | **P1** | `slowapi` in `pyproject.toml` is unused; `/auth/*`, `/import`, `/chat`, `/graph/reindex` unprotected | Wire `slowapi` per-IP and per-tenant limits |
| **GitHub Token in CLI Args** | **P2** | `cloner.py` embeds `github_token` in clone URL CLI args (`ps` visibility) | Use `GIT_ASKPASS` helper or ephemeral credential helper; never log tokens |
| **Raw LLM Exception Leakage** | **P2** | `GoogleLLMService` & `OpenAILLMService` pass raw provider errors into `InternalServerError` | Return sanitized error messages; log full trace server-side only |
| **Prompt Injection Delimiters** | **P2** | `rag/prompt.py` uses static `====` separators around untrusted repo/doc content | Use randomized/XML boundary tags + strict untrusted-data framing |
| **Unpinned Container & `root` User** | **P2** | `backend/Dockerfile` runs as `root` with `--reload` | Switch to non-root user and production `uvicorn` command |

---

## 3. SaaS Security Requirements for Upcoming Phases

- **GitHub OAuth & BYOK:** Encrypt OAuth tokens and customer BYOK keys at rest (Fernet/AES-GCM with server KMS/env key); validate OAuth `state` against signed CSRF token; never return secrets in API responses.
- **Document Uploads:** Enforce MIME/magic-byte validation, max file size, extension allowlist, and isolated parsing (no arbitrary macro/script execution).
- **Webhooks (GitHub & Billing):** Verify HMAC signatures (`X-Hub-Signature-256`, Stripe/Razorpay signature) and enforce idempotency keys.
- **Audit Trail:** Log membership changes, role updates, repo/project deletions, and admin actions in `audit_logs`.
