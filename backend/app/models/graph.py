"""
TrunkHQ — Unified Relationship Graph Models.

Defines GraphNode, GraphEdge, and GraphIndexRun entities for representing
code entities, architectural components, engineering knowledge, and their relationships.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class NodeType:
    """Standard controlled vocabulary for graph nodes."""

    # Code domain
    PROJECT = "project"
    REPOSITORY = "repository"
    DIRECTORY = "directory"
    FILE = "file"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    SYMBOL = "symbol"
    TEST = "test"

    # Architecture domain
    SERVICE = "service"
    API_ENDPOINT = "api_endpoint"
    DATABASE = "database"
    TABLE = "table"
    QUEUE = "queue"
    EXTERNAL_SYSTEM = "external_system"
    DEPLOYMENT = "deployment"
    CONFIG = "config"

    # Knowledge domain
    DOCUMENT = "document"
    REQUIREMENT = "requirement"
    DECISION = "decision"
    ISSUE = "issue"
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    INCIDENT = "incident"

    ALL_CODE = {REPOSITORY, DIRECTORY, FILE, MODULE, CLASS, FUNCTION, METHOD, SYMBOL, TEST}
    ALL_ARCHITECTURE = {SERVICE, API_ENDPOINT, DATABASE, TABLE, QUEUE, EXTERNAL_SYSTEM, DEPLOYMENT, CONFIG}
    ALL_KNOWLEDGE = {DOCUMENT, REQUIREMENT, DECISION, ISSUE, COMMIT, PULL_REQUEST, INCIDENT}


class EdgeType:
    """Standard controlled vocabulary for typed graph relationships."""

    # Structural & Code
    CONTAINS = "CONTAINS"
    DEFINES = "DEFINES"
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    IMPLEMENTS = "IMPLEMENTS"
    TESTS = "TESTS"

    # Architecture & Services
    DEPENDS_ON = "DEPENDS_ON"
    EXPOSES = "EXPOSES"
    READS_FROM = "READS_FROM"
    WRITES_TO = "WRITES_TO"

    # Knowledge & Traceability
    IMPLEMENTS_REQUIREMENT = "IMPLEMENTS_REQUIREMENT"
    DOCUMENTS = "DOCUMENTS"
    BELONGS_TO = "BELONGS_TO"
    INTRODUCED_BY = "INTRODUCED_BY"
    TRACKED_BY = "TRACKED_BY"
    SUPERSEDES = "SUPERSEDES"


class GraphIndexRun(Base, UUIDMixin, TimestampMixin):
    """Tracks graph extraction runs for a repository snapshot."""

    __tablename__ = "graph_index_runs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )

    commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="RUNNING", nullable=False)

    nodes_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nodes_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nodes_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    edges_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    edges_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    edges_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extractor_version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_graph_index_runs_repo_status", "workspace_id", "repository_id", "status"),
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("status", "RUNNING")
        kwargs.setdefault("nodes_created", 0)
        kwargs.setdefault("nodes_updated", 0)
        kwargs.setdefault("nodes_deleted", 0)
        kwargs.setdefault("edges_created", 0)
        kwargs.setdefault("edges_updated", 0)
        kwargs.setdefault("edges_deleted", 0)
        kwargs.setdefault("extractor_version", "1.0")
        kwargs.setdefault("schema_version", "1.0")
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<GraphIndexRun id={self.id} repo_id={self.repository_id} "
            f"status={self.status} nodes={self.nodes_created} edges={self.edges_created}>"
        )


class GraphNode(Base, UUIDMixin, TimestampMixin):
    """A canonical entity in the unified relationship graph."""

    __tablename__ = "graph_nodes"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )

    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    stable_key: Mapped[str] = mapped_column(String(512), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    qualified_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    source_kind: Mapped[str] = mapped_column(String(50), default="code", nullable=False)
    source_uri: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    source_commit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Relationships
    outgoing_edges = relationship(
        "GraphEdge",
        foreign_keys="GraphEdge.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    incoming_edges = relationship(
        "GraphEdge",
        foreign_keys="GraphEdge.target_node_id",
        back_populates="target_node",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "stable_key", name="uq_graph_nodes_workspace_stable_key"),
        Index("ix_graph_nodes_workspace_type", "workspace_id", "node_type"),
        Index("ix_graph_nodes_workspace_repo", "workspace_id", "repository_id"),
        Index("ix_graph_nodes_workspace_name", "workspace_id", "name"),
        Index("ix_graph_nodes_properties", "properties", postgresql_using="gin"),
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("status", "active")
        kwargs.setdefault("source_kind", "code")
        kwargs.setdefault("properties", {})
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<GraphNode id={self.id} type={self.node_type} name={self.name}>"


class GraphEdge(Base, UUIDMixin, TimestampMixin):
    """A typed, directed, evidence-backed relationship between two graph nodes."""

    __tablename__ = "graph_edges"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )

    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )

    edge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    evidence_kind: Mapped[str] = mapped_column(String(50), default="static", nullable=False)
    source_uri: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    source_commit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Relationships
    source_node = relationship(
        "GraphNode",
        foreign_keys=[source_node_id],
        back_populates="outgoing_edges",
    )
    target_node = relationship(
        "GraphNode",
        foreign_keys=[target_node_id],
        back_populates="incoming_edges",
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("properties", {})
        kwargs.setdefault("confidence", 1.0)
        kwargs.setdefault("evidence_kind", "static")
        super().__init__(**kwargs)

    __table_args__ = (
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="ck_graph_edges_confidence"),
        CheckConstraint("source_node_id <> target_node_id", name="ck_graph_edges_no_self_loop"),
        UniqueConstraint(
            "workspace_id",
            "source_node_id",
            "target_node_id",
            "edge_type",
            name="uq_graph_edges_unique_relation",
        ),
        Index("ix_graph_edges_outgoing", "workspace_id", "source_node_id", "edge_type"),
        Index("ix_graph_edges_incoming", "workspace_id", "target_node_id", "edge_type"),
        Index("ix_graph_edges_workspace_type", "workspace_id", "edge_type"),
        Index("ix_graph_edges_workspace_repo", "workspace_id", "repository_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<GraphEdge id={self.id} {self.source_node_id} "
            f"--[{self.edge_type}]--> {self.target_node_id}>"
        )
