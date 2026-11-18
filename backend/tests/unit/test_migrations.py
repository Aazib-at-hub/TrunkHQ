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
    m3 = _load_migration_module("003_project_storage_house.py")
    m4 = _load_migration_module("004_hybrid_search_indexes.py")
    m5 = _load_migration_module("005_multi_tenancy_orgs.py")
    m6 = _load_migration_module("006_projects_table.py")
    m7 = _load_migration_module("007_documents_intelligence.py")
    m8 = _load_migration_module("008_audit_logs.py")
    m9 = _load_migration_module("009_billing_and_usage.py")
    m10 = _load_migration_module("010_knowledge_freshness.py")

    assert m1.revision == "001_initial_schema"
    assert m1.down_revision is None

    assert m2.revision == "002_relationship_graph"
    assert m2.down_revision == "001_initial_schema"

    assert m3.revision == "003_project_storage_house"
    assert m3.down_revision == "002_relationship_graph"

    assert m4.revision == "004_hybrid_search_indexes"
    assert m4.down_revision == "003_project_storage_house"

    assert m5.revision == "005_multi_tenancy_orgs"
    assert m5.down_revision == "004_hybrid_search_indexes"

    assert m6.revision == "006_projects_table"
    assert m6.down_revision == "005_multi_tenancy_orgs"

    assert m7.revision == "007_documents_intelligence"
    assert m7.down_revision == "006_projects_table"

    assert m8.revision == "008_audit_logs"
    assert m8.down_revision == "007_documents_intelligence"

    assert m9.revision == "009_billing_and_usage"
    assert m9.down_revision == "008_audit_logs"

    assert m10.revision == "010_knowledge_freshness"
    assert m10.down_revision == "009_billing_and_usage"

    # 004 must not drop ix_code_chunks_embedding_hnsw created in 001
    m4_src = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "004_hybrid_search_indexes.py"
    ).read_text(encoding="utf-8")
    downgrade_section = m4_src.split("def downgrade", 1)[1]
    assert "ix_code_chunks_embedding_hnsw" not in downgrade_section
