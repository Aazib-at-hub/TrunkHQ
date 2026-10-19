# Cortex Engineering — Production Deployment Runbook

## 1. Prerequisites & Environment Dependencies

* **Runtime:** Python 3.12+, Node.js 20+ (LTS)
* **Database:** PostgreSQL 16+ with `pgvector` extension enabled (`CREATE EXTENSION IF NOT EXISTS vector;`)
* **Git:** Git CLI 2.30+ installed on system PATH
* **Memory & Storage:**
  - Minimum 4 GB RAM (8 GB recommended for local embedding model)
  - 20 GB SSD storage for temporary clone directories and PostgreSQL tables

---

## 2. Environment Configuration Matrix

Ensure the following variables are defined in production `.env`:

```env
# Database
DATABASE_URL=postgresql+asyncpg://cortex_user:secure_password@postgres-host:5432/cortex_prod
DATABASE_URL_SYNC=postgresql://cortex_user:secure_password@postgres-host:5432/cortex_prod

# Authentication (MANDATORY: Generate a 64-char random key)
JWT_SECRET_KEY=e4f8a32b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440

# LLM & AI Providers
LLM_PROVIDER=google
LLM_MODEL=gemini-2.0-flash
GOOGLE_API_KEY=AIzaSy...

# Embedding Provider
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Ingestion Constraints
MAX_FILE_SIZE_BYTES=1048576
CHUNK_SIZE=1500
CHUNK_OVERLAP=200
REPO_CLONE_DIR=repos

# Production Security
DEBUG=False
LOG_LEVEL=INFO
CORS_ORIGINS=https://app.cortexengineering.io
```

---

## 3. Database Migration Sequence

Run database migrations using Alembic in order:

```bash
cd backend
# 1. Verify connection and current revision
alembic current

# 2. Upgrade to head
alembic upgrade head
```

---

## 4. Production Service Launch

### Backend Service (FastAPI / Uvicorn)
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend Service (Next.js Standalone / Node)
```bash
cd frontend
npm run build
npm run start
```

---

## 5. Post-Deployment Smoke Verification

1. **Health Check:**
   ```bash
   curl -s http://localhost:8000/api/v1/health | jq .
   # Expected: {"status": "healthy", "database": "connected"}
   ```
2. **User Registration & Login:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@cortex.internal","username":"admin","password":"StrongPassword123!"}'
   ```
3. **Repository Import Verification:**
   Import a small verified test repo (e.g. `https://github.com/pallets/flask`). Verify status transitions from `CLONING` $\rightarrow$ `INDEXING` $\rightarrow$ `READY`.

---

## 6. Backup & Recovery Procedure

### Automated Backup Command
```bash
pg_dump -h postgres-host -U cortex_user -F c -b -v -f cortex_backup_$(date +%Y%m%d_%H%M%S).dump cortex_prod
```

### Restore Procedure
```bash
# 1. Recreate clean target database
dropdb -h postgres-host -U cortex_user cortex_prod
createdb -h postgres-host -U cortex_user cortex_prod

# 2. Restore pgvector extension and data
pg_restore -h postgres-host -U cortex_user -d cortex_prod -v cortex_backup_XXXX.dump
```
