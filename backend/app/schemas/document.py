"""
TrunkHQ — Document Intelligence Schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    """Summary metadata for an uploaded project document."""

    id: UUID
    organization_id: UUID
    project_id: UUID
    uploaded_by: UUID
    title: str
    file_name: str
    file_ext: str
    mime_type: str
    size_bytes: int
    status: str
    error_message: Optional[str] = None
    chunk_count: int
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentChunkResponse(BaseModel):
    """Chunk preview for document inspection."""

    id: UUID
    chunk_index: int
    section_title: Optional[str] = None
    page_number: Optional[int] = None
    content: str

    model_config = {"from_attributes": True}


class DocumentDetailResponse(DocumentResponse):
    """Document details including extracted chunks."""

    chunks: list[DocumentChunkResponse] = []
