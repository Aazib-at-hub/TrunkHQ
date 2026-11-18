"""
TrunkHQ — Organization & Workspace API Routes.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.database.session import get_db
from app.models.audit_log import AuditLog
from app.models.organization import OrgRole
from app.repositories.organization_repo import OrganizationRepository
from app.repositories.user_repo import UserRepository
from app.schemas.common import MessageResponse
from app.schemas.organization import (
    AddMemberRequest,
    AuditLogResponse,
    CreateOrganizationRequest,
    OrganizationMemberResponse,
    OrganizationResponse,
    UpdateMemberRoleRequest,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get(
    "",
    response_model=list[OrganizationResponse],
    summary="List organizations for current user",
)
async def list_organizations(
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationResponse]:
    """List all tenant workspaces the authenticated user belongs to."""
    org_dao = OrganizationRepository(db)
    rows = await org_dao.list_for_user(current_user_id)
    if not rows:
        user = await UserRepository(db).get_by_id(current_user_id)
        if user:
            org = await org_dao.create_with_owner(
                name=f"{user.username}'s Workspace",
                owner_id=current_user_id,
                account_type=getattr(user, "account_type", "individual"),
            )
            await db.commit()
            rows = [(org, OrgRole.OWNER)]

    result: list[OrganizationResponse] = []
    for org, role in rows:
        item = OrganizationResponse.model_validate(org)
        item.role = role
        result.append(item)
    return result


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization workspace",
)
async def create_organization(
    request: CreateOrganizationRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    """Create a new isolated tenant workspace with the caller as owner."""
    org_dao = OrganizationRepository(db)
    org = await org_dao.create_with_owner(
        name=request.name,
        owner_id=current_user_id,
        account_type=request.account_type,
    )
    await db.commit()
    resp = OrganizationResponse.model_validate(org)
    resp.role = OrgRole.OWNER
    return resp


@router.get(
    "/{org_id}/members",
    response_model=list[OrganizationMemberResponse],
    summary="List organization members",
)
async def list_organization_members(
    org_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationMemberResponse]:
    """List members of an organization (requires membership)."""
    org_dao = OrganizationRepository(db)
    caller = await org_dao.get_member(org_id, current_user_id)
    if not caller:
        raise ForbiddenError("You do not have access to this organization")

    members = await org_dao.list_members(org_id)
    return [
        OrganizationMemberResponse(
            id=m.id,
            organization_id=m.organization_id,
            user_id=m.user_id,
            username=m.user.username if m.user else "unknown",
            email=m.user.email if m.user else "",
            role=m.role,
            created_at=m.created_at,
        )
        for m in members
    ]


@router.post(
    "/{org_id}/members",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a user to an organization",
)
async def add_organization_member(
    org_id: UUID,
    request: AddMemberRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMemberResponse:
    """Add an existing registered user to the organization (owner/admin only)."""
    org_dao = OrganizationRepository(db)
    caller = await org_dao.get_member(org_id, current_user_id)
    if not caller or caller.role not in OrgRole.ADMIN_ROLES:
        raise ForbiddenError("Only organization owners or admins can add members")

    target_user = await UserRepository(db).get_by_email(request.email)
    if not target_user:
        raise NotFoundError("No user found with that email address")

    existing = await org_dao.get_member(org_id, target_user.id)
    if existing:
        raise ConflictError("User is already a member of this organization")

    member = await org_dao.add_member(org_id, target_user.id, role=request.role)
    db.add(
        AuditLog(
            organization_id=org_id,
            actor_user_id=current_user_id,
            action="member.added",
            target_type="user",
            target_id=str(target_user.id),
            details={"email": target_user.email, "role": request.role},
        )
    )
    await db.commit()
    return OrganizationMemberResponse(
        id=member.id,
        organization_id=member.organization_id,
        user_id=member.user_id,
        username=target_user.username,
        email=target_user.email,
        role=member.role,
        created_at=member.created_at,
    )


@router.patch(
    "/{org_id}/members/{member_user_id}",
    response_model=OrganizationMemberResponse,
    summary="Update a member's role in an organization",
)
async def update_organization_member_role(
    org_id: UUID,
    member_user_id: UUID,
    request: UpdateMemberRoleRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMemberResponse:
    """Update a non-owner member's role (owner/admin only)."""
    org_dao = OrganizationRepository(db)
    caller = await org_dao.get_member(org_id, current_user_id)
    if not caller or caller.role not in OrgRole.ADMIN_ROLES:
        raise ForbiddenError("Only organization owners or admins can update member roles")

    target = await org_dao.get_member(org_id, member_user_id)
    if not target:
        raise NotFoundError("Member not found in organization")
    if target.role == OrgRole.OWNER:
        raise ForbiddenError("Cannot change the role of the organization owner")

    updated = await org_dao.update_member_role(org_id, member_user_id, request.role)
    target_user = await UserRepository(db).get_by_id(member_user_id)
    db.add(
        AuditLog(
            organization_id=org_id,
            actor_user_id=current_user_id,
            action="member.role_updated",
            target_type="user",
            target_id=str(member_user_id),
            details={"role": request.role},
        )
    )
    await db.commit()
    return OrganizationMemberResponse(
        id=updated.id if updated else target.id,
        organization_id=org_id,
        user_id=member_user_id,
        username=target_user.username if target_user else "unknown",
        email=target_user.email if target_user else "",
        role=request.role,
        created_at=target.created_at,
    )


@router.delete(
    "/{org_id}/members/{member_user_id}",
    response_model=MessageResponse,
    summary="Remove a member from an organization",
)
async def remove_organization_member(
    org_id: UUID,
    member_user_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Remove a non-owner member from an organization (owner/admin only)."""
    org_dao = OrganizationRepository(db)
    caller = await org_dao.get_member(org_id, current_user_id)
    if not caller or caller.role not in OrgRole.ADMIN_ROLES:
        raise ForbiddenError("Only organization owners or admins can remove members")

    target = await org_dao.get_member(org_id, member_user_id)
    if not target:
        raise NotFoundError("Member not found in organization")
    if target.role == OrgRole.OWNER:
        raise ForbiddenError("Cannot remove the organization owner")

    await org_dao.remove_member(org_id, member_user_id)
    db.add(
        AuditLog(
            organization_id=org_id,
            actor_user_id=current_user_id,
            action="member.removed",
            target_type="user",
            target_id=str(member_user_id),
            details=None,
        )
    )
    await db.commit()
    return MessageResponse(message="Member removed from organization")


@router.get(
    "/{org_id}/audit-logs",
    response_model=list[AuditLogResponse],
    summary="List organization audit logs",
)
async def list_organization_audit_logs(
    org_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogResponse]:
    """List recent audit events for an organization (owner/admin only)."""
    org_dao = OrganizationRepository(db)
    caller = await org_dao.get_member(org_id, current_user_id)
    if not caller or caller.role not in OrgRole.ADMIN_ROLES:
        raise ForbiddenError("Only organization owners or admins can view audit logs")

    res = await db.execute(
        select(AuditLog)
        .where(AuditLog.organization_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return [AuditLogResponse.model_validate(row) for row in res.scalars().all()]
