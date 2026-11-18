"""
TrunkHQ — Repository Model.

Represents an imported GitHub repository with its processing state,
metadata, and relationships to files, chunks, and conversations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, inspect as sa_inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class RepositoryStatus:
    """Repository processing status constants."""

    PENDING = "PENDING"
    CLONING = "CLONING"
    DISCOVERING = "DISCOVERING"
    FILTERING = "FILTERING"
    EXTRACTING = "EXTRACTING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    INDEXING = "INDEXING"
    READY = "READY"
    FAILED = "FAILED"

    ALL = [
        PENDING, CLONING, DISCOVERING, FILTERING,
        EXTRACTING, CHUNKING, EMBEDDING, INDEXING,
        READY, FAILED,
    ]


class Repository(Base, UUIDMixin, TimestampMixin):
    """Imported GitHub repository entity."""

    __tablename__ = "repositories"

    # Ownership & Tenancy
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Repository metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    github_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    branch: Mapped[str] = mapped_column(String(255), default="main", nullable=False)

    # Project storage-house metadata
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)
    links: Mapped[Optional[dict[str, str]]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Processing state
    status: Mapped[str] = mapped_column(
        String(20), default=RepositoryStatus.PENDING, nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Statistics (populated after processing)
    file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    languages: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    last_indexed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_indexed_commit_sha: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )

    # Relationships
    user = relationship("User", back_populates="repositories")
    project = relationship("Project", back_populates="repositories")
    files = relationship(
        "RepositoryFile", back_populates="repository", cascade="all, delete-orphan", lazy="noload"
    )
    chunks = relationship(
        "CodeChunk", back_populates="repository", cascade="all, delete-orphan", lazy="noload"
    )
    conversations = relationship(
        "Conversation", back_populates="repository", cascade="all, delete-orphan", lazy="noload"
    )

    # Indexes
    __table_args__ = (
        Index("ix_repositories_user_id", "user_id"),
        Index("ix_repositories_user_status", "user_id", "status"),
    )

    @property
    def owner_username(self) -> Optional[str]:
        """Return owner's username when the user relationship is loaded."""
        if "user" in sa_inspect(self).unloaded or self.user is None:
            return None
        return self.user.username

    def __repr__(self) -> str:
        return f"<Repository id={self.id} name={self.name} status={self.status}>"
