# TrunkHQ — SaaS Gap Analysis (Phase 0)

**Date:** November 17, 2026  

| Domain | Current State | Target SaaS Requirement | Priority |
| :--- | :--- | :--- | :--- |
| **Multi-Tenancy & Orgs** | Flat `users` + shared `Project Storage House` (`list_all`, `get_by_id_shared`) | `organizations`, `organization_members` (Owner/Admin/Developer/Viewer), `organization_id` isolation on all queries | **P0** |
| **Project Abstraction** | 1 `Repository` = 1 "Project" | `projects` grouping multiple GitHub `repositories` + `documents` + `conversations` | **P0** |
| **Auth & Onboarding** | Email/password register + login (`auth.py`) | Guided onboarding (account type, org creation), email verification, password reset, GitHub OAuth (encrypted token storage, `state` CSRF) | **P1** |
| **GitHub Integration** | Public/private URL clone using env/request PAT | GitHub OAuth repo picker, multi-repo sync, signed webhooks with idempotency | **P1** |
| **Document Intelligence** | Not implemented (code-only ingestion) | Upload & parse PDF/DOCX/MD/TXT/OpenAPI/SQL/diagrams scoped to `project_id` + `organization_id` | **P1** |
| **RAG & AI Chat** | Hybrid pgvector+FTS + line citations (non-streaming) | Project-scoped cross-repo + doc retrieval, SSE streaming responses, token accounting, BYOK per org | **P1** |
| **Knowledge Graph** | Python AST + TS/JS + manifests; scoped by `repository_id` | Cross-repo + document-to-code edges (`DOCUMENTS`, `EXPOSES`, `BELONGS_TO`), lazy subgraph pagination | **P2** |
| **Billing & Metering** | Static `/pricing` marketing page only | `plans`, `subscriptions`, `usage_records`, server-verified payment webhooks (Stripe/Razorpay), entitlement checks | **P1** |
| **Background Jobs** | In-process `asyncio.create_task` | Durable job queue (`ingestion_jobs` / Redis+ARQ) with retries, concurrency limits, progress events | **P1** |
| **UI/UX Shell** | Top Navbar + `/`, `/pricing`, `/projects/[id]`, `/system` | Enterprise app shell: collapsible sidebar, workspace/org switcher, global search, onboarding wizard, team/billing/org settings | **P1** |
| **Security & Ops** | Admin `/health`, `/live`, security headers, owner reindex check | Rate limiting (`slowapi`), encrypted secrets/BYOK, audit logs, non-root Dockerfile, CI/CD, E2E + tenant isolation tests | **P0/P1** |
