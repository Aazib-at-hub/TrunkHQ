"""
TrunkHQ — Git Repository Cloner.

Handles cloning public GitHub repositories into isolated directories
using Git CLI with shallow clone (--depth 1) for speed and disk economy.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Optional

from app.core.exceptions import ValidationError
from app.core.logging import get_logger

logger = get_logger("cloner")

GITHUB_URL_REGEX = re.compile(
    r"^https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?/?$"
)


def validate_github_url(url: str) -> tuple[str, str]:
    """
    Validate that the given string is a valid GitHub repository URL.

    Returns:
        tuple[owner, repo_name]
    """
    cleaned = url.strip()
    match = GITHUB_URL_REGEX.match(cleaned)
    if not match:
        raise ValidationError(
            f"Invalid GitHub repository URL '{url}'. Expected format: https://github.com/owner/repository"
        )
    owner, repo = match.group(1), match.group(2)
    return owner, repo


def force_rm_directory(target_dir: Path) -> None:
    """Remove a directory tree, clearing Windows read-only attributes (e.g. .git pack files)."""
    if not target_dir.exists():
        return

    def _force_rm(action, name, exc):
        try:
            os.chmod(name, stat.S_IWRITE)
            os.remove(name)
        except Exception:
            pass

    shutil.rmtree(target_dir, onerror=_force_rm)


async def clone_repository(
    github_url: str,
    target_dir: Path,
    branch: str = "main",
    timeout_seconds: int = 120,
    github_token: Optional[str] = None,
) -> Path:
    """
    Clone a git repository shallowly into target_dir.

    Args:
        github_url: HTTPS GitHub URL.
        target_dir: Local destination path.
        branch: Branch name to clone.
        timeout_seconds: Timeout for git command.
        github_token: Optional GitHub PAT for private repositories.

    Returns:
        Path to cloned directory.
    """
    owner, repo_name = validate_github_url(github_url)

    # Validate branch name to prevent git CLI option injection
    safe_branch = branch.strip() if branch else "main"
    if safe_branch.startswith("-") or ".." in safe_branch or not re.match(r"^[a-zA-Z0-9._/-]+$", safe_branch):
        raise ValidationError(f"Invalid branch name '{branch}'. Cannot start with '-' or contain '..'")

    if target_dir.exists():
        logger.info("Cleaning up existing target directory", path=str(target_dir))
        force_rm_directory(target_dir)

    target_dir.parent.mkdir(parents=True, exist_ok=True)

    # Format normalized clone URL (never log clone_url when token is present)
    safe_display_url = f"https://github.com/{owner}/{repo_name}.git"
    clone_url = (
        f"https://x-access-token:{github_token}@github.com/{owner}/{repo_name}.git"
        if github_token
        else safe_display_url
    )

    # Try requested branch first, fallback to default branch if requested branch fails
    cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        safe_branch,
        "--",
        clone_url,
        str(target_dir),
    ]

    logger.info(
        "Cloning repository",
        repo=f"{owner}/{repo_name}",
        branch=safe_branch,
        dest=str(target_dir),
    )

    try:
        completed = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        force_rm_directory(target_dir)
        raise RuntimeError(f"Cloning {safe_display_url} timed out after {timeout_seconds}s")

    if completed.returncode != 0:
        # If specific branch failed, try clone without --branch to get default
        stderr_msg = completed.stderr.decode("utf-8", errors="ignore")
        if github_token:
            stderr_msg = stderr_msg.replace(github_token, "***")
        logger.warning(
            "Clone with specified branch failed, retrying with default branch",
            error=stderr_msg,
        )

        # Ensure directory created by failed clone is cleaned before retry
        force_rm_directory(target_dir)

        fallback_cmd = [
            "git",
            "clone",
            "--depth",
            "1",
            "--",
            clone_url,
            str(target_dir),
        ]

        try:
            fallback_completed = await asyncio.to_thread(
                subprocess.run,
                fallback_cmd,
                capture_output=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            force_rm_directory(target_dir)
            raise RuntimeError(f"Fallback clone timed out after {timeout_seconds}s")

        if fallback_completed.returncode != 0:
            err = fallback_completed.stderr.decode("utf-8", errors="ignore")
            if github_token:
                err = err.replace(github_token, "***")
            force_rm_directory(target_dir)
            raise RuntimeError(f"Git clone failed: {err.strip()}")

    logger.info("Clone completed successfully", dest=str(target_dir))
    return target_dir


async def get_head_commit_sha(repo_dir: Path, timeout_seconds: int = 10) -> Optional[str]:
    """Return the HEAD commit SHA for a cloned git repository, or None on failure."""
    if not repo_dir.exists():
        return None
    try:
        completed = await asyncio.to_thread(
            subprocess.run,
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True,
            timeout=timeout_seconds,
        )
        if completed.returncode == 0:
            sha = completed.stdout.decode("utf-8", errors="ignore").strip()
            return sha or None
    except Exception as exc:
        logger.warning("Failed to resolve HEAD commit SHA", path=str(repo_dir), error=str(exc))
    return None
