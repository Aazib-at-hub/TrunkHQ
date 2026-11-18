# TrunkHQ — Architecture and Data-Flow Report

## 1. Verified Architecture Overview

```
                                  +-----------------------------+
                                  |   Next.js 16 Web Frontend   |
                                  |  (React 19, React Flow,     |
                                  |   Zustand, Tailwind CSS)    |
                                  +--------------+--------------+
                                                 | HTTP / REST (CORS)
                                                 v
                                  +-----------------------------+
                                  |     FastAPI Backend (v1)    |
                                  |  (AsyncPG, Pydantic v2)     |
                                  +--------------+--------------+
                                                 |
         +---------------------------------------+---------------------------------------+
         |                                       |                                       |
         v                                       v                                       v
+------------------+                   +------------------+                   +--------------------+
| Ingestion & AST  |                   | Hybrid RAG       |                   | Relationship Graph |
| Pipeline Engine  |                   | Retrieval Engine |                   | Query & Blast Rad. |
+--------+---------+                   +--------+---------+                   +---------+----------+
         |                                      |                                       |
         v                                      v                                       v
+--------------------------------------------------------------------------------------------------+
|                              PostgreSQL 16 + pgvector Database                                   |
| - users               - repositories         - files             - code_chunks (HNSW 384d + GIN) |
| - conversations       - messages             - message_sources   - graph_nodes                   |
| - graph_edges         - graph_index_runs                                                         |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. Component Responsibilities

### Frontend Layer (`frontend/`)
* **State Management:** Zustand auth store (`lib/store/auth.ts`) and theme store (`lib/store/theme.ts`, Day/Night toggle).
* **Admin-Only Diagnostics:** `/system` page and Navbar health indicator are gated to admin users (`user?.is_admin`, backed by `ADMIN_EMAILS` on the server).
* **Graph Visualization (`components/graph/RelationshipGraph.tsx`):** React Flow canvas with organic force-directed and hierarchical layouts, macro cluster hulls, 1-hop neighborhood inspection, shortest path tracing, and blast radius impact highlighting.
* **Chat & Source Inspection (`components/chat/ChatInterface.tsx`):** Supports Standard RAG and Graph-Enhanced RAG with clickable line-level source citations (`SourceViewerModal`).

### Backend Layer (`backend/app/`)
* **Authentication & Admin RBAC (`api/v1/auth.py`, `api/deps.py`, `core/security.py`):**
  - BCrypt password hashing and HS256 JWT bearer authentication.
  - `require_admin` checks `user.email.lower()` against configured `settings.admin_email_set`.
* **Health & Liveness (`api/v1/health.py`):**
  - `GET /api/v1/live`: Unauthenticated liveness probe (`{"status": "alive"}`) for container orchestrators.
  - `GET /api/v1/health`: Admin-only readiness probe verifying PostgreSQL connectivity (`SELECT 1`) and reporting provider configuration.
* **Ingestion Pipeline (`ingestion/`):**
  - **Git Cloner:** Shallow clone (`--depth 1`) with branch regex validation (`^[a-zA-Z0-9._/-]+$`) and `--` option terminator.
  - **File Discovery & Filter:** Ignores binaries, `node_modules`, `.git`, build artifacts, and blocks symlinks escaping the clone root.
  - **Chunker & Embeddings:** Line-aware chunking and batched `all-MiniLM-L6-v2` (384-dim) embeddings into `code_chunks.embedding` (`Vector(384)`).
  - **AST/Lexical Graph Extractor (`graph/`):** Extracts modules, classes, functions, calls, imports, and architectural manifest relationships.
* **Hybrid Retrieval (`rag/retriever.py`):**
  - Combines pgvector cosine similarity search and PostgreSQL `tsvector` full-text search (GIN indexed in migration `004`).

---

## 3. Data-Flow & Trust Boundaries

1. **Shared Project Storage House Model:**
   - Repositories, indexed files, chunks, and graph reads are shared across authenticated users in the same Cortex instance (`get_by_id_shared`, `list_all`).
   - Mutating operations (`PATCH /repositories/{id}`, `DELETE /repositories/{id}`, `POST /repositories/{id}/reindex`, `POST /repositories/{id}/graph/reindex`) require `repo.user_id == current_user_id`.
   - `ConversationRepository` isolates chat conversations and message history per `user_id`.
2. **Untrusted Code Isolation:**
   - Cloned repositories are parsed statically (Python `ast` + regex/lexical extractors) and never executed. Temporary clones are removed via `shutil.rmtree` in `pipeline.py`.
3. **Database Schema & Migrations (`backend/alembic/versions/`):**
   - Linear chain: `001_initial_schema` -> `002_relationship_graph` -> `003_project_storage_house` -> `004_hybrid_search_indexes`.
