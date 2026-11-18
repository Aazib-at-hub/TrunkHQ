# 05. TrunkHQ V2 — Implementation Prompts

> **Usage:** Run these prompts sequentially in Antigravity. Each prompt is scoped to exact files in this repository so working functionality is preserved.

---

## Prompt 1 — Phase 1: UI/UX Polish, Direct Routing & Real Citation Previews

```text
Implement Phase 1 of docs/v2-audit/04_improvement_specification.md without modifying backend ingestion or graph extractors:
1. Add Next.js route `frontend/app/projects/[id]/page.tsx` that loads the project via `repoApi.getRepo(id)` and renders `Navbar` + `ChatInterface` (with `onBack` navigating to `/`). Update `frontend/app/page.tsx` so clicking a `RepoCard` navigates to `/projects/${repo.id}` via `useRouter`, and make the `Navbar` brand link to `/`.
2. In `frontend/components/chat/ChatInterface.tsx`:
   - Default `activeTab` to `"details"` and order tabs `Details`, `Chat`, `Graph`.
   - Simplify the sub-header to Back | Project Name + Status | Tabs; move the `Vector RAG / Graph-Enhanced RAG` toggle into the chat prompt bar.
   - Fix `handleOpenSource` so clicking any `SourceCard` fetches real file content via `repoApi.getFileDetail` (matching `file_path` from `repoApi.listFiles`) instead of showing the stub comment.
   - Add a compact History dropdown in the Chat view wired to `chatApi.listConversations`, `chatApi.getConversation`, and `chatApi.deleteConversation`.
   - Call `onRepoUpdated` when status polling detects changes.
3. Fix loading/error states and UI consistency:
   - Set `loadingRepos(true)` in `frontend/app/page.tsx` and `loading(true)` in `frontend/components/graph/GraphNodeDetails.tsx` before async fetches, and render inline error states instead of swallowing errors.
   - Replace native `confirm()`/`alert()` in `page.tsx`, `ChatInterface.tsx`, and `RelationshipGraph.tsx` with `Modal` / inline feedback.
   - Replace hardcoded dark hex backgrounds in `ChatInterface.tsx`, `RelationshipGraph.tsx`, `GraphToolbar.tsx`, `GraphNodeDetails.tsx`, `GraphInsightsPanel.tsx`, `ImpactPanel.tsx`, and `CustomNode.tsx` with theme tokens from `globals.css`, and fix `RelationshipGraph.tsx` height (`h-full`) so it does not clip under the `ChatInterface` header.
   - Group secondary `GraphToolbar.tsx` controls (Layout, Cluster pills, Insights) under a `View Options` toggle.
Verify with `tsc --noEmit` in `frontend/`.
```

---

## Prompt 2 — Phase 2: Incremental Ingestion, Hybrid RAG & Reliability

```text
Implement Phase 2 of docs/v2-audit/04_improvement_specification.md in `backend/`:
1. Add an Alembic migration creating a pgvector HNSW index (`vector_cosine_ops`) on `chunks.embedding` and a GIN `tsvector` index on `chunks.content` (or generated column).
2. Update `backend/app/ingestion/pipeline.py` and `backend/app/ingestion/cloner.py`:
   - Use `RepositoryFile.content_hash` for incremental reindexing (skip unchanged, update modified, delete removed, bulk-insert new files/chunks).
   - Fix empty-repo reindex to clear stale files/chunks via `file_dao.delete_by_repository`, await `proc.wait()` after `proc.kill()` on timeout, and use `_force_rm` for Windows cleanup.
   - Pass `Settings.github_token` to `git clone` when configured; guard `"PENDING"` in `RepositoryService.reindex_repository`.
   - Fix missing `Optional`/`Any` typing imports in `pipeline.py`, `rag/generator.py`, and `rag/prompt.py`.
3. Upgrade retrieval and generation:
   - Add hybrid retrieval (pgvector cosine + PostgreSQL full-text search fused with RRF) in `backend/app/retrieval/retriever.py`.
   - Implement reranking in `backend/app/decision/` wired to `Settings.jev_enabled`.
   - Pass recent conversation messages from `ChatService.ask_question` into `RAGGenerator.generate_answer`, enforce a token budget in `rag/prompt.py`, skip LLM hallucination or return explicit uncertainty when retrieval is empty, and record only grounded citations.
   - Fix `GoogleLLMService` in `backend/app/llm/google_llm.py` to avoid mutating global `genai.configure` per call and handle blocked/empty responses safely.
Add/update unit tests in `backend/tests/unit/` and run `python -m pytest backend\tests\unit -q`.
```

