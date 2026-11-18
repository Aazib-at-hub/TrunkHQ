"""
TrunkHQ — Project Document Intelligence API Routes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_tenant_context
from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.database.session import get_db
from app.embeddings import get_embedding_service
from app.ingestion.doc_parser import (
    compute_sha256,
    parse_document_segments,
    validate_document_upload,
)
from app.models.document import Document, DocumentChunk
from app.models.organization import OrgRole
from app.repositories.document_repo import DocumentRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentDetailResponse,
    DocumentResponse,
)

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["Documents"])


async def _verify_project_in_org(
    project_id: UUID, organization_id: UUID, db: AsyncSession
):
    project = await ProjectRepository(db).get_by_id_in_org(project_id, organization_id)
    if not project:
        raise NotFoundError("Project not found")
    return project


@router.get(
    "",
    response_model=list[DocumentResponse],
    summary="List uploaded documents for a project",
)
async def list_project_documents(
    project_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    """List documents scoped strictly to the active organization and project."""
    await _verify_project_in_org(project_id, tenant.organization_id, db)
    docs = await DocumentRepository(db).list_by_project(project_id, tenant.organization_id)
    return [DocumentResponse.model_validate(d) for d in docs]


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and index a project document",
)
async def upload_project_document(
    project_id: UUID,
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Validate, parse, chunk, and embed a project specification or doc file."""
    if tenant.role not in OrgRole.WRITE_ROLES:
        raise ForbiddenError("Viewers cannot upload project documents")

    await _verify_project_in_org(project_id, tenant.organization_id, db)
    raw_bytes = await file.read()
    filename = file.filename or "document.txt"
    ext = validate_document_upload(filename, raw_bytes)
    settings = get_settings()

    parsed_chunks = parse_document_segments(
        filename=filename,
        content_bytes=raw_bytes,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    doc = Document(
        organization_id=tenant.organization_id,
        project_id=project_id,
        uploaded_by=tenant.user_id,
        title=(title.strip() if title and title.strip() else Path(filename).stem)[:255],
        file_name=filename[:255],
        file_ext=ext,
        mime_type=(file.content_type or "application/octet-stream")[:120],
        size_bytes=len(raw_bytes),
        content_hash=compute_sha256(raw_bytes),
        status="INDEXING",
        chunk_count=len(parsed_chunks),
    )
    doc_dao = DocumentRepository(db)
    saved_doc = await doc_dao.create(doc)

    embeddings = get_embedding_service().embed_batch([c.content for c in parsed_chunks])
    chunk_models = [
        DocumentChunk(
            organization_id=tenant.organization_id,
            project_id=project_id,
            document_id=saved_doc.id,
            chunk_index=c.chunk_index,
            section_title=c.section_title,
            page_number=c.page_number,
            content=c.content,
            embedding=emb,
        )
        for c, emb in zip(parsed_chunks, embeddings)
    ]
    await doc_dao.add_chunks(chunk_models)
    saved_doc.status = "READY"
    await db.commit()
    await db.refresh(saved_doc)
    return DocumentResponse.model_validate(saved_doc)


@router.get(
    "/{doc_id}",
    response_model=DocumentDetailResponse,
    summary="Get document metadata and extracted chunks",
)
async def get_project_document(
    project_id: UUID,
    doc_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailResponse:
    """Fetch a single project document and its extracted text chunks."""
    doc_dao = DocumentRepository(db)
    doc = await doc_dao.get_by_id_in_org(doc_id, project_id, tenant.organization_id)
    if not doc:
        raise NotFoundError("Document not found")
    chunks = await doc_dao.list_chunks(doc.id, tenant.organization_id)
    base = DocumentResponse.model_validate(doc)
    return DocumentDetailResponse(
        **base.model_dump(),
        chunks=[DocumentChunkResponse.model_validate(c) for c in chunks],
    )


@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a project document",
)
async def delete_project_document(
    project_id: UUID,
    doc_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a document and its vector chunks from the project."""
    if tenant.role not in OrgRole.WRITE_ROLES:
        raise ForbiddenError("Viewers cannot delete project documents")
    deleted = await DocumentRepository(db).delete_in_org(
        doc_id, project_id, tenant.organization_id
    )
    if not deleted:
        raise NotFoundError("Document not found")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
