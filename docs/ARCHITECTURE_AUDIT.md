# TrunkHQ — Phase 0 Architecture Audit

**Date:** November 17, 2026  
**Principle:** Preserve working intelligence engines (`ingestion/`, `rag/`, `graph/`) and evolve into a modular multi-tenant SaaS.

---

## 1. What Currently Works Well (Reusable Core)

1. **Repository Ingestion Pipeline (`backend/app/ingestion/`):**
   - Shallow `git clone --depth 1` with branch regex validation and `--` option terminator (`cloner.py`).
   - File discovery with symlink escape protection, binary/vendor directory filtering, and `content_hash` tracking (`discovery.py`, `filter.py`).
   - Line-aware chunking (`chunker.py`) and batched 384-dim `all-MiniLM-L6-v2` embeddings.
   - Idempotent re-index purge (`delete_by_repository`) and startup stale-job recovery (`recover_stale_repositories` in `main.py`).
2. **Hybrid RAG Engine (`backend/app/rag/`):**
   - Combines pgvector cosine similarity + PostgreSQL `tsvector` full-text search (`retriever.py`) with line-level source citations (`prompt.py`, `message_sources`).
   - Provider abstraction for Google Gemini and OpenAI (`llm/`).
3. **AST & Lexical Knowledge Graph (`backend/app/graph/`):**
   - Python AST + TypeScript/JS + manifest extractors producing typed `graph_nodes` and `graph_edges`.
   - Subgraph slicing, 1-hop neighbors, BFS shortest path, blast-radius impact analysis, and hub/module insights (`graph_repo.py`, `RelationshipGraph.tsx`).
4. **Core Web App & Theme System (`frontend/`):**
   - Clean Day/Night CSS variable system, React Flow graph explorer, inline `SourceViewerModal`, and admin-gated `/system` diagnostics.

---

## 2. Partially Implemented / Broken / Technical Debt

1. **Single-Instance Shared Tenancy ("Project Storage House"):**
   - `RepositoryRepository.list_all` and `get_by_id_shared` return repositories across *all* registered users. Suitable only for a single-team deployment, **not** multi-tenant SaaS.
2. **In-Process Background Jobs:**
   - `asyncio.create_task` runs ingestion inside the FastAPI web process. Server restarts abort in-flight jobs; no worker pool, retry/dead-letter handling, or concurrency caps.
3. **Database & Migration Debt:**
   - `004_hybrid_search_indexes.py` `downgrade()` drops `ix_code_chunks_embedding_hnsw` created in `001`; `upgrade()` creates indexes without `CONCURRENTLY`.
   - `code_chunks.embedding` is hardcoded to `Vector(384)` (`chunk.py:50`), blocking 1536-dim OpenAI embeddings without migration.
   - `session.py` lacks `pool_recycle`, `pool_timeout`, and `statement_timeout`.
4. **Sequential Retrieval & Unstreaming Chat:**
   - `retriever.py` runs `_vector_search` and `_fts_search` sequentially; `POST /chat` returns full responses rather than SSE streaming.
5. **Unwired Rate Limiting & Raw LLM Exceptions:**
   - `slowapi` is in `pyproject.toml` but not attached to `app`; `GoogleLLMService` / `OpenAILLMService` expose raw exception strings in `InternalServerError`.
6. **Container & Deployment Debt:**
   - `backend/Dockerfile` runs as `root` with `--reload`; `pyproject.toml` uses unpinned `>=` bounds; no `.github/` CI/CD workflows exist.

---

## 3. Architectural Changes Justified for SaaS

| Proposed Change | Why Necessary |
| :--- | :--- |
| Add `organizations` + `organization_members` + `projects` tables; scope all data by `organization_id` | Enables freelancers (isolated client projects), agencies, startups, and enterprises to share one Cloud SaaS safely without data leakage. |
| Introduce `Project` entity above `Repository` & `Document` | Matches real engineering systems where 1 product/client project contains multiple GitHub repos + uploaded specs/PDFs/diagrams. |
| Add `documents` + `document_chunks` (reusing `Vector(384)` hybrid RAG) | Required for SRS/PRD/OpenAPI/architecture doc intelligence alongside code. |
| Wire `slowapi` + `usage_events` / `subscriptions` | Protects AI inference costs and enables plan entitlements (`Free`, `Pro`, `Team`, `Business`, `Enterprise`). |
| Move ingestion to durable DB-backed job table / ARQ worker | Prevents lost imports on deploy and supports webhook-driven incremental sync. |
