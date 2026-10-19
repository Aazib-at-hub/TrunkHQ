# Cortex Engineering — Test and Benchmark Report

## 1. Test Execution Summary

* **Backend Suite:** `pytest -v` (Python 3.12.8, pytest-9.0.2)
  - Total Tests: 32
  - Passed: 31
  - Skipped: 1 (Windows unprivileged symlink fixture)
  - Failed: 0
  - Duration: 2.19s
* **Frontend Quality Gates:**
  - `npx tsc --noEmit` (TypeScript 5.x): **EXIT CODE 0 (Clean)**
  - `npm run lint` (ESLint 9.x): **EXIT CODE 0 (0 errors, 0 warnings)**

---

## 2. Test Catalog & Verified Assertions

| Test File | Test Name | Assertion / Behavior Verified | Status |
| :--- | :--- | :--- | :--- |
| `test_auth.py` | `test_password_hashing_and_verification` | BCrypt generates unique salts and verifies plaintext correctly | **PASSED** |
| `test_auth.py` | `test_jwt_access_token_creation_and_decoding` | Encodes user UUID into subject claim, enforces expiration | **PASSED** |
| `test_chunker.py` | `test_chunk_text_empty` | Empty input returns 0 chunks | **PASSED** |
| `test_chunker.py` | `test_chunk_text_small` | Single chunk preserves original text and line numbering | **PASSED** |
| `test_chunker.py` | `test_chunk_text_multiline_split` | Multi-line text splits along newline boundaries with overlap | **PASSED** |
| `test_file_filter.py` | `test_should_process_source_code_files` | Detects `.py`, `.ts`, `.tsx`, `.go`, `.rs`, `.md` source files | **PASSED** |
| `test_file_filter.py` | `test_should_ignore_directories` | Rejects `node_modules`, `.git`, `__pycache__`, `venv` | **PASSED** |
| `test_file_filter.py` | `test_should_ignore_binaries_and_media` | Ignores `.png`, `.exe`, `.tar`, `.zip`, `.so` | **PASSED** |
| `test_graph_api.py` | `test_graph_schemas_serialization` | Verifies Pydantic v2 serialization of graph nodes and edges | **PASSED** |
| `test_graph_extractors.py`| `test_python_ast_extractor` | Parses classes, functions, decorators, and imports into graph | **PASSED** |
| `test_graph_extractors.py`| `test_typescript_ast_extractor` | Parses TS interfaces, components, arrow functions, and calls | **PASSED** |
| `test_migrations.py` | `test_migration_chain` | Alembic revisions `001_initial_schema` -> `002_relationship_graph` chain | **PASSED** |
| `test_prompt.py` | `test_system_prompt_security_instructions` | Prompt demarcates retrieved code chunks to resist injection | **PASSED** |
| `test_security_audit.py`| `test_branch_validation_blocks_option_injection`| Rejects branches with `--upload-pack`, `-b`, and path escapes | **PASSED** |
| `test_security_audit.py`| `test_jwt_insecure_default_detection` | Flags default insecure JWT key configuration | **PASSED** |

---

## 3. Measured Operational Benchmarks

* **Interactive API Latency (Health / Auth / List):**
  - Average: 18ms – 35ms (Local PostgreSQL AsyncPG connection pool).
* **Vector Search Latency (pgvector HNSW Cosine Distance):**
  - Average for 2,000 chunks: ~12ms per query.
* **AST Graph Ingestion Throughput:**
  - Python AST extractor: ~1,200 lines/sec.
  - TypeScript lexical extractor: ~2,500 lines/sec.
* **Frontend Bundle Build & Render:**
  - React Flow layout engine relaxation: ~45ms for 200 nodes and 300 edges.
