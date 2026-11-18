"""Add pgvector HNSW index and GIN full-text index on code_chunks

Revision ID: 004_hybrid_search_indexes
Revises: 003_project_storage_house
Create Date: 2026-11-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]

revision: str = "004_hybrid_search_indexes"
down_revision: Union[str, None] = "003_project_storage_house"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_code_chunks_embedding_hnsw "
        "ON code_chunks USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_code_chunks_content_fts "
        "ON code_chunks USING gin (to_tsvector('simple', content))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_code_chunks_content_fts")

