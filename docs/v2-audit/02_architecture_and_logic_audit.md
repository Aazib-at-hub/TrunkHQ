# 02. TrunkHQ V2 — Architecture & Logic Audit

> **Scope:** Audit of `backend/app/` covering ingestion, chunking, embeddings, retrieval, decision/reranking, RAG generation, security, and operational reliability.

---

## 1. Current Architecture Summary

- **Framework & Storage:** FastAPI (`backend/app/main.py`) + PostgreSQL with `pgvector` (`backend/app/models/`).
- **Ingestion:** `RepositoryService._trigger_ingestion` spawns an in-process `asyncio.create_task` running `IngestionPipeline.run` (`backend/app/ingestion/pipeline.py`).
- **Retrieval & Generation:** `ChatService.ask_question` (`backend/app/services/chat_service.py`) embeds the query, runs cosine similarity search on `CodeChunk`, optionally appends 1-hop graph neighbors, and calls `RAGGenerator.generate_answer` (`backend/app/rag/generator.py`).

---

## 2. Core Intelligence & Logic Gaps

### A. Ingestion & Repository Understanding
1. **No Incremental Indexing:** `RepositoryFile.content_hash` is computed and stored (`extractor.py`), but `IngestionPipeline.run` always deletes all `RepositoryFile` rows (`file_dao.delete_by_repository`) and re-embeds every file from scratch.
2. **No Repository-Level Architectural Summary:** Cortex does not generate or store a structured overview (frameworks, entrypoints, API surface, DB models, directory roles) at ingestion time.
3. **Hardcoded 2000-File Cap & Line-Only Chunking:** `discovery.py` caps at `max_total_files = 2000`; `chunker.py:chunk_text` splits purely by character count (`1500` chars, `200` overlap) on line boundaries without AST/symbol boundaries, splitting functions/classes mid-body.
4. **Unused `RepositoryStatus` Stages:** `DISCOVERING`, `FILTERING`, `EXTRACTING`, `CHUNKING`, `EMBEDDING` are declared in `models/repository.py:26-30` but never set by `IngestionPipeline`.

### B. Retrieval & RAG Pipeline
1. **Pure Vector Search (No Hybrid / Symbol Search):** `RetrieverService.retrieve` (`backend/app/retrieval/retriever.py`) uses only `CodeChunk.embedding.cosine_distance(query_vector)`. Exact symbol names, error codes, endpoints, and config keys are poorly served without full-text (`tsvector`/BM25) or symbol-index matching.
2. **Graph-Enhanced Mode Uses Naive Word Splitting:** `ChatService.ask_question` (`chat_service.py:109-119`) splits the question on whitespace (`len > 3`, first 4 words) and calls `GraphRepository.search_nodes`. Stopwords (e.g., `"does"`, `"work"`, `"this"`) consume slots, and no query intent/entity extraction exists.
3. **JEV Decision Layer Is a Stub:** `get_decision_service()` (`backend/app/decision/__init__.py:15-17`) ignores `Settings.jev_enabled` and always returns `SimpleDecisionService`, whose `filter_and_rank` returns `chunks` untouched.
4. **No Multi-Turn History in RAG:** `ChatService` saves messages to `conversations`/`messages`, but `RAGGenerator.generate_answer` (`rag/generator.py:46`) receives only the current `question`—follow-up questions (`"what about its tests?"`) have zero conversation memory.
5. **No Citation Verification or Uncertainty Gate:** `RAGGenerator.generate_answer` records **all** retrieved chunks as `MessageSource` citations regardless of whether the LLM actually used them, and still invokes the LLM when `retrieved_chunks` is empty.
6. **No Token Budget Guard:** `build_user_prompt` (`rag/prompt.py:28`) concatenates all chunks + graph context without bounding total prompt tokens.

---

## 3. Critical Bugs, Bottlenecks & Production Risks

| Severity | Issue | Location | Impact |
| :--- | :--- | :--- | :--- |
| **High** | **Hardcoded `Vector(384)`** | `backend/app/models/chunk.py:50` | Switching `EMBEDDING_PROVIDER=openai` (`1536` dims) crashes DB inserts and queries. |
| **High** | **Missing pgvector Index** | `backend/app/models/chunk.py:60-63` | No HNSW/IVFFlat index on `CodeChunk.embedding`; every query performs a sequential scan. |
| **High** | **In-Process `asyncio.create_task`** | `backend/app/services/repository_service.py:31,91-108` | Server restart leaves repos stuck in `CLONING`/`INDEXING`. `reindex_repository` (`line 166`) does not guard `"PENDING"`, allowing concurrent duplicate jobs. |
| **High** | **Global `genai.configure` + Unsafe `.text`** | `backend/app/llm/google_llm.py:31,46` | Mutates global SDK state per call; `response.text` raises `ValueError` on safety-blocked/empty responses. |
| **Medium** | **Stale Data on Empty Reindex** | `backend/app/ingestion/pipeline.py:91-104` | Returns early with `READY` (`file_count=0`) without calling `file_dao.delete_by_repository`, leaving old chunks in DB. |
| **Medium** | **Windows Cleanup & Subprocess Bugs** | `backend/app/ingestion/cloner.py:116-158`, `pipeline.py:323` | `proc.kill()` without `await proc.wait()`; `shutil.rmtree(..., ignore_errors=True)` leaves read-only `.git` pack files on Windows instead of using `_force_rm`. |
| **Medium** | **N+1 DB Flush in Ingestion** | `backend/app/ingestion/pipeline.py:189-194` | `file_dao.create` flushes and refreshes each `RepositoryFile` one by one instead of bulk inserting. |
| **Medium** | **OpenAI Embedding Batching** | `backend/app/embeddings/openai_embeddings.py:48` | No token-limit batching or retry/backoff on rate limits (`429`). |
| **Low** | **Unused `github_token` & Dead Code** | `config.py:36`, `chunk_repo.py:53-75` | `Settings.github_token` is never passed to `cloner.py` (private repos fail); `ChunkRepository.search_similar` is unused. |
| **Low** | **Missing `typing` Imports** | `pipeline.py:215,242`, `generator.py:51`, `prompt.py:31` | `Optional` and `Any` used in annotations without import (only masked by `from __future__ import annotations`). |

