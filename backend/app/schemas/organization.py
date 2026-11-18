"""
TrunkHQ — Organization & Onboarding Schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


AccountTypeLiteral = Literal["individual", "freelancer", "agency", "startup", "enterprise"]
OrgRoleLiteral = Literal["owner", "admin", "developer", "viewer"]


class CreateOrganizationRequest(BaseModel):
    """Create a new tenant organization / workspace."""

    name: str = Field(..., min_length=2, max_length=120)
    account_type: AccountTypeLiteral = "startup"


class AddMemberRequest(BaseModel):
    """Add an existing user to an organization by email."""

    email: EmailStr
    role: Literal["admin", "developer", "viewer"] = "developer"


class UpdateMemberRoleRequest(BaseModel):
    """Update a member's organization role."""

    role: Literal["admin", "developer", "viewer"]


class OnboardingRequest(BaseModel):
    """Guided onboarding completion payload."""

    account_type: AccountTypeLiteral
    workspace_name: Optional[str] = Field(default=None, min_length=2, max_length=120)


class OrganizationResponse(BaseModel):
    """Public organization summary with caller's role."""

    id: UUID
    name: str
    slug: str
    account_type: str
    owner_id: UUID
    role: str = "member"
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationMemberResponse(BaseModel):
    """Organization membership detail."""

    id: UUID
    organization_id: UUID
    user_id: UUID
    username: str
    email: str
    role: str
    created_at: datetime


class AuditLogResponse(BaseModel):
    """Organization audit log entry."""

    id: UUID
    organization_id: UUID
    actor_user_id: UUID
    action: str
    target_type: str
    target_id: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}
