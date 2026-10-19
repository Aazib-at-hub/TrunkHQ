# Cortex Engineering — Architecture and Data-Flow Report

## 1. Verified Architecture Overview

```
                                  +-----------------------------+
                                  |   Next.js 16 Web Frontend   |
                                  |  (React 19, React Flow,     |
                                  |   Zustand, Tailwind CSS)    |
                                  +--------------+--------------+
                                                 | HTTPS / REST
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
| Ingestion & AST  |                   | Semantic RAG     |                   | Relationship Graph |
| Pipeline Engine  |                   | Retrieval Engine |                   | Query & Blast Rad. |
+--------+---------+                   +--------+---------+                   +---------+----------+
         |                                      |                                       |
         v                                      v                                       v
+--------------------------------------------------------------------------------------------------+
|                              PostgreSQL 16 + pgvector Database                                   |
| - users               - repositories         - files             - code_chunks (HNSW 384d)       |
| - conversations       - messages             - message_sources   - graph_nodes                   |
| - graph_edges         - graph_index_runs                                                         |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. Component Responsibilities

### Frontend Layer (`frontend/`)
* **State Management:** Zustand auth store caching JWT tokens in memory with persistent hydration.
* **Graph Visualization:** React Flow canvas leveraging dynamic force relaxation physics with collision push for high-density symbol clusters.
* **Context Mode Toggle:** Allows switching between Standard Vector RAG and Graph-Enhanced AST Neighborhood RAG.
* **Live Ingestion Feedback:** Real-time polling against backend repository status endpoints.

### Backend Layer (`backend/app/`)
* **Authentication (`api/v1/auth.py`, `core/security.py`):**
  - BCrypt password hashing.
  - Stateless JWT token encoding with subject claim user UUID validation.
* **Ingestion Pipeline (`ingestion/`):**
  - **Git Cloner:** Shallow clone (`--depth 1`) using sanitized subprocess arguments with option terminator (`--`).
  - **File Discovery & Filter:** Prunes binaries, `node_modules`, `dist`, `.git`, test artifacts, and verifies symlink targets stay within repository bounds.
  - **Chunker:** Sliding window character/line chunker with configurable overlap and newline preservation.
  - **Vector Embeddings:** Batched embedding via `all-MiniLM-L6-v2` (384 dimensions) persisted to pgvector.
  - **AST Graph Extractor (`graph/`):** Extracts code declarations, functions, classes, and calls into directed edges.

---

## 3. Data-Flow Lifecycle: Repository Import to Grounded Answer

```
[User Import Request]
        |
        v
[Validate URL & Branch] ---> (Rejects flag injection e.g. --upload-pack)
        |
        v
[git clone --depth 1]   ---> Isolated temporary directory: backend/repos/<repo_id>
        |
        v
[File Discovery]        ---> Rejects symlinks pointing outside clone root
        |
        v
[AST Extraction]        ---> Generates stable graph nodes & edges
        |
        v
[Chunking & Embeddings] ---> 384-dimensional dense vectors
        |
        v
[Atomic Purge & Save]   ---> Idempotently deletes old records, saves new files & chunks
        |
        v
[Cleanup Disk]          ---> shutil.rmtree(clone_dest)
        |
        v
[Status -> READY]       ---> Unlocks Chat & Relationship Graph
```

---

## 4. Trust Boundaries & Security Enforcements

1. **User / Tenant Isolation:**
   - Every API request authenticates via JWT `Bearer` token.
   - Every database query for repositories, files, chunks, conversations, or graph entities filters by `repository.user_id == current_user_id`.
   - Cross-tenant data leakage is prevented at both the service layer and SQL statement level.
2. **Untrusted Code Execution:**
   - Cloned code is never executed. Only parsed statically via Python AST and lexical regex tokenizers.
3. **Prompt Injection Mitigations:**
   - User inputs and retrieved source snippets are strictly demarcated within the system prompt templates in `app/rag/prompt.py`.
