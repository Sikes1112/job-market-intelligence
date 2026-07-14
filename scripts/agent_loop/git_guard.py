from __future__ import annotations

import subprocess
from pathlib import Path


class GitGuardError(RuntimeError):
    pass


def run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise GitGuardError(result.stderr.strip() or "git command failed")
    return result.stdout


def current_head(repo_root: Path) -> str:
    return run_git(repo_root, "rev-parse", "HEAD").strip()


def status_short(repo_root: Path) -> str:
    return run_git(repo_root, "status", "--short")


def diff_check(repo_root: Path) -> None:
    result = subprocess.run(
        ["git", "diff", "--check"],
        cwd=repo_root,
        check=False,
    )
    if result.returncode != 0:
        raise GitGuardError("git diff --check failed")


def ensure_repository(repo_root: Path) -> None:
    run_git(repo_root, "rev-parse", "--show-toplevel")
