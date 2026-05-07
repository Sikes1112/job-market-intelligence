"""Static checks that Slice 3 primitive modules stay free of business layers."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED = REPO_ROOT / "backend" / "shared"

SLICE_3_FILES = [
    SHARED / "state.py",
    SHARED / "versioning.py",
    SHARED / "freshness.py",
    SHARED / "confidence.py",
]

FORBIDDEN_FRAGMENTS = (
    "backend.api",
    "backend.personalization",
    "backend.audit",
    "backend.outputs",
    "backend.scoring.service",
    "backend.scoring.rulesets",
    "backend.scoring.normalization",
    "backend.geography.service",
    "backend.companies.service",
    "backend.presence.service",
    "backend.hiring.service",
    "backend.entry_level.service",
    "backend.orchestration.queues",
    "backend.orchestration.workers",
    "backend.orchestration.scheduler",
    "backend.orchestration.events",
    "backend.orchestration.invalidation",
    "backend.orchestration.jobs",
    "fastapi",
    "uvicorn",
    "celery",
    "sqlalchemy",  # primitives are pure Python; no DB coupling
)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.append(module)
            names.extend(f"{module}.{alias.name}" for alias in node.names)
    return names


def test_every_slice3_file_exists() -> None:
    for path in SLICE_3_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice3_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_3_FILES:
        bad = [
            name
            for name in _imports(path)
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS)
        ]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_slice3_modules_define_no_routes_or_decorators_from_web_layer() -> None:
    forbidden_substrings = (
        "APIRouter",
        "@router.",
        "@app.",
        "FastAPI(",
    )
    for path in SLICE_3_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"
