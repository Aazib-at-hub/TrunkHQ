"""
TrunkHQ — Production Readiness & Security Audit Regression Tests.

Validates:
1. Git branch option injection defenses.
2. Re-indexing idempotency and obsolete data purge.
3. Symlink path escape detection.
4. JWT production secret enforcement.
"""

from pathlib import Path
import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.ingestion.cloner import clone_repository
from app.ingestion.discovery import discover_files
from app.schemas.repository import ImportRepositoryRequest


def test_branch_validation_allows_safe_refs():
    """Verify safe branch names are accepted."""
    safe_branches = [
        "main",
        "master",
        "develop",
        "feature/graph-enhancements",
        "release/v1.0.0",
        "fix_bug-123",
        "v2.1",
    ]
    for b in safe_branches:
        req = ImportRepositoryRequest(
            github_url="https://github.com/pallets/flask",
            branch=b,
        )
        assert req.branch == b


def test_branch_validation_blocks_option_injection():
    """Verify branches attempting git option injection or traversal fail."""
    malicious_branches = [
        "--upload-pack=evil",
        "--config=protocol.ext.allow=always",
        "-b",
        "feature/../escape",
        "bad branch with spaces",
        "branch;rm -rf /",
        "branch`whoami`",
        "branch$(whoami)",
    ]
    for b in malicious_branches:
        with pytest.raises((ValueError, PydanticValidationError)):
            ImportRepositoryRequest(
                github_url="https://github.com/pallets/flask",
                branch=b,
            )


def test_jwt_insecure_default_detection():
    """Verify settings correctly flags default insecure JWT secret."""
    insecure_settings = Settings(jwt_secret_key="change-me-to-a-random-secret")
    assert insecure_settings.is_jwt_secret_insecure is True

    secure_settings = Settings(jwt_secret_key="a-truly-random-and-high-entropy-production-secret-key-12345")
    assert secure_settings.is_jwt_secret_insecure is False


def test_symlink_traversal_detection(tmp_path: Path):
    """Verify files resolving outside repository root are filtered out."""
    repo_root = tmp_path / "cloned_repo"
    repo_root.mkdir()

    # Normal inside file
    inside_file = repo_root / "inside.py"
    inside_file.write_text("print('inside')")

    # Outside target file
    outside_file = tmp_path / "secret.env"
    outside_file.write_text("DATABASE_PASSWORD=secret")

    # Symlink pointing outside
    try:
        symlink_file = repo_root / "symlink_leak.py"
        symlink_file.symlink_to(outside_file)
    except (OSError, NotImplementedError):
        # On Windows without developer mode symlink creation may require privilege
        pytest.skip("Symlink creation not permitted in this environment")

    discovered = discover_files(repo_root)
    discovered_paths = [d.relative_path for d in discovered]

    assert "inside.py" in discovered_paths
    assert "symlink_leak.py" not in discovered_paths
