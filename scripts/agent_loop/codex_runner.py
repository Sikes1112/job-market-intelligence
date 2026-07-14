from __future__ import annotations

import os
import subprocess
from pathlib import Path


class CodexRunError(RuntimeError):
    pass


def _base_command(
    *,
    repo_root: Path,
    sandbox: str,
    schema_path: Path,
    output_path: Path,
) -> list[str]:
    command = [
        "codex",
        "exec",
        "--ephemeral",
        "--sandbox",
        sandbox,
        "--cd",
        str(repo_root),
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(output_path),
    ]

    profile = os.environ.get("CODEX_PROFILE", "").strip()
    model = os.environ.get("CODEX_MODEL", "").strip()

    if profile:
        command.extend(["--profile", profile])
    if model:
        command.extend(["--model", model])

    command.append("-")
    return command


def run_codex(
    *,
    repo_root: Path,
    sandbox: str,
    schema_path: Path,
    output_path: Path,
    prompt: str,
    extra_env: dict[str, str] | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    result = subprocess.run(
        _base_command(
            repo_root=repo_root,
            sandbox=sandbox,
            schema_path=schema_path,
            output_path=output_path,
        ),
        cwd=repo_root,
        input=prompt,
        text=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise CodexRunError(f"Codex exited with code {result.returncode}")
    if not output_path.exists():
        raise CodexRunError(f"Codex did not write {output_path}")
