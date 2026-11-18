# 04. TrunkHQ V2 — Improvement Specification

> **Principle:** Preserve the working FastAPI + PostgreSQL/pgvector + Next.js foundation. Fix correctness bugs first, then layer V2 intelligence, graph precision, and UI simplicity in 5 ordered phases.

---

## Phase 1 — UI/UX Polish & Navigation Foundation
**Dependencies:** None (pure frontend + existing backend endpoints).

1. **Direct Project Routing (`/projects/[id]`):**
   - Add `frontend/app/projects/[id]/page.tsx` wrapping `ChatInterface`.
   - Update `frontend/app/page.tsx` so clicking a `RepoCard` routes to `/projects/${repo.id}` instead of toggling local `selectedRepo` state.
   - Make `Navbar.tsx` brand clickable (`/`).
2. **Workspace Simplification (`ChatInterface.tsx`, `Navbar.tsx`, `GraphToolbar.tsx`):**
   - Default `ChatInterface` tab to `details` (`Details` | `Chat` | `Graph`).
   - Keep `ChatInterface` header to `Back | Project Name + Status | Tabs`; move `Vector RAG / Graph-Enhanced RAG` toggle into the chat prompt bar.
   - Surface past conversations via a compact **History** dropdown using `chatApi.listConversations`, `getConversation`, and `deleteConversation`.
   - In `GraphToolbar.tsx`, keep Search + Domain filter visible by default and group Layout/Cluster/Insights under a **View Options** toggle.
3. **Fix Broken States & Visual Consistency:**
   - **Real Citation Previews:** Update `ChatInterface.tsx:handleOpenSource` to resolve the file by `file_path` and fetch real source lines via `repoApi.getFileDetail` (falling back gracefully if not found).
   - **Fix Spinners & Errors:** Set `loadingRepos(true)` in `page.tsx`, `loading(true)` in `GraphNodeDetails.tsx`, and surface inline error states in `page.tsx`, `ImpactPanel.tsx`, and `ProjectDetailsPanel.tsx`.
   - **Theme & Height Fixes:** Replace hardcoded dark hex colors (`#1a1b25`, `#101118`, `#171822`) with CSS theme tokens (`bg-bg-primary`, `bg-bg-secondary`, `bg-bg-tertiary`), fix `RelationshipGraph.tsx` container height (`h-full` inside flex parent), and replace native `confirm()`/`alert()` with `Modal` + inline feedback.

**Acceptance Criteria:**
- Refreshing `/projects/[id]` preserves the project view; browser Back returns to `/`.
- Clicking any chat citation opens real file content scrolled/highlighted to `start_line..end_line`.
- Light and dark OS themes both maintain readable contrast across all panels.

---

## Phase 2 — Core Logic, Ingestion & Hybrid RAG Upgrade
**Dependencies:** Alembic migration for pgvector index & flexible embedding dimension.

1. **Vector Index & Dimension Safety (`models/chunk.py` + Alembic):**
   - Add pgvector HNSW index (`vector_cosine_ops`) on `CodeChunk.embedding`.
   - Align `CodeChunk.embedding` dimension with configured provider or enforce dimension validation at startup.
2. **Incremental Ingestion & Pipeline Reliability (`ingestion/pipeline.py`, `cloner.py`):**
   - Compare `RepositoryFile.content_hash` on reindex: skip unchanged files, update modified files, delete removed files, and bulk-insert new files/chunks.
   - Fix empty-repo reindex stale data bug (`delete_by_repository` before early return), `proc.kill()` + `await proc.wait()` on clone timeout, and use `_force_rm` everywhere on Windows.
   - Pass `Settings.github_token` when cloning private repositories; guard `"PENDING"` in `reindex_repository`.
   - Generate a repository-level architectural summary during ingestion and store it on `Repository`.
