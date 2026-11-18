"""
TrunkHQ — Organization & Membership Data Access.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.organization import Organization, OrganizationMember, OrgRole


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"
    return f"{base[:48]}-{str(uuid.uuid4())[:8]}"


class OrganizationRepository:
    """Data access layer for multi-tenant organizations and memberships."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_with_owner(
        self,
        name: str,
        owner_id: UUID,
        account_type: str = "individual",
        slug: Optional[str] = None,
    ) -> Organization:
        """Create an organization and attach the owner as an OrganizationMember."""
        org = Organization(
            name=name.strip(),
            slug=slug or _slugify(name),
            account_type=account_type,
            owner_id=owner_id,
        )
        self.db.add(org)
        await self.db.flush()

        member = OrganizationMember(
            organization_id=org.id,
            user_id=owner_id,
            role=OrgRole.OWNER,
        )
        self.db.add(member)
        await self.db.flush()
        await self.db.refresh(org)
        return org

    async def get_by_id(self, org_id: UUID) -> Optional[Organization]:
        res = await self.db.execute(select(Organization).where(Organization.id == org_id))
        return res.scalar_one_or_none()

    async def get_member(
        self, org_id: UUID, user_id: UUID
    ) -> Optional[OrganizationMember]:
        res = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return res.scalar_one_or_none()

    async def get_default_for_user(self, user_id: UUID) -> Optional[OrganizationMember]:
        """Return the user's primary (oldest) organization membership."""
        res = await self.db.execute(
            select(OrganizationMember)
            .options(selectinload(OrganizationMember.organization))
            .where(OrganizationMember.user_id == user_id)
            .order_by(OrganizationMember.created_at.asc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def list_for_user(
        self, user_id: UUID
    ) -> Sequence[tuple[Organization, str]]:
        """List all organizations a user belongs to alongside their role."""
        res = await self.db.execute(
            select(Organization, OrganizationMember.role)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id)
            .order_by(Organization.created_at.asc())
        )
        return list(res.all())

    async def list_members(self, org_id: UUID) -> Sequence[OrganizationMember]:
        res = await self.db.execute(
            select(OrganizationMember)
            .options(selectinload(OrganizationMember.user))
            .where(OrganizationMember.organization_id == org_id)
            .order_by(OrganizationMember.created_at.asc())
        )
        return list(res.scalars().all())

    async def add_member(
        self, org_id: UUID, user_id: UUID, role: str = OrgRole.DEVELOPER
    ) -> OrganizationMember:
        member = OrganizationMember(organization_id=org_id, user_id=user_id, role=role)
        self.db.add(member)
        await self.db.flush()
        await self.db.refresh(member)
        return member

    async def update_member_role(
        self, org_id: UUID, user_id: UUID, role: str
    ) -> Optional[OrganizationMember]:
        member = await self.get_member(org_id, user_id)
        if not member:
            return None
        member.role = role
        await self.db.flush()
        await self.db.refresh(member)
        return member

    async def remove_member(self, org_id: UUID, user_id: UUID) -> bool:
        member = await self.get_member(org_id, user_id)
        if not member:
            return False
        await self.db.delete(member)
        await self.db.flush()
        return True
