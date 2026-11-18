"""
TrunkHQ — Repository Schemas.

Request and response schemas for repository import, listing, and status.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ── Requests ─────────────────────────────────────────────────────────────────


def _normalize_tags(v: Optional[list[str]]) -> Optional[list[str]]:
    """Trim, lowercase, and deduplicate project tags."""
    if v is None:
        return None
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in v:
        tag = raw.strip().lower()
        if tag and tag not in seen:
            seen.add(tag)
            cleaned.append(tag[:40])
    return cleaned


class ImportRepositoryRequest(BaseModel):
    """Repository import request."""

    github_url: str = Field(
        ...,
        description="Public GitHub repository URL",
        examples=["https://github.com/owner/repo"],
    )
    branch: str = Field(
        default="main",
        description="Branch to index",
        max_length=255,
    )
    description: Optional[str] = Field(
        default=None,
        description="Short project overview",
        max_length=2000,
    )
    tags: Optional[list[str]] = Field(
        default=None,
        description="Project tags (e.g., backend, rag, fastapi)",
    )
    links: Optional[dict[str, str]] = Field(
        default=None,
        description="Named external links (e.g., docs, demo, jira)",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Detailed project notes or architecture summary",
    )
    project_id: Optional[UUID] = Field(
        default=None,
        description="Optional parent Project UUID to group multiple repositories",
    )

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        return _normalize_tags(v)

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        """Validate that the URL is a valid GitHub repository URL."""
        import re

        pattern = r"^https://github\.com/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+/?$"
        if not re.match(pattern, v.rstrip("/")):
            raise ValueError(
                "URL must be a valid GitHub repository URL "
                "(e.g., https://github.com/owner/repo)"
            )
        return v.rstrip("/")

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, v: str) -> str:
        """Validate that the branch name cannot inject git CLI options."""
        import re

        cleaned = v.strip()
        if not cleaned:
            return "main"
        if cleaned.startswith("-") or ".." in cleaned or not re.match(r"^[a-zA-Z0-9._/-]+$", cleaned):
            raise ValueError(
                f"Invalid branch name '{v}'. Branch must not start with '-' or contain '..'"
            )
        return cleaned


class UpdateRepositoryRequest(BaseModel):
    """Update project metadata in the storage house."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    tags: Optional[list[str]] = Field(default=None)
    links: Optional[dict[str, str]] = Field(default=None)
    notes: Optional[str] = Field(default=None)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        return _normalize_tags(v)


# ── Responses ────────────────────────────────────────────────────────────────


class RepositoryResponse(BaseModel):
    """Repository summary for listing."""

    id: UUID
    user_id: UUID
    organization_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    owner_username: Optional[str] = None
    name: str
    github_url: str
    branch: str
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    links: Optional[dict[str, str]] = None
    notes: Optional[str] = None
    status: str
    file_count: int
    chunk_count: int
    languages: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RepositoryDetailResponse(RepositoryResponse):
    """Extended repository details including files."""

    files: list[FileResponse] = []


class FileResponse(BaseModel):
    """File summary."""

    id: UUID
    path: str
    filename: str
    language: str
    size_bytes: int

    model_config = {"from_attributes": True}


class FileDetailResponse(FileResponse):
    """File with content for source viewer."""

    content: Optional[str] = None
    chunks: list[ChunkResponse] = []


class ChunkResponse(BaseModel):
    """Code chunk summary."""

    id: UUID
    chunk_index: int
    start_line: int
    end_line: int
    language: str
    content: str

    model_config = {"from_attributes": True}


class RepositoryStatusResponse(BaseModel):
    """Lightweight status polling response."""

    id: UUID
    status: str
    file_count: int
    chunk_count: int
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


# Fix forward references
RepositoryDetailResponse.model_rebuild()
FileDetailResponse.model_rebuild()
