"""Project storage house metadata columns on repositories

Revision ID: 003_project_storage_house
Revises: 002_relationship_graph
Create Date: 2026-11-13 00:00:00.000000

Mirrors project metadata additions on app/models/repository.py.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_project_storage_house"
down_revision: Union[str, None] = "002_relationship_graph"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("repositories", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("repositories", sa.Column("tags", postgresql.JSONB(), nullable=True))
    op.add_column("repositories", sa.Column("links", postgresql.JSONB(), nullable=True))
    op.add_column("repositories", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("repositories", "notes")
    op.drop_column("repositories", "links")
    op.drop_column("repositories", "tags")
    op.drop_column("repositories", "description")

