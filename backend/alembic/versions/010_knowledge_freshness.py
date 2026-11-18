"""Add last_indexed_commit_sha to repositories for delta knowledge freshness

Revision ID: 010_knowledge_freshness
Revises: 009_billing_and_usage
Create Date: 2026-11-18 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

revision: str = "010_knowledge_freshness"
down_revision: Union[str, None] = "009_billing_and_usage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column("last_indexed_commit_sha", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("repositories", "last_indexed_commit_sha")
