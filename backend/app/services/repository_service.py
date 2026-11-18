"""
TrunkHQ — Repository Business Logic Service.

Coordinates repository import validation, status checks, file exploration,
reindexing triggers, and background ingestion pipeline scheduling.
"""

from __future__ import annotations

import asyncio
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.embeddings import get_embedding_service
from app.ingestion.cloner import validate_github_url
from app.ingestion.pipeline import IngestionPipeline
from app.models.file import RepositoryFile
from app.models.repository import Repository
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.file_repo import FileRepository
from app.repositories.repository_repo import RepositoryRepository

logger = get_logger("repository_service")

# Strong references to in-flight ingestion tasks (asyncio holds only weak refs).
_background_tasks: set[asyncio.Task] = set()


class RepositoryService:
    """Business operations for repository management and ingestion."""

    def __init__(
        self,
        session: AsyncSession,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session = session
        self._session_factory = session_factory
        self._repo_dao = RepositoryRepository(session)
        self._file_dao = FileRepository(session)
        self._chunk_dao = ChunkRepository(session)
        self._settings = get_settings()

    async def import_repository(
        self,
        user_id: UUID,
        github_url: str,
        branch: Optional[str] = "main",
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        links: Optional[dict[str, str]] = None,
        notes: Optional[str] = None,
        organization_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
    ) -> Repository:
        """
        Validate URL, register repository entity, and spawn background ingestion task.
        """
        owner, repo_name = validate_github_url(github_url)

        # Check if already stored in this organization
        existing = (
            await self._repo_dao.get_by_url_in_org(github_url, organization_id)
            if organization_id is not None
            else await self._repo_dao.get_by_url_shared(github_url)
        )
        if existing:
            raise ConflictError(f"Repository '{github_url}' is already stored in this workspace.")

        if project_id is not None and organization_id is not None:
            from app.repositories.project_repo import ProjectRepository

            proj = await ProjectRepository(self._session).get_by_id_in_org(
                project_id, organization_id
            )
            if not proj:
                raise NotFoundError("Target project not found in this organization")

        repo = Repository(
            user_id=user_id,
            organization_id=organization_id,
            project_id=project_id,
            name=repo_name,
            github_url=github_url,
            branch=branch or "main",
            description=description,
            tags=tags,
            links=links,
            notes=notes,
            status="PENDING",
        )
        saved_repo = await self._repo_dao.create(repo)
        await self._session.commit()

        # Reload with owner relationship for response serialization
        loaded_repo = await self._repo_dao.get_by_id_shared(saved_repo.id)

        # Trigger background ingestion task
        self._trigger_ingestion(saved_repo.id)

        return loaded_repo or saved_repo

    def _trigger_ingestion(self, repository_id: UUID) -> None:
        """Launch background async task for pipeline execution."""
        embedding_service = get_embedding_service()
        pipeline = IngestionPipeline(
            session_factory=self._session_factory,
            embedding_service=embedding_service,
            settings=self._settings,
        )

        async def _run():
            try:
                await pipeline.run(repository_id)
            except Exception as e:
                logger.error("Background ingestion pipeline failed", error=str(e))

        task = asyncio.create_task(_run())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    async def list_repositories(
        self,
        user_id: Optional[UUID] = None,
        search: Optional[str] = None,
        tag: Optional[str] = None,
        language: Optional[str] = None,
        organization_id: Optional[UUID] = None,
    ) -> Sequence[Repository]:
        """Fetch repositories scoped to the active organization."""
        if organization_id is not None:
            return await self._repo_dao.list_by_org(
                organization_id=organization_id,
                search=search,
                tag=tag,
                language=language,
            )
        return await self._repo_dao.list_all(search=search, tag=tag, language=language)

    async def get_repository(
        self,
        repository_id: UUID,
        user_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
    ) -> Repository:
        """Fetch single repository scoped to the active organization."""
        repo = (
            await self._repo_dao.get_by_id_in_org(repository_id, organization_id)
            if organization_id is not None
            else await self._repo_dao.get_by_id_shared(repository_id)
        )
        if not repo:
            raise NotFoundError("Repository not found")
        return repo

    async def update_repository(
        self,
        repository_id: UUID,
        user_id: UUID,
        organization_id: Optional[UUID] = None,
        **fields,
    ) -> Repository:
        """Update project metadata (owner only)."""
        repo = await self.get_repository(repository_id, organization_id=organization_id)
        if repo.user_id != user_id:
            raise ForbiddenError("Only the project owner can update project details.")
        updated = await self._repo_dao.update_metadata(repository_id, **fields)
        await self._session.commit()
        return updated or repo

    async def list_files(
        self,
        repository_id: UUID,
        user_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
    ) -> Sequence[RepositoryFile]:
        """List all indexed files for a repository."""
        await self.get_repository(repository_id, organization_id=organization_id)
        return await self._file_dao.list_by_repository(repository_id)

    async def get_file_detail(
        self,
        repository_id: UUID,
        file_id: UUID,
        user_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
    ) -> tuple[RepositoryFile, list]:
        """Get file entity and associated chunks."""
        await self.get_repository(repository_id, organization_id=organization_id)
        file_rec = await self._file_dao.get_by_id(file_id)
        if not file_rec or file_rec.repository_id != repository_id:
            raise NotFoundError("File not found in this repository")
        chunks = await self._chunk_dao.list_by_file(file_id)
        return file_rec, list(chunks)

    async def reindex_repository(
        self,
        repository_id: UUID,
        user_id: UUID,
        organization_id: Optional[UUID] = None,
    ) -> Repository:
        """Reset repository status and rerun ingestion (owner only)."""
        repo = await self.get_repository(repository_id, organization_id=organization_id)
        if repo.user_id != user_id:
            raise ForbiddenError("Only the project owner can reindex this project.")
        if repo.status in ("PENDING", "CLONING", "INDEXING"):
            raise ValidationError("Repository is currently being indexed.")

        await self._repo_dao.update_status(repository_id, "PENDING")
        await self._session.commit()

        self._trigger_ingestion(repository_id)
        return repo

    async def delete_repository(
        self,
        repository_id: UUID,
        user_id: UUID,
        organization_id: Optional[UUID] = None,
    ) -> None:
        """Delete repository and all cascaded data (owner only)."""
        repo = await self.get_repository(repository_id, organization_id=organization_id)
        if repo.user_id != user_id:
            raise ForbiddenError("Only the project owner can delete this project.")
        deleted = await self._repo_dao.delete(repository_id, user_id)
        if not deleted:
            raise NotFoundError("Repository not found")
        await self._session.commit()
