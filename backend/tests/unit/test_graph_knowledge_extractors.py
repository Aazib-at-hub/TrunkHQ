"""
Unit tests for extended knowledge graph extractors:
- SQL DDL tables & foreign key references
- OpenAPI / Swagger YAML & JSON endpoints
- Architecture Decision Records (ADR)
- Mermaid architecture diagrams
"""

from __future__ import annotations

import uuid

from app.graph.extractors.manifest import ManifestGraphExtractor
from app.models.graph import EdgeType, NodeType


def test_sql_schema_extraction() -> None:
    repo_id = uuid.uuid4()
    sql = """
    CREATE TABLE IF NOT EXISTS public.organizations (
        id UUID PRIMARY KEY
    );
    CREATE TABLE projects (
        id UUID PRIMARY KEY,
        organization_id UUID REFERENCES public.organizations(id)
    );
    """
    res = ManifestGraphExtractor().extract(repo_id, "db/schema.sql", sql)
    table_names = {n.name for n in res.nodes if n.node_type == NodeType.TABLE}
    assert table_names == {"organizations", "projects"}
    assert any(e.edge_type == EdgeType.DEFINES for e in res.edges)
    assert any(e.edge_type == EdgeType.DEPENDS_ON for e in res.edges)


def test_openapi_spec_extraction() -> None:
    repo_id = uuid.uuid4()
    spec = """
openapi: 3.0.3
info:
  title: Cortex API
  version: 1.0.0
paths:
  /api/v1/projects:
    get:
      summary: List projects
    post:
      summary: Create project
"""
    res = ManifestGraphExtractor().extract(repo_id, "docs/openapi.yaml", spec)
    endpoints = {n.name for n in res.nodes if n.node_type == NodeType.API_ENDPOINT}
    assert endpoints == {"GET /api/v1/projects", "POST /api/v1/projects"}
    assert any(e.edge_type == EdgeType.EXPOSES for e in res.edges)


def test_adr_and_mermaid_diagram_extraction() -> None:
    repo_id = uuid.uuid4()
    adr = """# ADR-001: Multi-Tenant Organization Boundary

## Decision
Use PostgreSQL organization_id scoping across all repositories.

```mermaid
flowchart LR
  Frontend[Next.js] --> Backend[FastAPI]
  Backend --> Postgres[(PostgreSQL)]
```
"""
    res = ManifestGraphExtractor().extract(repo_id, "docs/adr/001-tenancy.md", adr)
    decisions = [n for n in res.nodes if n.node_type == NodeType.DECISION]
    services = {n.name for n in res.nodes if n.node_type == NodeType.SERVICE}
    assert len(decisions) == 1
    assert "ADR-001" in decisions[0].name
    assert {"Frontend", "Backend", "Postgres"}.issubset(services)
    assert any(
        e.edge_type == EdgeType.DEPENDS_ON and e.evidence_kind == "diagram_mermaid"
        for e in res.edges
    )
