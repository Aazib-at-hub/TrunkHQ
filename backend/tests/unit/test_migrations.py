"""
Tests ensuring Alembic migration revisions can be loaded and have consistent chain references.
"""

import importlib.util
from pathlib import Path


def _load_migration_module(filename: str):
    versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    file_path = versions_dir / filename
    spec = importlib.util.spec_from_file_location(filename[:-3], file_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migration_chain() -> None:
    """Verify migration down_revision chaining."""
    m1 = _load_migration_module("001_initial_schema.py")
    m2 = _load_migration_module("002_relationship_graph.py")

    assert m1.revision == "001_initial_schema"
    assert m1.down_revision is None

    assert m2.revision == "002_relationship_graph"
    assert m2.down_revision == "001_initial_schema"
