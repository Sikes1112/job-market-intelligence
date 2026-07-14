from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: str
    cwd: str
    exit_code: int
    stdout_tail: str
    stderr_tail: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


def _tail(value: str, limit: int = 12000) -> str:
    return value[-limit:]


def run_command(name: str, command: str, cwd: Path) -> CommandResult:
    result = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        executable="/bin/bash",
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )
    return CommandResult(
        name=name,
        command=command,
        cwd=str(cwd),
        exit_code=result.returncode,
        stdout_tail=_tail(result.stdout),
        stderr_tail=_tail(result.stderr),
    )


def default_full_verification(repo_root: Path) -> list[CommandResult]:
    frontend = repo_root / "frontend"
    commands: list[tuple[str, str, Path]] = [
        ("full_backend", "python3 -m pytest -q", repo_root),
        (
            "backend_lint",
            "python3 -m ruff check alembic backend scripts tests",
            repo_root,
        ),
        (
            "compile",
            "python3 -m compileall -q backend tests alembic scripts",
            repo_root,
        ),
        ("frontend_tests", "npm test", frontend),
        ("frontend_lint", "npm run lint", frontend),
        ("frontend_build", "npm run build", frontend),
        ("public_demo_smoke", "npm run smoke:public-demo", frontend),
        ("git_diff_check", "git diff --check", repo_root),
    ]
    return [run_command(name, command, cwd) for name, command, cwd in commands]


def results_to_json(results: Iterable[CommandResult]) -> dict:
    values = [asdict(result) | {"passed": result.passed} for result in results]
    return {
        "passed": all(item["passed"] for item in values),
        "results": values,
    }
