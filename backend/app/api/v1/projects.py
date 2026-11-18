"""
TrunkHQ — Multi-Repository Project API Routes.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_tenant_context
from app.core.exceptions import ForbiddenError, NotFoundError
from app.database.session import get_db
from app.models.organization import OrgRole
from app.repositories.project_repo import ProjectRepository
from app.schemas.project import (
    CreateProjectRequest,
    ProjectDetailResponse,
    ProjectResponse,
    UpdateProjectRequest,
)
from app.schemas.repository import RepositoryResponse

router = APIRouter(prefix="/projects", tags=["Projects"])


def _to_project_response(project) -> ProjectResponse:
    repos = getattr(project, "repositories", None) or []
    return ProjectResponse(
        id=project.id,
        organization_id=project.organization_id,
        created_by=project.created_by,
        name=project.name,
        slug=project.slug,
        description=project.description,
        category=project.category,
        tech_stack=project.tech_stack,
        repository_count=len(repos),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get(
    "",
    response_model=list[ProjectResponse],
    summary="List projects in the active organization",
)
async def list_projects(
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    """List multi-repository projects scoped to the active organization."""
    dao = ProjectRepository(db)
    projects = await dao.list_by_org(tenant.organization_id)
    return [_to_project_response(p) for p in projects]


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a multi-repository project",
)
async def create_project(
    data: CreateProjectRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create a new project inside the active organization."""
    if tenant.role not in OrgRole.WRITE_ROLES:
        raise ForbiddenError("Viewers cannot create projects")
    dao = ProjectRepository(db)
    project = await dao.create(
        organization_id=tenant.organization_id,
        created_by=tenant.user_id,
        name=data.name,
        description=data.description,
        category=data.category,
        tech_stack=data.tech_stack,
    )
    await db.commit()
    return _to_project_response(project)


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Get project details and attached repositories",
)
async def get_project(
    project_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> ProjectDetailResponse:
    """Fetch a project and its linked repositories within the active organization."""
    dao = ProjectRepository(db)
    project = await dao.get_by_id_in_org(project_id, tenant.organization_id)
    if not project:
        raise NotFoundError("Project not found")
    repos = getattr(project, "repositories", None) or []
    base = _to_project_response(project)
    return ProjectDetailResponse(
        **base.model_dump(),
        repositories=[RepositoryResponse.model_validate(r) for r in repos],
    )


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project metadata",
)
async def update_project(
    project_id: UUID,
    data: UpdateProjectRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update project fields (owner/admin/developer)."""
    if tenant.role not in OrgRole.WRITE_ROLES:
        raise ForbiddenError("Viewers cannot update projects")
    dao = ProjectRepository(db)
    fields = data.model_dump(exclude_unset=True)
    updated = await dao.update_in_org(project_id, tenant.organization_id, **fields)
    if not updated:
        raise NotFoundError("Project not found")
    await db.commit()
    return _to_project_response(updated)


@router.post(
    "/{project_id}/repositories/{repo_id}",
    response_model=RepositoryResponse,
    summary="Attach an organization repository to a project",
)
async def attach_repository_to_project(
    project_id: UUID,
    repo_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    """Associate an existing organization repository with this project."""
    if tenant.role not in OrgRole.WRITE_ROLES:
        raise ForbiddenError("Viewers cannot modify project repositories")
    dao = ProjectRepository(db)
    project = await dao.get_by_id_in_org(project_id, tenant.organization_id)
    if not project:
        raise NotFoundError("Project not found")
    repo = await dao.attach_repository(project_id, repo_id, tenant.organization_id)
    if not repo:
        raise NotFoundError("Repository not found in this organization")
    await db.commit()
    return RepositoryResponse.model_validate(repo)


@router.delete(
    "/{project_id}/repositories/{repo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Detach a repository from a project",
)
async def detach_repository_from_project(
    project_id: UUID,
    repo_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Unlink a repository from a project without deleting the repository."""
    if tenant.role not in OrgRole.WRITE_ROLES:
        raise ForbiddenError("Viewers cannot modify project repositories")
    dao = ProjectRepository(db)
    detached = await dao.detach_repository(project_id, repo_id, tenant.organization_id)
    if not detached:
        raise NotFoundError("Repository not attached to this project")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a project",
)
async def delete_project(
    project_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete project metadata (repositories remain in organization)."""
    if tenant.role not in OrgRole.WRITE_ROLES:
        raise ForbiddenError("Viewers cannot delete projects")
    dao = ProjectRepository(db)
    deleted = await dao.delete_in_org(project_id, tenant.organization_id)
    if not deleted:
        raise NotFoundError("Project not found")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
