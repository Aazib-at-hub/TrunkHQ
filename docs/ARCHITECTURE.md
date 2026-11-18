# TrunkHQ — Target SaaS Architecture

**Date:** November 17, 2026  
**Style:** Modular Monolith (FastAPI + PostgreSQL/pgvector + Next.js)

---

## 1. Architectural Principles

1. **Preserve Core Intelligence Engines:** Keep `ingestion/`, `rag/`, and `graph/` intact; evolve interfaces to accept `organization_id` and `project_id` cleanly.
2. **Modular Monolith First:** Clear domain module boundaries inside `backend/app/` without premature microservices. Background ingestion moves to a durable job worker (`ingestion_jobs` / ARQ) sharing the same codebase.
3. **Tenant-Aware Data Access:** Every tenant-owned query enforces `organization_id` (and `OrganizationMember` membership) at the dependency/DAO layer—never relying on frontend filtering.

---

## 2. Target Domain Modules (`backend/app/`)

```
backend/app/
  api/v1/
    auth.py            # Register, login, email verify, password reset, GitHub OAuth
    organizations.py   # Org CRUD, switcher, invitations, member roles, audit logs
    projects.py        # Multi-repo + doc project management
    repositories.py    # GitHub repo import, sync, webhook receiver, files
    documents.py       # PDF/DOCX/MD/OpenAPI/SQL/diagram upload & status
    chat.py            # Project-scoped streaming SSE RAG + citations
    graph.py           # Cross-repo & doc subgraph, paths, impact analysis
    billing.py         # Plans, subscriptions, usage metering, webhook handler
    health.py          # /live (public) & /health (admin-only)
  core/                # Config, JWT/OAuth security, crypto (BYOK/tokens), rate limit
  ingestion/           # Cloner, discovery, filter, chunker, document parsers
  rag/                 # Hybrid vector+FTS retriever, citation prompt, SSE streamer
  graph/               # Python AST, TS/JS, manifest, and document-to-code extractors
  llm/                 # Provider-agnostic LLM & embedding adapters + token accounting
  repositories/        # Tenant-scoped DAOs (Org, Project, Repo, Doc, Graph, Billing)
  services/            # Domain orchestration & entitlement checks
```

---

## 3. Target Request & Ingestion Flow

1. **Authenticated Request:** JWT -> `get_current_user` -> `get_current_org(org_id)` verifies `OrganizationMember` role -> service/DAO filters strictly by `organization_id`.
2. **Background Ingestion:** `POST /repositories/import` or `POST /documents/upload` creates an `ingestion_jobs` row and enqueues work asynchronously; worker updates progress/errors idempotently and populates `code_chunks`/`document_chunks` + `graph_nodes`/`graph_edges`.
3. **Contextual Retrieval:** `POST /chat` queries only `code_chunks` and `document_chunks` belonging to the authorized `project_id` + `organization_id`, expands 1-hop graph context, streams cited Markdown over SSE, and records token usage in `usage_records`.
