# TrunkHQ — Current System Map (Phase 0)

**Date:** November 17, 2026  
**Scope:** Actual implemented modules, data models, API routes, and UI views in the repository.

---

## 1. Technology Stack (Observed)

| Layer | Technology / Versions | Source |
| :--- | :--- | :--- |
| **Frontend** | Next.js `16.3.8`, React `19.2.8`, TypeScript `^5`, Tailwind CSS `^4` | `frontend/package.json` |
| **Frontend State & UI** | Zustand `^5.0.15`, TanStack Query `^5.104.0`, `@xyflow/react` `^12.12.0`, `lucide-react`, `react-syntax-highlighter` | `frontend/package.json` |
| **Backend** | Python `3.12` (`>=3.11`), FastAPI `>=0.115.0`, Uvicorn, Pydantic `>=2.7.0` | `backend/pyproject.toml` |
| **Database & Search** | PostgreSQL 16 + `pgvector` (`Vector(384)` HNSW cosine + PostgreSQL `tsvector` GIN), SQLAlchemy `>=2.0.30` (AsyncPG), Alembic `>=1.13.0` | `docker-compose.yml`, `backend/alembic/versions/` |
| **AI & Embeddings** | Local `sentence-transformers` (`all-MiniLM-L6-v2`, 384d), Google Gemini (`google-generativeai`), optional OpenAI (`openai`) | `backend/pyproject.toml`, `backend/app/core/config.py` |
| **Auth & Logging** | `python-jose` (HS256 JWT), `passlib[bcrypt]`, `structlog`, `slowapi` (declared, not yet wired) | `backend/pyproject.toml` |

---

## 2. Database Schema (`backend/app/models/` & `backend/alembic/versions/`)

Linear migration chain: `001_initial_schema` -> `002_relationship_graph` -> `003_project_storage_house` -> `004_hybrid_search_indexes`.

| Table | Model File | Key Columns & Ownership |
| :--- | :--- | :--- |
| `users` | `models/user.py` | `id`, `email`, `username`, `hashed_password` (no `account_type`, `email_verified`, or OAuth fields) |
| `repositories` | `models/repository.py` | `id`, `user_id` (FK `users.id`), `name`, `github_url`, `branch`, `description`, `tags` (JSONB), `links` (JSONB), `notes`, `status`, `file_count`, `chunk_count` |
| `files` | `models/file.py` | `id`, `repository_id` (FK `repositories.id`), `path`, `language`, `content_hash`, `line_count` |
| `code_chunks` | `models/chunk.py` | `id`, `file_id`, `repository_id`, `content`, `start_line`, `end_line`, `embedding` (`Vector(384)`) |
| `conversations` | `models/conversation.py` | `id`, `repository_id`, `user_id`, `title` |
| `messages` / `message_sources` | `models/message.py` | `id`, `conversation_id`, `role`, `content`; `message_sources` links `chunk_id`, `file_path`, `start_line`, `end_line`, `similarity_score` |
| `graph_nodes` / `graph_edges` / `graph_index_runs` | `models/graph.py` | `id`, `workspace_id` (currently `repo.user_id`), `repository_id`, `node_type`/`edge_type`, `stable_key`, `properties`, `source_kind` |

---

## 3. Backend API Surface (`backend/app/api/v1/`)

| Router | Endpoints | Auth / Scoping |
| :--- | :--- | :--- |
| `auth.py` | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` | Public register/login; JWT bearer on `/me` (`is_admin` computed from `ADMIN_EMAILS`) |
| `repositories.py` | `POST /repositories/import`, `GET /repositories`, `PATCH /repositories/{id}`, `GET /repositories/{id}`, `GET /repositories/{id}/status`, `GET /repositories/{id}/files`, `GET /repositories/{id}/files/{file_id}/content`, `POST /repositories/{id}/reindex`, `DELETE /repositories/{id}` | Shared read across all authenticated users (`list_all`, `get_by_id_shared`); owner-only (`repo.user_id == current_user_id`) for `PATCH`, `DELETE`, `reindex` |
| `chat.py` | `POST /chat`, `GET /chat/conversations`, `GET /chat/conversations/{id}`, `DELETE /chat/conversations/{id}` | Conversations filtered by `user_id`; retrieval reads across shared repos |
| `graph.py` | `GET /repositories/{id}/graph`, `GET .../nodes/{node_id}`, `GET .../nodes/{node_id}/neighbors`, `POST .../paths`, `POST .../impact`, `GET .../search`, `GET .../insights`, `GET .../status`, `POST .../reindex` | Shared read scoped to `repository_id`; `reindex` requires `repo.user_id == current_user_id` |
| `health.py` | `GET /live`, `GET /health` | `/live` unauthenticated; `/health` gated by `require_admin` |

---

## 4. Frontend Routes & Components (`frontend/`)

| Route | Purpose |
| :--- | :--- |
| `/` (`app/page.tsx`) | Unauthenticated Cloud SaaS landing page + Authenticated Project Storage House dashboard (search, tag filter, import modal, delete modal) |
| `/pricing` (`app/pricing/page.tsx`) | Cloud SaaS pricing tiers (Free, Pro, Team, Enterprise), BYOK & hybrid usage overview |
| `/projects/[id]` (`app/projects/[id]/page.tsx`) | Project workspace with 3 tabs: **Details** (`ProjectDetailsPanel`), **Chat** (`ChatInterface` + `SourceViewerModal`), **Graph** (`RelationshipGraph` with React Flow, `GraphToolbar`, `GraphNodeDetails`, `ImpactPanel`, `GraphInsightsPanel`) |
| `/system` (`app/system/page.tsx`) | Admin-only backend health & per-repo/graph indexing diagnostics |
