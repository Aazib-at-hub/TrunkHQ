# TrunkHQ

Cloud SaaS Engineering Intelligence & Project Knowledge Hub.

TrunkHQ helps startups, software agencies, freelancers, and engineering teams understand codebases, onboard new engineers faster, trace architecture dependencies, and query repositories + technical documentation with exact line-level citations.

---

## Architecture & Tech Stack

- **Frontend:** Next.js `16.3.8` (App Router), React `19.2.8`, TypeScript `^5`, Tailwind CSS `^4`, Zustand, TanStack Query, React Flow (`@xyflow/react`), `react-syntax-highlighter`.
- **Backend:** Python `3.12`, FastAPI, SQLAlchemy `2.0` Async (`asyncpg`), Alembic (`001`–`009`), Pydantic `v2`, `slowapi` rate limiting, `structlog`.
- **Database & Hybrid Search:** PostgreSQL `16` + `pgvector` (`Vector(384)` HNSW cosine + PostgreSQL `tsvector` GIN full-text search).
- **Embeddings & LLMs:** Local `sentence-transformers` (`all-MiniLM-L6-v2`, 384d), Google Gemini (`gemini-2.0-flash`), optional OpenAI (`gpt-4o-mini`).

---

## Key Implemented Capabilities

1. **Multi-Tenancy & Organizations (`X-Organization-Id`):**
   - Personal and team `Organization` workspaces with server-enforced RBAC (`owner`, `admin`, `developer`, `viewer`), member management (`/team`), and `audit_logs`.
   - Guided onboarding (`/auth` + onboarding flow) for Individual, Freelancer, Agency, Startup, and Enterprise accounts.
2. **Multi-Repo Projects & GitHub Sync:**
   - Group multiple GitHub repositories under a `Project`, plus HMAC-SHA256 verified GitHub push webhooks (`POST /api/v1/repositories/webhook/github`).
3. **Document Intelligence:**
   - Upload and chunk `.pdf`, `.docx`, `.md`, `.txt`, `.csv`, `.json`, `.yaml`, `.yml`, and `.sql` files per project (`Docs` tab) into `document_chunks` for cross-code + doc retrieval.
4. **Hybrid RAG & SSE Streaming Chat:**
   - Combines pgvector cosine similarity, PostgreSQL full-text search, project documentation context, and 1-hop graph context with randomized `<untrusted_context_...>` prompt boundaries and exact file/line citations (`POST /chat` and `POST /chat/stream`).
5. **Interactive Knowledge Graph:**
   - Python AST + TypeScript/JS + architectural manifest extractors, paginated subgraph slicing (`GET /repositories/{id}/graph`, `GET /projects/{id}/graph`), 1-hop neighbors, BFS path tracing, and blast-radius impact analysis.
6. **SaaS Billing & Usage Metering:**
   - Centralized `plans`, `subscriptions`, and `usage_records` (`ai_queries` metering), `/pricing` and `/billing` UI, and HMAC-verified payment webhook (`POST /api/v1/billing/webhook`).
7. **Enterprise App Shell & Security:**
   - Collapsible sidebar, workspace switcher, `Ctrl+K` command palette, Day/Night theme toggle, admin-only `/system` diagnostics & `/api/v1/health`, public `/api/v1/live` liveness probe, and non-debug `JWT_SECRET_KEY` startup guard.

---

## Quickstart with Docker Compose

1. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Set a strong 64-char JWT_SECRET_KEY, GOOGLE_API_KEY (or OPENAI_API_KEY), and ADMIN_EMAILS
   ```

2. **Start Services:**
   ```bash
   docker compose up -d --build
   ```

3. **Run Database Migrations:**
   ```bash
   docker compose exec backend python -m alembic upgrade head
   ```

4. **Access Endpoints:**
   - Web App: [http://localhost:3000](http://localhost:3000)
   - FastAPI Docs: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
   - Liveness Probe: [http://localhost:8000/api/v1/live](http://localhost:8000/api/v1/live)
   - Admin Health Diagnostics: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health) *(requires admin JWT)*

---

## Local Development Setup

### Backend

```bash
cd backend
python -m venv venv
# Windows: .\venv\Scripts\activate
# Linux/macOS: source venv/bin/activate

pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

> Note: On Windows systems where `alembic.exe` is blocked by Application Control, invoke Alembic via `python -m alembic upgrade head`.

Run unit tests:
```bash
python -m pytest backend\tests\unit -q
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Typecheck, lint, and production build:
```bash
npx tsc --noEmit
npm run lint
npm run build
```

---

## Documentation Index

- [Architecture Overview](docs/ARCHITECTURE.md)
- [Database Schema & Migrations](docs/DATABASE_SCHEMA.md)
- [Multi-Tenancy & RBAC Model](docs/TENANCY_MODEL.md)
- [Implementation Status](docs/IMPLEMENTATION_STATUS.md)
- [Business Model & Pricing](docs/business/cortex_business_model.md)
- [Production Readiness Reports](docs/production-readiness/01_executive_readiness_report.md)
