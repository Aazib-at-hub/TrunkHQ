"""
TrunkHQ — Billing & Usage Metering Data Access.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Plan, Subscription, UsageRecord


def current_period_ym() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


class BillingRepository:
    """Data access layer for plans, subscriptions, and usage metering."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_plans(self) -> list[Plan]:
        res = await self.db.execute(
            select(Plan)
            .where(Plan.is_active.is_(True))
            .order_by(Plan.monthly_price_inr.asc())
        )
        return list(res.scalars().all())

    async def get_plan_by_code(self, code: str) -> Optional[Plan]:
        res = await self.db.execute(select(Plan).where(Plan.code == code))
        return res.scalar_one_or_none()

    async def get_org_subscription(self, organization_id: UUID) -> Optional[Subscription]:
        res = await self.db.execute(
            select(Subscription).where(Subscription.organization_id == organization_id)
        )
        sub = res.scalar_one_or_none()
        if sub:
            return sub

        free_plan = await self.get_plan_by_code("free")
        if not free_plan:
            return None
        sub = Subscription(
            organization_id=organization_id,
            plan_id=free_plan.id,
            status="active",
            billing_cycle="monthly",
            provider="manual",
        )
        self.db.add(sub)
        await self.db.flush()
        await self.db.refresh(sub)
        return sub

    async def upsert_org_subscription(
        self,
        organization_id: UUID,
        plan_id: UUID,
        status: str,
        billing_cycle: str = "monthly",
        provider: str = "manual",
        provider_sub_id: Optional[str] = None,
    ) -> Subscription:
        sub = await self.get_org_subscription(organization_id)
        if not sub:
            sub = Subscription(
                organization_id=organization_id,
                plan_id=plan_id,
                status=status,
                billing_cycle=billing_cycle,
                provider=provider,
                provider_sub_id=provider_sub_id,
            )
            self.db.add(sub)
        else:
            sub.plan_id = plan_id
            sub.status = status
            sub.billing_cycle = billing_cycle
            sub.provider = provider
            if provider_sub_id:
                sub.provider_sub_id = provider_sub_id
        await self.db.flush()
        await self.db.refresh(sub)
        return sub

    async def record_usage(
        self, organization_id: UUID, metric: str, quantity: int = 1
    ) -> None:
        rec = UsageRecord(
            organization_id=organization_id,
            metric=metric,
            quantity=quantity,
            period_ym=current_period_ym(),
        )
        self.db.add(rec)
        await self.db.flush()

    async def get_monthly_usage(
        self, organization_id: UUID, period_ym: Optional[str] = None
    ) -> dict[str, int]:
        ym = period_ym or current_period_ym()
        res = await self.db.execute(
            select(UsageRecord.metric, func.coalesce(func.sum(UsageRecord.quantity), 0))
            .where(
                UsageRecord.organization_id == organization_id,
                UsageRecord.period_ym == ym,
            )
            .group_by(UsageRecord.metric)
        )
        return {metric: int(total) for metric, total in res.all()}
