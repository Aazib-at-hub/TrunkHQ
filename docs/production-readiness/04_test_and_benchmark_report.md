# TrunkHQ — Test and Verification Report

**Verification Date:** November 14, 2026  

---

## 1. Automated Verification Summary (Observed)

| Check | Command | Latest Observed Result |
| :--- | :--- | :--- |
| **Backend Unit Tests** | `python -m pytest backend\tests\unit -q` | **`51 passed, 1 skipped in 2.02s`** (exit code `0`) |
| **Frontend TypeScript** | `cd frontend; npx tsc --noEmit` | **Exit code `0`** (0 type errors) |
| **Frontend ESLint** | `cd frontend; npm run lint` | **Exit code `0`** (`0 errors, 1 warning`: `react-hooks/exhaustive-deps` in `ChatInterface.tsx:118`) |

> Note: The single skipped test in `backend/tests/unit` is the Windows unprivileged symlink fixture in `test_security_audit.py`.

---

## 2. Test Suite Coverage Map

- `test_auth.py`: Password hashing/verification (BCrypt), JWT creation/decoding, `require_admin` RBAC checks.
- `test_chunker.py`: Empty, small, and multi-line sliding-window chunking.
- `test_file_filter.py`: Language detection, ignored directories (`node_modules`, `.git`, etc.), binary/media exclusion.
- `test_graph_api.py`: Graph Pydantic v2 schemas and API route registration.
- `test_graph_extractors.py`: Python AST and TypeScript lexical graph extraction.
- `test_migrations.py`: Alembic linear revision chain (`001` -> `002` -> `003` -> `004`).
- `test_phase2_rag.py`: Phase 2 hybrid retrieval and RAG context assembly unit tests.
- `test_project_storage_house.py`: Shared read access, owner-only mutation (`PATCH`/`DELETE`/reindex), tag normalization.
- `test_prompt.py`: System/user prompt construction and source demarcation.
- `test_retrieval_citation_eval.py`: Retrieval citation formatting and line-range evaluation.
- `test_security_audit.py`: Git branch option injection rejection, symlink escape protection, JWT insecure default detection.
- `test_security_hardening.py` *(added in this audit)*:
  - `test_reindex_graph_rejects_non_owner` (`403 ForbiddenError`)
  - `test_graph_repo_rejects_cross_repository_nodes` (`get_neighbors`, `find_path`, `get_impact` scoped to `repository_id`)
  - `test_lifespan_refuses_insecure_jwt_in_non_debug_mode` (`RuntimeError` fail-fast)
  - `test_liveness_endpoint_and_security_headers` (`/api/v1/live` + security response headers)
- `test_url_validation.py`: GitHub URL validation.

---

## 3. Unverified Tests & Benchmarks (Not Executed)
- **Integration / E2E Tests:** No automated Playwright/Cypress E2E suite or live PostgreSQL integration test run was executed in this audit.
- **Load & Latency Benchmarks:** No staging load test (concurrent imports, concurrent chat/RAG requests, or p95/p99 latency measurement) was executed; prior latency estimates are omitted until measured on target hardware.
- **Alembic Clean-DB Roundtrip:** `alembic upgrade head` -> `downgrade` -> `upgrade` against a fresh PostgreSQL instance was not executed (note: `004_hybrid_search_indexes.py` `downgrade()` drops `ix_code_chunks_embedding_hnsw` from `001`).
