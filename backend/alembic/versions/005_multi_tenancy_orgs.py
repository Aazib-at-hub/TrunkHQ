"""Add multi-tenant organizations, memberships, and user onboarding fields

Revision ID: 005_multi_tenancy_orgs
Revises: 004_hybrid_search_indexes
Create Date: 2026-11-17 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]
from sqlalchemy.dialects.postgresql import UUID

revision: str = "005_multi_tenancy_orgs"
down_revision: Union[str, None] = "004_hybrid_search_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("account_type", sa.String(32), server_default="individual", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "onboarding_completed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(120), unique=True, nullable=False),
        sa.Column("account_type", sa.String(32), server_default="individual", nullable=False),
        sa.Column(
            "owner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    op.create_table(
        "organization_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), server_default="developer", nullable=False),
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
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member_org_user"),
    )
    op.create_index("ix_org_members_user_id", "organization_members", ["user_id"])

    op.add_column(
        "repositories",
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_repositories_organization_id", "repositories", ["organization_id"])

    op.add_column(
        "conversations",
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_conversations_organization_id", "conversations", ["organization_id"])

    # Backfill 1 personal organization per existing user & attach existing repos/conversations
    op.execute(
        """
        INSERT INTO organizations (id, name, slug, account_type, owner_id, created_at, updated_at)
        SELECT
            u.id,
            u.username || '''s Workspace',
            'ws-' || LEFT(u.id::text, 8),
            u.account_type,
            u.id,
            NOW(),
            NOW()
        FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM organization_members om WHERE om.user_id = u.id
        );
        """
    )
    op.execute(
        """
        INSERT INTO organization_members (id, organization_id, user_id, role, created_at, updated_at)
        SELECT
            o.id,
            o.id,
            o.owner_id,
            'owner',
            NOW(),
            NOW()
        FROM organizations o
        WHERE NOT EXISTS (
            SELECT 1 FROM organization_members om
            WHERE om.organization_id = o.id AND om.user_id = o.owner_id
        );
        """
    )
    op.execute(
        """
        UPDATE repositories r
        SET organization_id = om.organization_id
        FROM organization_members om
        WHERE r.organization_id IS NULL AND om.user_id = r.user_id;
        """
    )
    op.execute(
        """
        UPDATE conversations c
        SET organization_id = om.organization_id
        FROM organization_members om
        WHERE c.organization_id IS NULL AND om.user_id = c.user_id;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_organization_id", table_name="conversations")
    op.drop_column("conversations", "organization_id")
    op.drop_index("ix_repositories_organization_id", table_name="repositories")
    op.drop_column("repositories", "organization_id")
    op.drop_index("ix_org_members_user_id", table_name="organization_members")
    op.drop_table("organization_members")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
    op.drop_column("users", "onboarding_completed")
    op.drop_column("users", "account_type")
