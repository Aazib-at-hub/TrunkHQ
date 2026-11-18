# TrunkHQ — SaaS Implementation Roadmap

**Date:** November 17, 2026  
**Approach:** Modular monolith evolution — preserve existing RAG, ingestion, and graph engines; ship incrementally with tests at every phase.

---

## Phase Overview

| Phase | Scope | Key Deliverables | Risk / Approval Gate |
| :---: | :--- | :--- | :--- |
| **0** | **Audit & Baseline** *(Current)* | `ARCHITECTURE_AUDIT.md`, `CURRENT_SYSTEM_MAP.md`, `SAAS_GAP_ANALYSIS.md`, `SECURITY_REVIEW.md`, `IMPLEMENTATION_ROADMAP.md` | Wait for user approval before Phase 1+ changes |
| **1** | **Target Architecture & Migration Design** | Finalize multi-tenant ERD (`organizations`, `organization_members`, `projects`, `subscriptions`) and backward-compatible Alembic migration strategy | Schema design review |
| **2** | **Design System & App Shell** | Linear/Vercel/GitHub-inspired UI: collapsible sidebar, workspace switcher, clean typography, dense technical layout, Day/Night preservation | UI/UX layout shift |
| **3** | **Auth, Onboarding & Multi-Tenancy** | `Organization` + `OrganizationMember` (Owner/Admin/Developer/Viewer), personal org auto-creation, tenant-scoped DAOs, guided onboarding, GitHub OAuth + email verification/reset | **HIGH RISK:** Alters data ownership & replaces `get_by_id_shared` |
| **4** | **Projects & Multi-Repo Management** | `Project` entity grouping multiple `Repository` connections, GitHub repo picker, signed webhooks & incremental sync | **HIGH RISK:** Adds `project_id` FK & updates repository routes |
| **5** | **Document Intelligence** | Upload & parse PDF/DOCX/MD/TXT/OpenAPI/SQL/diagrams into `documents` & `document_chunks` scoped to `project_id` + `organization_id` | Storage & file parsing limits |
| **6** | **RAG & AI Chat Upgrade** | Cross-repo + document hybrid retrieval, SSE streaming responses, token accounting, encrypted BYOK per org | Streaming protocol & token metering |
| **7** | **Knowledge Graph Evolution** | Project-level cross-repo + document nodes/edges (`DOCUMENTS`, `EXPOSES`, `BELONGS_TO`), lazy subgraph pagination, provenance/confidence badges | Graph schema extensions |
| **8** | **Team Collaboration & Permissions** | Org/project invitations, RBAC enforcement, shared team conversations, activity/audit logs | Permission matrix verification |
| **9** | **Billing, Entitlements & Metering** | `plans`, `subscriptions`, `usage_records`, server-verified payment webhooks (Razorpay/Stripe), quota enforcement | **HIGH RISK:** Financial & entitlement enforcement |
| **10** | **Security Hardening & Production Ops** | `slowapi` rate limiting, durable background worker queue, non-root Dockerfile, CI/CD, full tenant-isolation & E2E test suite | Final launch gate |