3. **Hybrid Retrieval + Multi-Turn RAG + Grounded Citations:**
   - Add PostgreSQL `tsvector` / GIN full-text search on `CodeChunk.content` + `RepositoryFile.path`, fused with vector cosine search via Reciprocal Rank Fusion (RRF).
   - Implement real reranking in `backend/app/decision/` (wired to `Settings.jev_enabled`) instead of the no-op `SimpleDecisionService`.
   - Pass recent conversation turns (`Message` history) into `RAGGenerator.generate_answer` with a token-budget cap in `build_user_prompt`.
   - Filter/verify citations so `MessageSource` only records chunks actually referenced or above threshold, and return an explicit uncertainty response without hallucinating when retrieval is empty.
   - Fix `GoogleLLMService` to avoid mutating global `genai.configure` per call and handle blocked/empty `response.text` safely.

**Acceptance Criteria:**
- Re-indexing an unchanged repo re-embeds 0 files.
- Exact symbol/endpoint queries rank the defining file in top 3 via hybrid RRF.
- Follow-up questions in the same conversation resolve pronouns/context from prior turns.

---

## Phase 3 — Knowledge Graph Precision & Cross-Language Parsing
**Dependencies:** Tree-sitter (`tree-sitter-languages` or language grammars) or upgraded AST/symbol resolver.

1. **Accurate Multi-Language Extraction (`backend/app/graph/extractors/`):**
   - Upgrade TypeScript/JS extraction (Tree-sitter or TS parser) to extract class methods, resolve relative imports (`./foo` -> `foo.ts` / `index.ts`), and trace cross-file calls.
   - Improve Python cross-file symbol resolution (import alias table mapping `from app.x import y` to target `file::symbol` `stable_key`).
   - Extract DB model -> table / service `READS_FROM` and `WRITES_TO` edges, plus Next.js API/page routes (`EXPOSES`).
2. **Reconciliation & Provenance:**
   - Populate `commit_sha` / `source_commit` from `git rev-parse HEAD` during ingestion.
   - Reconcile stale nodes across all `source_kind` values (`code`, `architecture`, `knowledge`), and populate `nodes_updated` / `edges_updated` in `GraphIndexRun`.

**Acceptance Criteria:**
- Cross-file `IMPORTS` and `CALLS` in both Python and TypeScript resolve to real `GraphNode` records rather than synthetic external placeholders when the target exists in the repo.

---

## Phase 4 — Graph-Assisted Intelligence & Canvas UX
**Dependencies:** Phase 1 & Phase 3.

1. **Interactive Canvas Features (`RelationshipGraph.tsx`, `ImpactPanel.tsx`, `GraphNodeDetails.tsx`):**
   - Wire `graphApi.findPath` into a "Trace Path (From -> To)" control and highlight the path on the canvas.
   - Wire `graphApi.searchNodes` for server-side search when repos exceed the initial node slice, with a clear truncation indicator (`Showing X of Y nodes`).
   - Highlight `ImpactPanel` blast-radius nodes/edges directly on the canvas and allow clicking impacted items to focus them.
   - Display `confidence` and `evidence_kind` on edge/neighbor inspection; unify hub threshold (`>= 5`) across backend and frontend.
2. **Intent-Aware Graph Retrieval (`chat_service.py`):**
   - Replace naive whitespace word splitting (`len > 3`) with symbol/entity extraction from the user query before calling `GraphRepository.search_nodes`.

**Acceptance Criteria:**
- Asking *"If I change `validate_token`, what breaks?"* returns callers, dependent modules, and test files grounded in `graph_edges`.

---

## Phase 5 — Production Validation & Observability
**Dependencies:** Phases 1–4.

1. **Worker Queue & Recovery:** Move ingestion off in-process `asyncio.create_task` (or add startup recovery marking stale `CLONING`/`INDEXING` runs as `FAILED` with retry).
2. **Evaluation & Automated Tests:** Add retrieval evaluation suite (precision@k / MRR on golden repo queries), citation-grounding tests, and CI checks (`pytest` + `tsc --noEmit` + `next build`).
3. **System Intelligence View:** Surface indexing run metrics (`GraphIndexRun`), retrieval latency, and error diagnostics in a dedicated `/system` view.

