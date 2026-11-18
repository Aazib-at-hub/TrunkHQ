"""
Unit tests for Phase 9 Billing, Entitlements, and Webhook Signature Verification.
"""

from __future__ import annotations

import hashlib
import hmac

from app.api.router import api_router
from app.api.v1.billing import verify_billing_signature


def test_billing_routes_registered() -> None:
    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/api/v1/billing/plans" in paths
    assert "/api/v1/billing/subscription" in paths
    assert "/api/v1/billing/webhook" in paths


def test_verify_billing_signature() -> None:
    secret = "billing-secret-key"
    payload = b'{"organization_id":"123","plan_code":"team","status":"active"}'
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    assert verify_billing_signature(payload, sig, secret) is True
    assert verify_billing_signature(payload, f"sha256={sig}", secret) is True
    assert verify_billing_signature(payload, "invalid-sig", secret) is False
    assert verify_billing_signature(payload, None, secret) is False
