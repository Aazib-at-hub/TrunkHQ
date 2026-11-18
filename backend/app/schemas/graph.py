"""
TrunkHQ — Pydantic Schemas for Relationship Graph.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GraphNodeSchema(BaseModel):
    """Canonical graph node representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    node_type: str
    stable_key: str
    name: str
    qualified_name: Optional[str] = None
    description: Optional[str] = None
    properties: dict[str, Any] = Field(default_factory=dict)
    source_kind: str = "code"
    source_uri: Optional[str] = None
    created_at: Optional[datetime] = None


class GraphEdgeSchema(BaseModel):
    """Directed, typed relationship between two graph nodes."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_node_id: UUID
    target_node_id: UUID
    edge_type: str
    confidence: float = 1.0
    evidence_kind: str = "static"
    source_uri: Optional[str] = None
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphSliceResponse(BaseModel):
    """Bounded graph response containing nodes and connecting edges."""

    repository_id: UUID
    nodes: list[GraphNodeSchema]
    edges: list[GraphEdgeSchema]
    total_nodes: int
    total_edges: int


class NodeNeighborsResponse(BaseModel):
    """1-hop neighborhood for a specific node."""

    node: Optional[GraphNodeSchema] = None
    outgoing_edges: list[GraphEdgeSchema] = Field(default_factory=list)
    incoming_edges: list[GraphEdgeSchema] = Field(default_factory=list)
    neighbors: list[GraphNodeSchema] = Field(default_factory=list)


class PathStepSchema(BaseModel):
    """A single step in a graph traversal path."""

    node: Optional[GraphNodeSchema] = None
    edge: Optional[GraphEdgeSchema] = None


class FindPathRequest(BaseModel):
    """Request payload for finding a relationship path between two entities."""

    source_id: UUID
    target_id: UUID
    max_depth: int = Field(default=5, ge=1, le=10)


class FindPathResponse(BaseModel):
    """Path traversal sequence connecting source and target nodes."""

    found: bool
    length: int
    steps: list[PathStepSchema]


class ImpactRequest(BaseModel):
    """Request to compute upstream/caller blast radius for an entity."""

    node_id: UUID
    max_depth: int = Field(default=3, ge=1, le=5)
    edge_types: Optional[list[str]] = None
    include_tests: bool = True


class ImpactResponse(BaseModel):
    """Blast radius and affected downstream/caller entities."""

    root: Optional[GraphNodeSchema] = None
    impacted_nodes: list[GraphNodeSchema]
    edges: list[GraphEdgeSchema]
    depth_levels: dict[str, int]
    total_impacted: int


class GraphStatusResponse(BaseModel):
    """Status of the repository relationship graph index."""

    repository_id: UUID
    status: str
    nodes_count: int = 0
    edges_count: int = 0
    nodes_created: int = 0
    edges_created: int = 0
    nodes_deleted: int = 0
    edges_deleted: int = 0
    extractor_version: Optional[str] = None
    error_summary: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class HubNodeInsight(BaseModel):
    """Architectural centrality and connectivity insight for a graph node."""

    node: GraphNodeSchema
    in_degree: int
    out_degree: int
    total_degree: int
    role: str = "standard"


class KeyModuleInsight(BaseModel):
    """Module breakdown insight."""

    module: str
    entity_count: int


class GraphInsightsResponse(BaseModel):
    """Comprehensive architectural and engineering knowledge insights."""

    repository_id: UUID
    total_nodes: int
    total_edges: int
    domains: dict[str, int]
    hub_nodes: list[HubNodeInsight]
    entrypoints: list[HubNodeInsight]
    key_modules: list[KeyModuleInsight]


class ImpactReportRequest(BaseModel):
    """Request for Cortex Impact Intelligence structured report."""

    node_id: UUID
    max_depth: int = Field(default=3, ge=1, le=5)
    change_description: Optional[str] = Field(default=None, max_length=1000)


class AffectedComponentItem(BaseModel):
    """Single affected component in an impact report."""

    node: GraphNodeSchema
    depth: int
    evidence_kind: str = "static"
    confidence: float = 1.0


class ImpactReportResponse(BaseModel):
    """Evidence-backed Cortex Impact Intelligence report."""

    root: GraphNodeSchema
    summary: str
    affected_components: list[AffectedComponentItem]
    related_documents: list[str]
    potential_risks: list[str]
    uncertainty_note: str
    edges: list[GraphEdgeSchema]
    total_impacted: int


class StaleDocFinding(BaseModel):
    document_id: UUID
    document_title: str
    file_name: str
    reason: str
    missing_references: list[str] = []


class ArchitectureDriftFinding(BaseModel):
    kind: str
    entity: str
    detail: str


class IntegrationRiskFinding(BaseModel):
    severity: str
    title: str
    detail: str


class EngineeringIntelligenceResponse(BaseModel):
    """Level 3 Engineering Intelligence report for a project."""

    project_id: UUID
    summary: str
    stale_docs: list[StaleDocFinding]
    architecture_drift: list[ArchitectureDriftFinding]
    integration_risks: list[IntegrationRiskFinding]
    uncertainty_note: str

