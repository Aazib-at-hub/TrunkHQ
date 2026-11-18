"""
TrunkHQ — Repository Data Access.

Database operations for the Repository entity. Enforces user ownership
on every query to prevent cross-user data access.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.repository import Repository


class RepositoryRepository:
    """Data access layer for Repository entities."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, repo_id: UUID, user_id: UUID) -> Optional[Repository]:
        """Get a repository by ID, scoped to the owning user."""
        result = await self.db.execute(
            select(Repository)
            .options(selectinload(Repository.user))
            .where(
                Repository.id == repo_id,
                Repository.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_shared(self, repo_id: UUID) -> Optional[Repository]:
        """Get a repository by ID for any authenticated workspace member."""
        result = await self.db.execute(
            select(Repository)
            .options(selectinload(Repository.user))
            .where(Repository.id == repo_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_in_org(
        self, repo_id: UUID, organization_id: UUID
    ) -> Optional[Repository]:
        """Get a repository by ID scoped strictly to an organization."""
        result = await self.db.execute(
            select(Repository)
            .options(selectinload(Repository.user))
            .where(
                Repository.id == repo_id,
                Repository.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_unscoped(self, repo_id: UUID) -> Optional[Repository]:
        """
        Get a repository by ID without ownership scoping.

        INTERNAL USE ONLY — for background ingestion jobs that run without
        a request user. Never call from API-facing code paths.
        """
        result = await self.db.execute(select(Repository).where(Repository.id == repo_id))
        return result.scalar_one_or_none()

    async def get_by_url(self, github_url: str, user_id: UUID) -> Optional[Repository]:
        """Check if a user already imported this repository URL."""
        result = await self.db.execute(
            select(Repository).where(
                Repository.github_url == github_url,
                Repository.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_url_shared(self, github_url: str) -> Optional[Repository]:
        """Check if any user already stored this repository URL in the workspace."""
        result = await self.db.execute(
            select(Repository).where(Repository.github_url == github_url)
        )
        return result.scalar_one_or_none()

    async def get_by_url_in_org(
        self, github_url: str, organization_id: UUID
    ) -> Optional[Repository]:
        """Check if a repository URL is already stored in the given organization."""
        result = await self.db.execute(
            select(Repository).where(
                Repository.github_url == github_url,
                Repository.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: UUID) -> list[Repository]:
        """List all repositories owned by a user, ordered by creation date."""
        result = await self.db.execute(
            select(Repository)
            .options(selectinload(Repository.user))
            .where(Repository.user_id == user_id)
            .order_by(Repository.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_all(
        self,
        search: Optional[str] = None,
        tag: Optional[str] = None,
        language: Optional[str] = None,
    ) -> list[Repository]:
        """List all repositories in the workspace, optionally filtered."""
        return await self._list_filtered(
            organization_id=None, search=search, tag=tag, language=language
        )

    async def list_by_org(
        self,
        organization_id: UUID,
        search: Optional[str] = None,
        tag: Optional[str] = None,
        language: Optional[str] = None,
    ) -> list[Repository]:
        """List all repositories belonging to a specific organization."""
        return await self._list_filtered(
            organization_id=organization_id, search=search, tag=tag, language=language
        )

    async def _list_filtered(
        self,
        organization_id: Optional[UUID],
        search: Optional[str] = None,
        tag: Optional[str] = None,
        language: Optional[str] = None,
    ) -> list[Repository]:
        stmt = (
            select(Repository)
            .options(selectinload(Repository.user))
            .order_by(Repository.created_at.desc())
        )
        if organization_id is not None:
            stmt = stmt.where(Repository.organization_id == organization_id)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Repository.name.ilike(pattern),
                    Repository.description.ilike(pattern),
                    Repository.github_url.ilike(pattern),
                    Repository.notes.ilike(pattern),
                )
            )
        result = await self.db.execute(stmt)
        repos = list(result.scalars().all())

        if tag:
            target_tag = tag.strip().lower()
            repos = [r for r in repos if r.tags and target_tag in [t.lower() for t in r.tags]]
        if language:
            target_lang = language.strip().lower()
            repos = [
                r
                for r in repos
                if r.languages and any(k.lower() == target_lang for k in r.languages.keys())
            ]
        return repos

    async def update_metadata(
        self,
        repo_id: UUID,
        **fields,
    ) -> Optional[Repository]:
        """Update project metadata fields on a repository."""
        if fields:
            await self.db.execute(
                update(Repository).where(Repository.id == repo_id).values(**fields)
            )
            await self.db.flush()
        return await self.get_by_id_shared(repo_id)

    async def create(self, repository: Repository) -> Repository:
        """Persist a new repository."""
        self.db.add(repository)
        await self.db.flush()
        await self.db.refresh(repository)
        return repository

    async def update_status(
        self,
        repo_id: UUID,
        status: str,
        error_message: Optional[str] = None,
        file_count: Optional[int] = None,
        chunk_count: Optional[int] = None,
        languages: Optional[dict] = None,
        last_indexed_at: Optional[datetime] = None,
    ) -> None:
        """Update repository processing status and statistics."""
        values: dict = {"status": status}
        if status != "FAILED":
            values["error_message"] = None  # Clear stale errors on retry
        if last_indexed_at is not None:
            values["last_indexed_at"] = last_indexed_at
        if error_message is not None:
            values["error_message"] = error_message
        if file_count is not None:
            values["file_count"] = file_count
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        if languages is not None:
            values["languages"] = languages

        await self.db.execute(
            update(Repository).where(Repository.id == repo_id).values(**values)
        )
        await self.db.flush()

    async def delete(self, repo_id: UUID, user_id: UUID) -> bool:
        """Delete a repository and all associated data (cascading). Returns True if deleted."""
        result = await self.db.execute(
            delete(Repository).where(
                Repository.id == repo_id,
                Repository.user_id == user_id,
            )
        )
        await self.db.flush()
        return result.rowcount > 0


# Backwards compatibility alias
RepositoryRepo = RepositoryRepository

