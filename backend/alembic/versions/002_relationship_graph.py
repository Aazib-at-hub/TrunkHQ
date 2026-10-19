"""Relationship graph schema with nodes, edges, and index runs

Revision ID: 002_relationship_graph
Revises: 001_initial_schema
Create Date: 2026-10-16 00:00:00.000000

Mirrors app/models/graph.py.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002_relationship_graph"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    # ── graph_index_runs ─────────────────────────────────────────────────────
    op.create_table(
        "graph_index_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commit_sha", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="RUNNING"),
        sa.Column("nodes_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("nodes_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("nodes_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("edges_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("edges_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("edges_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("extractor_version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("schema_version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "ix_graph_index_runs_repo_status",
        "graph_index_runs",
        ["workspace_id", "repository_id", "status"],
    )

    # ── graph_nodes ──────────────────────────────────────────────────────────
    op.create_table(
        "graph_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_type", sa.String(50), nullable=False),
        sa.Column("stable_key", sa.String(512), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("qualified_name", sa.String(512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("source_kind", sa.String(50), nullable=False, server_default="code"),
        sa.Column("source_uri", sa.String(1024), nullable=True),
        sa.Column("source_commit", sa.String(64), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "stable_key", name="uq_graph_nodes_workspace_stable_key"),
    )
    op.create_index("ix_graph_nodes_workspace_type", "graph_nodes", ["workspace_id", "node_type"])
    op.create_index("ix_graph_nodes_workspace_repo", "graph_nodes", ["workspace_id", "repository_id"])
    op.create_index("ix_graph_nodes_workspace_name", "graph_nodes", ["workspace_id", "name"])
    op.create_index(
        "ix_graph_nodes_properties",
        "graph_nodes",
        ["properties"],
        postgresql_using="gin",
    )

    # ── graph_edges ──────────────────────────────────────────────────────────
    op.create_table(
        "graph_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("graph_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("graph_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("edge_type", sa.String(50), nullable=False),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("evidence_kind", sa.String(50), nullable=False, server_default="static"),
        sa.Column("source_uri", sa.String(1024), nullable=True),
        sa.Column("source_commit", sa.String(64), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="ck_graph_edges_confidence"),
        sa.CheckConstraint("source_node_id <> target_node_id", name="ck_graph_edges_no_self_loop"),
        sa.UniqueConstraint(
            "workspace_id",
            "source_node_id",
            "target_node_id",
            "edge_type",
            name="uq_graph_edges_unique_relation",
        ),
    )
    op.create_index(
        "ix_graph_edges_outgoing",
        "graph_edges",
        ["workspace_id", "source_node_id", "edge_type"],
    )
    op.create_index(
        "ix_graph_edges_incoming",
        "graph_edges",
        ["workspace_id", "target_node_id", "edge_type"],
    )
    op.create_index(
        "ix_graph_edges_workspace_type",
        "graph_edges",
        ["workspace_id", "edge_type"],
    )
    op.create_index(
        "ix_graph_edges_workspace_repo",
        "graph_edges",
        ["workspace_id", "repository_id"],
    )


def downgrade() -> None:
    op.drop_table("graph_edges")
    op.drop_table("graph_nodes")
    op.drop_table("graph_index_runs")
