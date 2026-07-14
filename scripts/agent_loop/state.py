from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from schemas import load_json, write_json


def load_state(path: Path) -> dict[str, Any]:
    return load_json(path)


def save_state(path: Path, state: dict[str, Any]) -> None:
    state["last_run_id"] = (
        f"{datetime.now(UTC).isoformat()}-{uuid.uuid4().hex[:8]}"
    )
    write_json(path, state)


def next_step(contract: dict[str, Any], state: dict[str, Any]) -> str | None:
    completed = set(state.get("completed_steps", []))
    for step in contract["required_steps"]:
        if step not in completed:
            return str(step)
    return None


def append_artifact(state: dict[str, Any], bucket: str, path: Path) -> None:
    artifacts = state.setdefault("artifacts", {})
    values = artifacts.setdefault(bucket, [])
    values.append(str(path))