---

## Prompt 3 — Phase 3: Knowledge Graph Precision & Cross-Language Parsing

```text
Implement Phase 3 of docs/v2-audit/04_improvement_specification.md in `backend/app/graph/` and `backend/app/ingestion/pipeline.py`:
1. Populate `commit_sha` / `source_commit` from `git rev-parse HEAD` during ingestion and store it on `GraphIndexRun`, `GraphNode`, and `GraphEdge`.
2. Upgrade `backend/app/graph/extractors/python.py` to build a per-file import alias map so cross-file `CALLS` and `IMPORTS` resolve to actual target `file::symbol` `stable_key`s instead of speculative local keys.
3. Upgrade `backend/app/graph/extractors/typescript.py` (using Tree-sitter if added to `requirements.txt`, or an AST-backed parser) to extract class methods, resolve relative imports (`./x` -> `.ts`/`.tsx`/`.js`/`/index.ts`), and trace cross-file calls.
4. Extend `backend/app/graph/extractors/manifest.py` to detect Next.js route handlers and SQLAlchemy/DB model `READS_FROM`/`WRITES_TO` relationships.
5. Update `GraphRepository.reconcile_deleted_entities` to reconcile stale nodes across all `source_kind` values and populate `nodes_updated`/`edges_updated` on `GraphIndexRun`.
Verify with `python -m pytest backend\tests\unit -q`.
```

---

## Prompt 4 — Phase 4: Graph Explorer Interactive Features & Graph-Assisted QA

```text
Implement Phase 4 of docs/v2-audit/04_improvement_specification.md across `frontend/components/graph/` and `backend/app/services/chat_service.py`:
1. In `frontend/components/graph/RelationshipGraph.tsx` and `GraphToolbar.tsx`:
   - Wire `graphApi.findPath` into a "Trace Path" mode allowing users to pick Source and Target nodes and highlight the shortest path on the React Flow canvas.
   - Wire `graphApi.searchNodes` for server-side node search and show a clear indicator when a repository has more nodes than the loaded slice.
   - Unify hub node degree threshold to `>= 5` across `RelationshipGraph.tsx`, `CustomNode.tsx`, `GraphNodeDetails.tsx`, and `GraphRepository.get_insights`.
2. In `frontend/components/graph/ImpactPanel.tsx` and `GraphNodeDetails.tsx`:
   - Highlight blast-radius nodes and edges on the canvas, allow clicking impacted items to focus/open their node details, and expose `includeTests` and `edgeTypes` filters.
   - Display `confidence` and `evidence_kind` badges on edges/neighbors.
3. In `backend/app/services/chat_service.py`, replace naive whitespace word splitting (`len > 3`) in `graph_enhanced` mode with symbol/entity extraction before querying `GraphRepository.search_nodes`.
Verify with `tsc --noEmit` in `frontend/` and `python -m pytest backend\tests\unit -q`.
```

---

## Prompt 5 — Phase 5: Production Validation & System Intelligence

```text
Implement Phase 5 of docs/v2-audit/04_improvement_specification.md:
1. Add startup recovery in `backend/app/main.py` lifespan to mark any stale `PENDING`/`CLONING`/`INDEXING` repositories left over from an unexpected restart as `FAILED` with a clear recovery message.
2. Add a retrieval & citation evaluation test suite in `backend/tests/unit/` covering hybrid ranking, empty-context uncertainty, and citation accuracy.
3. Add a System Intelligence view (`/system` or modal) surfacing repository indexing status, `GraphIndexRun` metrics (`nodes_created`, `edges_created`, `extractor_version`, `completed_at`), and backend health diagnostics.
Verify all backend unit tests and frontend `tsc --noEmit` / `next build` pass.
```

