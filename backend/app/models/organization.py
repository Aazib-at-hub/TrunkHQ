"""
TrunkHQ — Organization & Membership Models.

Provides the foundational multi-tenant boundary so individuals, freelancers,
agencies, startups, and enterprises can share one Cloud SaaS platform without
cross-tenant data leakage.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class OrgRole:
    """Organization-level RBAC roles."""

    OWNER = "owner"
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"

    ALL = [OWNER, ADMIN, DEVELOPER, VIEWER]
    WRITE_ROLES = {OWNER, ADMIN, DEVELOPER}
    ADMIN_ROLES = {OWNER, ADMIN}


class AccountType:
    """Supported customer segment types."""

    INDIVIDUAL = "individual"
    FREELANCER = "freelancer"
    AGENCY = "agency"
    STARTUP = "startup"
    ENTERPRISE = "enterprise"

    ALL = [INDIVIDUAL, FREELANCER, AGENCY, STARTUP, ENTERPRISE]


class Organization(Base, UUIDMixin, TimestampMixin):
    """Tenant organization / workspace entity."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    account_type: Mapped[str] = mapped_column(
        String(32), default=AccountType.INDIVIDUAL, nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    members = relationship(
        "OrganizationMember",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id} slug={self.slug}>"


class OrganizationMember(Base, UUIDMixin, TimestampMixin):
    """Membership linking a User to an Organization with an RBAC role."""

    __tablename__ = "organization_members"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), default=OrgRole.DEVELOPER, nullable=False)

    organization = relationship("Organization", back_populates="members")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member_org_user"),
        Index("ix_org_members_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<OrganizationMember org={self.organization_id} user={self.user_id} role={self.role}>"
