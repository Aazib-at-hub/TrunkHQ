# TrunkHQ — Intelligence Strategy & Flagship Roadmap

**Positioning:** *The intelligence layer for modern software engineering.*

## 1. Three Intelligence Levels

| Level | Capability | Status |
| :---: | :--- | :--- |
| **1 — Contextual Understanding** | Hybrid RAG (code + docs), line-level citations, architecture summaries | **Implemented** |
| **2 — Graph-Based Reasoning** | `GraphReasoningService`, query-aware multi-hop impact traversal, `Cortex Impact Intelligence` reports (`/graph/impact-report`) | **Implemented (Core)** |
| **3 — Engineering Intelligence** | Stale-doc detection, architecture drift alerts, proactive integration risk reports (`/projects/{id}/intelligence`) | **Implemented (Core)** |

## 2. Flagship Feature: Cortex Impact Intelligence

- **Endpoint:** `POST /api/v1/repositories/{repo_id}/graph/impact-report`
- **Output:** Affected components with hop depth & evidence kind, related project documents, deterministic breaking-change risks (API endpoints, DB tables, missing tests), uncertainty disclosure, and impact subgraph edges.
