"""
TrunkHQ — FastAPI Dependencies.

Shared dependency functions used across API routes for authentication,
database sessions, and authorization checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, InvalidTokenError, ValidationError
from app.core.security import decode_access_token
from app.database.session import get_db
from app.repositories.organization_repo import OrganizationRepository
from app.repositories.user_repo import UserRepository


@dataclass(frozen=True)
class TenantContext:
    """Authenticated user + verified organization membership."""

    user_id: UUID
    organization_id: UUID
    role: str


async def get_current_user_id(
    authorization: str = Header(..., description="Bearer <token>"),
) -> UUID:
    """
    Extract and validate the current user ID from the Authorization header.

    Args:
        authorization: The Authorization header value (Bearer <token>).

    Returns:
        The authenticated user's UUID.

    Raises:
        InvalidTokenError: If the token is missing, malformed, or expired.
    """
    if not authorization.startswith("Bearer "):
        raise InvalidTokenError("Authorization header must start with 'Bearer '")

    token = authorization[7:]  # Strip "Bearer " prefix
    if not token:
        raise InvalidTokenError("Token is empty")

    return decode_access_token(token)


async def require_admin(
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """Require the authenticated user to be an administrator."""
    user = await UserRepository(db).get_by_id(current_user_id)
    if not user or user.email.lower() not in get_settings().admin_emails_set:
        raise ForbiddenError("Admin privileges required")
    return current_user_id


async def get_tenant_context(
    current_user_id: UUID = Depends(get_current_user_id),
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """Resolve and verify the caller's active organization membership."""
    org_dao = OrganizationRepository(db)

    if x_organization_id:
        try:
            org_id = UUID(x_organization_id)
        except ValueError as exc:
            raise ValidationError("Invalid X-Organization-Id header") from exc

        member = await org_dao.get_member(org_id, current_user_id)
        if not member:
            raise ForbiddenError("You do not have access to this organization")
        return TenantContext(
            user_id=current_user_id,
            organization_id=org_id,
            role=member.role,
        )

    default_member = await org_dao.get_default_for_user(current_user_id)
    if not default_member:
        user = await UserRepository(db).get_by_id(current_user_id)
        if not user:
            raise ForbiddenError("User account not found")
        org = await org_dao.create_with_owner(
            name=f"{user.username}'s Workspace",
            owner_id=current_user_id,
            account_type=getattr(user, "account_type", "individual"),
        )
        await db.commit()
        return TenantContext(user_id=current_user_id, organization_id=org.id, role="owner")

    return TenantContext(
        user_id=current_user_id,
        organization_id=default_member.organization_id,
        role=default_member.role,
    )
