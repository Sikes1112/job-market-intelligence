"""Static checks that Slice 4 contract modules stay free of business layers."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

SLICE_4_FILES = [
    BACKEND / "orchestration" / "jobs" / "types.py",
    BACKEND / "orchestration" / "jobs" / "errors.py",
    BACKEND / "orchestration" / "jobs" / "envelopes.py",
    BACKEND / "orchestration" / "jobs" / "dedupe.py",
    BACKEND / "orchestration" / "events" / "recommendations.py",
    BACKEND / "orchestration" / "dependencies" / "refs.py",
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
    "backend.orchestration.invalidation",
    "backend.orchestration.state_machine",
    "fastapi",
    "uvicorn",
    "celery",
    "redis",
    "sqlalchemy",  # contracts must not couple to the storage stack
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


def test_every_slice4_file_exists() -> None:
    for path in SLICE_4_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice4_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_4_FILES:
        bad = [
            name
            for name in _imports(path)
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS)
        ]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_slice4_modules_define_no_routes_or_workers() -> None:
    forbidden_substrings = (
        "APIRouter",
        "@router.",
        "@app.",
        "FastAPI(",
        "Celery(",
        "task(",
        "enqueue(",
        ".enqueue(",
    )
    for path in SLICE_4_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_envelope_module_does_not_touch_jobs_table() -> None:
    """Slice 4 contract code must not reach into the Slice 2 Job ORM model."""
    text = (BACKEND / "orchestration" / "jobs" / "envelopes.py").read_text()
    assert "from backend.orchestration.jobs.models" not in text
    assert "Job(" not in text  # the SQLAlchemy class
