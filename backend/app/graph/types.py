"""
TrunkHQ — Relationship Graph Extraction Data Structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ExtractedNode:
    """An extracted entity ready for graph insertion."""

    node_type: str
    stable_key: str
    name: str
    qualified_name: Optional[str] = None
    description: Optional[str] = None
    properties: dict[str, Any] = field(default_factory=dict)
    source_kind: str = "code"
    source_uri: Optional[str] = None
    content_hash: Optional[str] = None


@dataclass
class ExtractedEdge:
    """An extracted relationship connecting two entities by stable_key."""

    source_key: str
    target_key: str
    edge_type: str
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    evidence_kind: str = "static"
    source_uri: Optional[str] = None
    content_hash: Optional[str] = None


@dataclass
class ExtractionResult:
    """Aggregated nodes and edges produced by an extractor."""

    nodes: list[ExtractedNode] = field(default_factory=list)
    edges: list[ExtractedEdge] = field(default_factory=list)
