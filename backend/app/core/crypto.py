"""
TrunkHQ — Symmetric Encryption Helpers for Customer Secrets (BYOK / OAuth).
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _get_fernet() -> Fernet:
    secret = get_settings().jwt_secret_key.encode("utf-8")
    digest = hashlib.sha256(secret).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a sensitive token or BYOK API key for database storage."""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a stored token or BYOK API key for server-side execution only."""
    return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def mask_secret(plaintext: str) -> str:
    """Return a non-recoverable display mask (e.g. sk-...abcd)."""
    cleaned = plaintext.strip()
    if len(cleaned) <= 8:
        return "****"
    return f"{cleaned[:4]}...{cleaned[-4:]}"
