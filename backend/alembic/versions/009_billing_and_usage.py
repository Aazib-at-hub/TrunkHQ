"""Add plans, subscriptions, and usage_records tables for SaaS billing

Revision ID: 009_billing_and_usage
Revises: 008_audit_logs
Create Date: 2026-11-17 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "009_billing_and_usage"
down_revision: Union[str, None] = "008_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), unique=True, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("monthly_price_inr", sa.Integer(), server_default="0", nullable=False),
        sa.Column("annual_price_inr", sa.Integer(), server_default="0", nullable=False),
        sa.Column("limits", JSONB(), nullable=False),
        sa.Column("features", JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_plans_code", "plans", ["code"], unique=True)

    op.create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            UUID(as_uuid=True),
            sa.ForeignKey("plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("billing_cycle", sa.String(16), server_default="monthly", nullable=False),
        sa.Column("provider", sa.String(32), server_default="manual", nullable=False),
        sa.Column("provider_sub_id", sa.String(120), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "usage_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric", sa.String(48), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("period_ym", sa.String(7), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_usage_org_period_metric",
        "usage_records",
        ["organization_id", "period_ym", "metric"],
    )

    # Seed standard Cortex SaaS plans
    op.execute(
        """
        INSERT INTO plans (id, code, name, monthly_price_inr, annual_price_inr, limits, features, is_active, created_at, updated_at)
        VALUES
            ('10000000-0000-0000-0000-000000000001', 'free', 'Free — Individual', 0, 0, '{"max_repos": 1, "max_ai_queries_per_month": 50, "max_doc_uploads": 5}', '{"byok_enabled": false, "graph_enabled": true, "audit_logs_enabled": false}', true, NOW(), NOW()),
            ('10000000-0000-0000-0000-000000000002', 'pro', 'Pro — Individual', 799, 7990, '{"max_repos": 10, "max_ai_queries_per_month": 500, "max_doc_uploads": 50}', '{"byok_enabled": false, "graph_enabled": true, "audit_logs_enabled": false}', true, NOW(), NOW()),
            ('10000000-0000-0000-0000-000000000003', 'team', 'Team — Startups & Agencies', 4999, 49990, '{"max_repos": 50, "max_ai_queries_per_month": 3000, "max_doc_uploads": 250}', '{"byok_enabled": true, "graph_enabled": true, "audit_logs_enabled": true}', true, NOW(), NOW()),
            ('10000000-0000-0000-0000-000000000004', 'business', 'Business', 14999, 149990, '{"max_repos": 200, "max_ai_queries_per_month": 15000, "max_doc_uploads": 1000}', '{"byok_enabled": true, "graph_enabled": true, "audit_logs_enabled": true}', true, NOW(), NOW()),
            ('10000000-0000-0000-0000-000000000005', 'enterprise', 'Enterprise', 0, 0, '{"max_repos": -1, "max_ai_queries_per_month": -1, "max_doc_uploads": -1}', '{"byok_enabled": true, "graph_enabled": true, "audit_logs_enabled": true}', true, NOW(), NOW())
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO subscriptions (id, organization_id, plan_id, status, billing_cycle, provider, created_at, updated_at)
        SELECT
            o.id,
            o.id,
            '10000000-0000-0000-0000-000000000001',
            'active',
            'monthly',
            'manual',
            NOW(),
            NOW()
        FROM organizations o
        WHERE NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.organization_id = o.id);
        """
    )


def downgrade() -> None:
    op.drop_index("ix_usage_org_period_metric", table_name="usage_records")
    op.drop_table("usage_records")
    op.drop_table("subscriptions")
    op.drop_index("ix_plans_code", table_name="plans")
    op.drop_table("plans")
