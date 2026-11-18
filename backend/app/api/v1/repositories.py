"""
TrunkHQ — Repository API Routes.

Endpoints for importing repositories, checking indexing status,
listing files, retrieving file details, reindexing, and deletion.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_tenant_context
from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, ValidationError
from app.database.session import async_session_maker, get_db
from app.models.organization import OrgRole
from app.models.repository import Repository
from app.schemas.repository import (
    ChunkResponse,
    FileDetailResponse,
    FileResponse,
    ImportRepositoryRequest,
    RepositoryDetailResponse,
    RepositoryResponse,
    RepositoryStatusResponse,
    UpdateRepositoryRequest,
)
from app.services.repository_service import RepositoryService

router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.post(
    "/import",
    response_model=RepositoryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Import a GitHub repository",
)
async def import_repository(
    data: ImportRepositoryRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    """Import a public GitHub repository and begin background indexing."""
    if tenant.role not in OrgRole.WRITE_ROLES:
        raise ForbiddenError("Viewers cannot import repositories")
    service = RepositoryService(db, async_session_maker)
    repo = await service.import_repository(
        user_id=tenant.user_id,
        github_url=data.github_url,
        branch=data.branch,
        description=data.description,
        tags=data.tags,
        links=data.links,
        notes=data.notes,
        organization_id=tenant.organization_id,
        project_id=data.project_id,
    )
    return RepositoryResponse.model_validate(repo)


@router.get(
    "",
    response_model=list[RepositoryResponse],
    summary="List all stored projects",
)
async def list_repositories(
    search: Optional[str] = Query(default=None, description="Search by name, description, URL, or notes"),
    tag: Optional[str] = Query(default=None, description="Filter by project tag"),
    language: Optional[str] = Query(default=None, description="Filter by programming language"),
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> list[RepositoryResponse]:
    """Retrieve all projects stored in the active organization workspace."""
    service = RepositoryService(db, async_session_maker)
    repos = await service.list_repositories(
        user_id=tenant.user_id,
        search=search,
        tag=tag,
        language=language,
        organization_id=tenant.organization_id,
    )
    return [RepositoryResponse.model_validate(r) for r in repos]


@router.patch(
    "/{repo_id}",
    response_model=RepositoryResponse,
    summary="Update project details",
)
async def update_repository(
    repo_id: UUID,
    data: UpdateRepositoryRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    """Update project metadata (owner only)."""
    if tenant.role not in OrgRole.WRITE_ROLES:
        raise ForbiddenError("Viewers cannot update projects")
    service = RepositoryService(db, async_session_maker)
    fields = data.model_dump(exclude_unset=True)
    repo = await service.update_repository(
        repo_id,
        tenant.user_id,
        organization_id=tenant.organization_id,
        **fields,
    )
    return RepositoryResponse.model_validate(repo)


@router.get(
    "/{repo_id}",
    response_model=RepositoryDetailResponse,
    summary="Get repository details",
)
async def get_repository(
    repo_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> RepositoryDetailResponse:
    """Retrieve repository information including file tree."""
    service = RepositoryService(db, async_session_maker)
    repo = await service.get_repository(
        repo_id, tenant.user_id, organization_id=tenant.organization_id
    )
    files = await service.list_files(
        repo_id, tenant.user_id, organization_id=tenant.organization_id
    )

    resp = RepositoryDetailResponse.model_validate(repo)
    resp.files = [FileResponse.model_validate(f) for f in files]
    return resp


@router.get(
    "/{repo_id}/status",
    response_model=RepositoryStatusResponse,
    summary="Get repository indexing status",
)
async def get_repository_status(
    repo_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> RepositoryStatusResponse:
    """Poll current indexing progress and counts."""
    service = RepositoryService(db, async_session_maker)
    repo = await service.get_repository(
        repo_id, tenant.user_id, organization_id=tenant.organization_id
    )
    return RepositoryStatusResponse.model_validate(repo)


@router.get(
    "/{repo_id}/files",
    response_model=list[FileResponse],
    summary="List repository files",
)
async def list_repository_files(
    repo_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> list[FileResponse]:
    """Retrieve all indexed files in repository."""
    service = RepositoryService(db, async_session_maker)
    files = await service.list_files(
        repo_id, tenant.user_id, organization_id=tenant.organization_id
    )
    return [FileResponse.model_validate(f) for f in files]


@router.get(
    "/{repo_id}/files/{file_id}",
    response_model=FileDetailResponse,
    summary="Get file content and chunks",
)
async def get_file_detail(
    repo_id: UUID,
    file_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> FileDetailResponse:
    """Fetch file metadata and chunk segments for code viewer."""
    service = RepositoryService(db, async_session_maker)
    file_rec, chunks = await service.get_file_detail(
        repo_id, file_id, tenant.user_id, organization_id=tenant.organization_id
    )

    full_content = _reconstruct_content(chunks)
    resp = FileDetailResponse.model_validate(file_rec)
    resp.content = full_content
    resp.chunks = [ChunkResponse.model_validate(c) for c in chunks]
    return resp


def _reconstruct_content(chunks: list) -> str:
    """
    Rebuild file text from overlapping chunks using their line ranges.

    Chunks overlap (CHUNK_OVERLAP), so concatenation would duplicate lines.
    Each line is written once at its 1-indexed position.
    """
    if not chunks:
        return ""
    lines: dict[int, str] = {}
    for chunk in chunks:
        for offset, text in enumerate(chunk.content.split("\n")):
            lines.setdefault(chunk.start_line + offset, text)
    max_line = max(lines)
    return "\n".join(lines.get(i, "") for i in range(1, max_line + 1))


@router.post(
    "/{repo_id}/reindex",
    response_model=RepositoryResponse,
    summary="Re-index repository",
)
async def reindex_repository(
    repo_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    """Reset repository status and rerun full indexing pipeline."""
    if tenant.role not in OrgRole.WRITE_ROLES:
        raise ForbiddenError("Viewers cannot reindex projects")
    service = RepositoryService(db, async_session_maker)
    repo = await service.reindex_repository(
        repo_id, tenant.user_id, organization_id=tenant.organization_id
    )
    return RepositoryResponse.model_validate(repo)


@router.delete(
    "/{repo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete repository",
)
async def delete_repository(
    repo_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Permanently delete repository, files, chunks, and conversations."""
    if tenant.role not in OrgRole.WRITE_ROLES:
        raise ForbiddenError("Viewers cannot delete projects")
    service = RepositoryService(db, async_session_maker)
    await service.delete_repository(
        repo_id, tenant.user_id, organization_id=tenant.organization_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def verify_github_signature(payload_body: bytes, signature_header: Optional[str], secret: str) -> bool:
    """Verify GitHub X-Hub-Signature-256 HMAC-SHA256 digest in constant time."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@router.post(
    "/webhook/github",
    status_code=status.HTTP_202_ACCEPTED,
    summary="GitHub push webhook for repository synchronization",
)
async def github_push_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(default=None, alias="X-Hub-Signature-256"),
    x_github_event: str = Header(default="push", alias="X-GitHub-Event"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Verify HMAC signature and trigger asynchronous reindex for matching repositories."""
    secret = get_settings().github_webhook_secret
    if not secret:
        raise ValidationError("GitHub webhook secret is not configured")

    body = await request.body()
    if not verify_github_signature(body, x_hub_signature_256, secret):
        raise ForbiddenError("Invalid GitHub webhook signature")

    if x_github_event != "push":
        return {"status": "ignored", "event": x_github_event}

    payload = await request.json()
    repo_url = ((payload.get("repository") or {}).get("html_url") or "").rstrip("/")
    ref = payload.get("ref") or ""
    branch = ref.removeprefix("refs/heads/") if ref.startswith("refs/heads/") else ref
    if not repo_url:
        return {"status": "ignored", "reason": "missing repository url"}

    res = await db.execute(
        select(Repository).where(
            Repository.github_url == repo_url,
            Repository.branch == (branch or "main"),
        )
    )
    matches = list(res.scalars().all())
    service = RepositoryService(db, async_session_maker)

    from app.ingestion.delta_sync import MAX_DELTA_FILES, extract_push_diff, run_delta_sync
    import asyncio

    after_sha, changed_paths, removed_paths = extract_push_diff(payload)
    forced = bool(payload.get("forced"))
    use_delta = (
        not forced
        and bool(changed_paths or removed_paths)
        and (len(changed_paths) + len(removed_paths) <= MAX_DELTA_FILES)
    )

    triggered = 0
    for repo in matches:
        if repo.status not in ("PENDING", "CLONING", "INDEXING"):
            if use_delta:
                task = asyncio.create_task(
                    run_delta_sync(
                        async_session_maker,
                        repo.id,
                        after_sha,
                        changed_paths,
                        removed_paths,
                    )
                )
                triggered += 1
                _ = task
            else:
                await service._repo_dao.update_status(repo.id, "PENDING")
                await db.commit()
                service._trigger_ingestion(repo.id)
                triggered += 1

    return {
        "status": "accepted",
        "mode": "delta" if use_delta else "full",
        "triggered": triggered,
    }

