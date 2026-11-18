"""Add multi-repository projects table and repository.project_id

Revision ID: 006_projects_table
Revises: 005_multi_tenancy_orgs
Create Date: 2026-11-17 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "006_projects_table"
down_revision: Union[str, None] = "005_multi_tenancy_orgs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), server_default="general", nullable=False),
        sa.Column("tech_stack", JSONB(), nullable=True),
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
        sa.UniqueConstraint("organization_id", "slug", name="uq_projects_org_slug"),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])

    op.add_column(
        "repositories",
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_repositories_project_id", "repositories", ["project_id"])

    # Backward-compatible backfill: create 1 Project per existing Repository
    op.execute(
        """
        INSERT INTO projects (id, organization_id, created_by, name, slug, description, category, created_at, updated_at)
        SELECT
            r.id,
            r.organization_id,
            r.user_id,
            r.name,
            LEFT(LOWER(REGEXP_REPLACE(r.name, '[^a-zA-Z0-9]+', '-', 'g')), 48) || '-' || LEFT(r.id::text, 8),
            r.description,
            'general',
            r.created_at,
            r.updated_at
        FROM repositories r
        WHERE r.organization_id IS NOT NULL
          AND r.project_id IS NULL
          AND NOT EXISTS (SELECT 1 FROM projects p WHERE p.id = r.id);
        """
    )
    op.execute(
        """
        UPDATE repositories r
        SET project_id = r.id
        WHERE r.organization_id IS NOT NULL
          AND r.project_id IS NULL
          AND EXISTS (SELECT 1 FROM projects p WHERE p.id = r.id);
        """
    )


def downgrade() -> None:
    op.drop_index("ix_repositories_project_id", table_name="repositories")
    op.drop_column("repositories", "project_id")
    op.drop_index("ix_projects_organization_id", table_name="projects")
    op.drop_table("projects")
