"""
TrunkHQ — Document & DocumentChunk Data Access.
"""

from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk


class DocumentRepository:
    """Tenant-scoped data access for project documents."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, document: Document) -> Document:
        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        self.db.add_all(chunks)
        await self.db.flush()

    async def get_by_id_in_org(
        self,
        doc_id: UUID,
        project_id: UUID,
        organization_id: UUID,
    ) -> Optional[Document]:
        res = await self.db.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.project_id == project_id,
                Document.organization_id == organization_id,
            )
        )
        return res.scalar_one_or_none()

    async def list_by_project(
        self, project_id: UUID, organization_id: UUID
    ) -> Sequence[Document]:
        res = await self.db.execute(
            select(Document)
            .where(
                Document.project_id == project_id,
                Document.organization_id == organization_id,
            )
            .order_by(Document.created_at.desc())
        )
        return list(res.scalars().all())

    async def list_chunks(
        self, doc_id: UUID, organization_id: UUID
    ) -> Sequence[DocumentChunk]:
        res = await self.db.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == doc_id,
                DocumentChunk.organization_id == organization_id,
            )
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(res.scalars().all())

    async def delete_in_org(
        self, doc_id: UUID, project_id: UUID, organization_id: UUID
    ) -> bool:
        doc = await self.get_by_id_in_org(doc_id, project_id, organization_id)
        if not doc:
            return False
        await self.db.delete(doc)
        await self.db.flush()
        return True
