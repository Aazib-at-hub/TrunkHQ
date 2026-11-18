"""
TrunkHQ — Billing, Plan & Usage Metering Schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class PlanResponse(BaseModel):
    id: UUID
    code: str
    name: str
    monthly_price_inr: int
    annual_price_inr: int
    limits: dict[str, Any]
    features: dict[str, Any]
    is_active: bool

    model_config = {"from_attributes": True}


class SubscriptionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    status: str
    billing_cycle: str
    provider: str
    current_period_end: Optional[datetime] = None
    plan: PlanResponse
    usage: dict[str, int]

    model_config = {"from_attributes": True}
