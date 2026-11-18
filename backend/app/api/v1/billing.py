"""
TrunkHQ — Billing, Entitlements & Usage Metering API Routes.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_tenant_context
from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.database.session import get_db
from app.repositories.billing_repo import BillingRepository
from app.schemas.billing import PlanResponse, SubscriptionResponse

router = APIRouter(prefix="/billing", tags=["Billing"])


def verify_billing_signature(
    payload_body: bytes, signature_header: Optional[str], secret: str
) -> bool:
    """Verify HMAC-SHA256 payment webhook signature in constant time."""
    if not signature_header:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


@router.get(
    "/plans",
    response_model=list[PlanResponse],
    summary="List available SaaS subscription plans",
)
async def list_billing_plans(
    db: AsyncSession = Depends(get_db),
) -> list[PlanResponse]:
    """Return active TrunkHQ plans and entitlements."""
    plans = await BillingRepository(db).list_plans()
    return [PlanResponse.model_validate(p) for p in plans]


@router.get(
    "/subscription",
    response_model=SubscriptionResponse,
    summary="Get active organization subscription and monthly usage",
)
async def get_organization_subscription(
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionResponse:
    """Return active organization plan, subscription status, and current-month usage."""
    dao = BillingRepository(db)
    sub = await dao.get_org_subscription(tenant.organization_id)
    if not sub or not sub.plan:
        raise NotFoundError("Subscription plan not found")
    await db.commit()
    usage = await dao.get_monthly_usage(tenant.organization_id)
    return SubscriptionResponse(
        id=sub.id,
        organization_id=sub.organization_id,
        status=sub.status,
        billing_cycle=sub.billing_cycle,
        provider=sub.provider,
        current_period_end=sub.current_period_end,
        plan=PlanResponse.model_validate(sub.plan),
        usage=usage,
    )


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Server-verified payment provider webhook",
)
async def billing_webhook(
    request: Request,
    x_billing_signature: Optional[str] = Header(default=None, alias="X-Billing-Signature"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Verify HMAC signature and update organization subscription server-side."""
    secret = get_settings().billing_webhook_secret
    if not secret:
        raise ValidationError("Billing webhook secret is not configured")

    body = await request.body()
    if not verify_billing_signature(body, x_billing_signature, secret):
        raise ForbiddenError("Invalid billing webhook signature")

    payload = await request.json()
    org_id_raw = payload.get("organization_id")
    plan_code = payload.get("plan_code")
    sub_status = payload.get("status", "active")
    billing_cycle = payload.get("billing_cycle", "monthly")
    provider = payload.get("provider", "razorpay")
    provider_sub_id = payload.get("provider_subscription_id")

    if not org_id_raw or not plan_code:
        raise ValidationError("Webhook payload missing organization_id or plan_code")

    dao = BillingRepository(db)
    plan = await dao.get_plan_by_code(plan_code)
    if not plan:
        raise NotFoundError(f"Plan '{plan_code}' not found")

    await dao.upsert_org_subscription(
        organization_id=UUID(org_id_raw),
        plan_id=plan.id,
        status=sub_status,
        billing_cycle=billing_cycle,
        provider=provider,
        provider_sub_id=provider_sub_id,
    )
    await db.commit()
    return {"status": "processed"}
