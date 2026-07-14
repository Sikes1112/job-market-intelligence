from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LoopPaths:
    repo_root: Path
    layer_dir: Path
    run_dir: Path
    schema_dir: Path

    @classmethod
    def build(cls, repo_root: Path) -> LoopPaths:
        root = repo_root.resolve()
        return cls(
            repo_root=root,
            layer_dir=root / "docs" / "implementation" / "layer_34c",
            run_dir=root / ".agent_loop" / "layer_34c",
            schema_dir=root / "scripts" / "agent_loop" / "output_schemas",
        )


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(path)
