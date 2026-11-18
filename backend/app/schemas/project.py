"""
TrunkHQ — Multi-Repo Project Schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.repository import RepositoryResponse


class CreateProjectRequest(BaseModel):
    """Create a multi-repository engineering project."""

    name: str = Field(..., min_length=2, max_length=160)
    description: Optional[str] = Field(default=None, max_length=2000)
    category: str = Field(default="general", max_length=64)
    tech_stack: Optional[list[str]] = None


class UpdateProjectRequest(BaseModel):
    """Update multi-repository project metadata."""

    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    description: Optional[str] = Field(default=None, max_length=2000)
    category: Optional[str] = Field(default=None, max_length=64)
    tech_stack: Optional[list[str]] = None


class ProjectResponse(BaseModel):
    """Project summary response."""

    id: UUID
    organization_id: UUID
    created_by: UUID
    name: str
    slug: str
    description: Optional[str] = None
    category: str
    tech_stack: Optional[list[str]] = None
    repository_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectDetailResponse(ProjectResponse):
    """Project details with attached repositories."""

    repositories: list[RepositoryResponse] = []
