"""
TrunkHQ — Project Data Access.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project
from app.models.repository import Repository


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"
    return f"{base[:48]}-{str(uuid.uuid4())[:8]}"


class ProjectRepository:
    """Tenant-scoped data access layer for multi-repository projects."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        organization_id: UUID,
        created_by: UUID,
        name: str,
        description: Optional[str] = None,
        category: str = "general",
        tech_stack: Optional[list[str]] = None,
    ) -> Project:
        project = Project(
            organization_id=organization_id,
            created_by=created_by,
            name=name.strip(),
            slug=_slugify(name),
            description=description,
            category=category,
            tech_stack=tech_stack,
        )
        self.db.add(project)
        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def get_by_id_in_org(
        self, project_id: UUID, organization_id: UUID
    ) -> Optional[Project]:
        res = await self.db.execute(
            select(Project)
            .options(selectinload(Project.repositories))
            .where(
                Project.id == project_id,
                Project.organization_id == organization_id,
            )
        )
        return res.scalar_one_or_none()

    async def list_by_org(self, organization_id: UUID) -> list[Project]:
        res = await self.db.execute(
            select(Project)
            .options(selectinload(Project.repositories))
            .where(Project.organization_id == organization_id)
            .order_by(Project.created_at.desc())
        )
        return list(res.scalars().all())

    async def update_in_org(
        self, project_id: UUID, organization_id: UUID, **fields
    ) -> Optional[Project]:
        if fields:
            await self.db.execute(
                update(Project)
                .where(
                    Project.id == project_id,
                    Project.organization_id == organization_id,
                )
                .values(**fields)
            )
            await self.db.flush()
        return await self.get_by_id_in_org(project_id, organization_id)

    async def delete_in_org(self, project_id: UUID, organization_id: UUID) -> bool:
        project = await self.get_by_id_in_org(project_id, organization_id)
        if not project:
            return False
        await self.db.delete(project)
        await self.db.flush()
        return True

    async def attach_repository(
        self, project_id: UUID, repo_id: UUID, organization_id: UUID
    ) -> Optional[Repository]:
        res = await self.db.execute(
            select(Repository).where(
                Repository.id == repo_id,
                Repository.organization_id == organization_id,
            )
        )
        repo = res.scalar_one_or_none()
        if not repo:
            return None
        repo.project_id = project_id
        await self.db.flush()
        return repo

    async def detach_repository(
        self, project_id: UUID, repo_id: UUID, organization_id: UUID
    ) -> bool:
        res = await self.db.execute(
            select(Repository).where(
                Repository.id == repo_id,
                Repository.project_id == project_id,
                Repository.organization_id == organization_id,
            )
        )
        repo = res.scalar_one_or_none()
        if not repo:
            return False
        repo.project_id = None
        await self.db.flush()
        return True
