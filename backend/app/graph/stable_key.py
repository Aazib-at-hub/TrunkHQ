"""
Cortex Engineering — Deterministic Stable Key Generation.

Generates reproducible natural keys for graph entities to ensure
idempotent re-indexing, updates, and cross-commit reconciliation.
"""

from __future__ import annotations

import re
from uuid import UUID


def normalize_path(path: str) -> str:
    """Normalize file paths to forward-slash canonical relative form."""
    norm = path.replace("\\", "/").strip("/")
    # Eliminate any redundant segments
    parts = [p for p in norm.split("/") if p and p != "."]
    return "/".join(parts)


def make_file_key(repository_id: UUID, relative_path: str) -> str:
    """Generate stable natural key for a file entity."""
    return f"repo:{repository_id}:file:{normalize_path(relative_path)}"


def make_symbol_key(
    repository_id: UUID,
    relative_path: str,
    qualified_name: str,
    symbol_kind: str,
) -> str:
    """Generate stable natural key for code symbols (classes, functions, methods)."""
    norm_path = normalize_path(relative_path)
    clean_name = re.sub(r"\s+", "", qualified_name)
    return f"repo:{repository_id}:file:{norm_path}:symbol:{clean_name}:{symbol_kind.lower()}"


def make_service_key(repository_id: UUID, service_name: str) -> str:
    """Generate stable natural key for a service or container entity."""
    clean_name = re.sub(r"[^a-zA-Z0-9_-]", "-", service_name.lower().strip())
    return f"repo:{repository_id}:service:{clean_name}"


def make_endpoint_key(repository_id: UUID, method: str, path: str) -> str:
    """Generate stable natural key for an API endpoint."""
    norm_method = method.upper().strip()
    norm_path = path.strip()
    return f"repo:{repository_id}:endpoint:{norm_method}:{norm_path}"


def make_document_key(repository_id: UUID, relative_path: str) -> str:
    """Generate stable natural key for an engineering document."""
    return f"repo:{repository_id}:document:{normalize_path(relative_path)}"
