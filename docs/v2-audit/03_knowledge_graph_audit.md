# 03. TrunkHQ V2 — Knowledge Graph Audit

> **Scope:** Audit of PostgreSQL graph models, AST/regex extractors, graph traversal APIs, and the React Flow Graph Explorer.

---

## 1. Current Graph Data Model (`backend/app/models/graph.py`)

PostgreSQL stores the graph in three tables (migration `002_relationship_graph.py`):
- **`graph_index_runs` (`GraphIndexRun`)**: Tracks `workspace_id`, `repository_id`, `commit_sha`, `status` (`RUNNING`/`READY`/`FAILED`), `nodes_created`, `nodes_updated` (never populated, always `0`), `nodes_deleted`, `edges_created`, `edges_updated` (always `0`), `edges_deleted`, `error_summary`, `extractor_version` (`"1.0"`), `schema_version` (`"1.0"`), `started_at`, `completed_at`.
- **`graph_nodes` (`GraphNode`)**: `workspace_id`, `repository_id`, `node_type`, `stable_key` (`uq_graph_nodes_workspace_stable_key`), `name`, `qualified_name`, `description`, `properties` (JSONB + GIN index), `status` (`"active"`), `source_kind` (`"code"` | `"architecture"` | `"knowledge"`), `source_uri`, `source_commit` (never populated), `content_hash`.
- **`graph_edges` (`GraphEdge`)**: `workspace_id`, `repository_id`, `source_node_id`, `target_node_id`, `edge_type`, `properties` (JSONB), `confidence` (`0.0..1.0`), `evidence_kind` (`"static"` | `"documentation"` | `"configuration"`), `source_uri`, `source_commit`, `content_hash`. Enforces `ck_graph_edges_no_self_loop` and `uq_graph_edges_unique_relation`.

### Extracted vs. Declared Coverage

| Category | Actually Extracted | Declared in `NodeType`/`EdgeType` but Unused |
| :--- | :--- | :--- |
| **Nodes** | `file`, `class`, `function`, `method`, `test`, `symbol` (TS interfaces/types + external placeholders), `service` (Docker), `api_endpoint` (FastAPI), `document` (Markdown) | `repository`, `directory`, `module`, `database`, `table`, `queue`, `external_system`, `deployment`, `config`, `requirement`, `decision`, `issue`, `commit`, `pull_request`, `incident` |
| **Edges** | `CONTAINS`, `DEFINES`, `IMPORTS`, `CALLS`, `INHERITS`, `IMPLEMENTS`, `TESTS`, `DEPENDS_ON`, `EXPOSES`, `DOCUMENTS` | `READS_FROM`, `WRITES_TO`, `IMPLEMENTS_REQUIREMENT`, `INTRODUCED_BY`, `TRACKED_BY`, `SUPERSEDES` |

---

## 2. Extraction Engine & Accuracy Gaps (`backend/app/graph/`)

1. **No Tree-sitter (Python `ast` + Regex Only):**
   - `PythonGraphExtractor` (`extractors/python.py`) uses `ast.parse` + `ast.walk`. Cross-file `CALLS` and `TESTS` build speculative keys using the caller's `relative_path`, and `IMPORTS` assumes dotted module paths map directly to `.py` files.
   - `TypeScriptGraphExtractor` (`extractors/typescript.py`) uses regex (`RE_IMPORT`, `RE_FUNCTION`, `RE_CLASS`, `RE_CALL`, etc.; `RE_REQUIRE` is defined but unused). It does **not** extract class methods, only resolves intra-file `CALLS`, and omits file extensions on local relative imports (`./foo` fails to match `foo.ts` / `foo/index.ts`).
   - `ManifestGraphExtractor` (`extractors/manifest.py`) only parses `.md` links, `Dockerfile`/`docker-compose` services, and Python `@router`/`@app` FastAPI decorators. Next.js/Express routes, SQLAlchemy/Prisma DB models (`READS_FROM`/`WRITES_TO`), and other languages (Go, Java, Rust) are not extracted.
2. **Stale Node Reconciliation Scope:** `reconcile_deleted_entities` (`graph_repo.py`) only purges deleted `source_kind="code"` nodes; stale `architecture` (`service`, `api_endpoint`) or `knowledge` (`document`) nodes are not reconciled on reindex.
3. **Commit Provenance Missing:** `commit_sha` / `source_commit` are never populated during ingestion or `reindex_graph`.

---

## 3. Traversal APIs & Frontend Explorer Gaps

### Backend (`backend/app/api/v1/graph.py`, `graph_repo.py`)
- Implemented endpoints: `GET /graph` (default `limit=300`), `GET /nodes/{node_id}`, `GET /nodes/{node_id}/neighbors`, `POST /paths` (outgoing BFS, `max_depth` 1..10), `POST /impact` (reverse BFS on `CALLS`/`IMPORTS`/`DEPENDS_ON` + 1-hop `TESTS`), `GET /search`, `GET /insights` (degree-based hubs `>= 5`), `GET /status`, `POST /reindex`.
- **Gap:** `find_graph_path` caps outgoing edges at 50 per node and searches directed outgoing edges only; `get_insights` loads all active nodes/edges into Python memory rather than aggregating in SQL.

### Frontend (`frontend/components/graph/`, `frontend/lib/graph/layout.ts`)
1. **Unused Backend APIs:** `graphApi.findPath`, `graphApi.searchNodes`, `graphApi.getStatus`, and `graphApi.getNode` (`frontend/lib/api/graph.ts`) are never called in the UI. Search in `GraphToolbar.tsx` only filters the initial 450-node slice (`RelationshipGraph.tsx:97,128`), and there is no truncation indicator when a repo exceeds 450 nodes.
2. **Blast Radius (`ImpactPanel.tsx`) Disconnected from Canvas:** Renders impacted nodes only in a modal list—it does not highlight the blast-radius subgraph on the React Flow canvas, let users click a node to focus it, or expose `edgeTypes` / `includeTests` controls.
3. **Confidence & Evidence Hidden:** `GraphEdge.confidence` and `evidence_kind` are typed in `frontend/types/graph.ts` but never shown on edges or in `GraphNodeDetails.tsx`.
4. **Heuristic Clustering & Threshold Mismatch:** `determineMacroCluster` (`frontend/lib/graph/layout.ts`) relies on hardcoded path substrings (`backend`, `frontend`, `data`, `architecture`). Hub badge threshold is `totDeg >= 6` in `RelationshipGraph.tsx:248` & `CustomNode.tsx:116`, but `>= 5` in `GraphRepository.get_insights:632` & `GraphNodeDetails.tsx:77`.
5. **Broken Loading Spinner:** `GraphNodeDetails.tsx:38-57` never calls `setLoading(true)` on node change.

