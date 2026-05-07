"""Static checks that Slice 5 geography service modules stay layer-clean."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

SLICE_5_FILES = [
    BACKEND / "geography" / "types.py",
    BACKEND / "geography" / "exceptions.py",
    BACKEND / "geography" / "repository.py",
    BACKEND / "geography" / "service.py",
    BACKEND / "orchestration" / "jobs" / "geography_build.py",
]

FORBIDDEN_FRAGMENTS = (
    # Other domain layers — geography stays self-contained
    "backend.companies",
    "backend.presence",
    "backend.hiring",
    "backend.entry_level",
    "backend.scoring",
    "backend.outputs",
    "backend.personalization",
    "backend.audit",
    # API layer
    "backend.api",
    # Worker / queue runtime that doesn't exist yet
    "backend.orchestration.queues",
    "backend.orchestration.workers",
    "backend.orchestration.scheduler",
    "backend.orchestration.invalidation",
    "backend.orchestration.state_machine",
    "backend.orchestration.events",  # event router/runtime, not contract objects
    # External execution machinery
    "celery",
    "redis",
    "kombu",
    "fastapi",
    "uvicorn",
)

# Slice 5 service may legitimately import these orchestration *contract* modules
# (Slice 4 surface) — they're allowed even though they live under
# backend.orchestration.
ALLOWED_ORCH_FRAGMENTS = (
    "backend.orchestration.jobs.envelopes",
    "backend.orchestration.jobs.errors",
    "backend.orchestration.jobs.types",
    "backend.orchestration.jobs.geography_build",
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


def test_every_slice5_file_exists() -> None:
    for path in SLICE_5_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice5_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_5_FILES:
        bad = []
        for name in _imports(path):
            if any(allowed in name for allowed in ALLOWED_ORCH_FRAGMENTS):
                continue
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS):
                bad.append(name)
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_geography_modules_define_no_routes_or_workers() -> None:
    forbidden_substrings = (
        "APIRouter",
        "@router.",
        "@app.",
        "FastAPI(",
        "Celery(",
        ".enqueue(",
        ".delay(",
    )
    for path in SLICE_5_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_geography_service_stays_in_geography_domain() -> None:
    """The service module must not reach into other domain models."""
    text = (BACKEND / "geography" / "service.py").read_text()
    forbidden_models = (
        "from backend.companies",
        "from backend.presence",
        "from backend.hiring",
        "from backend.entry_level",
        "from backend.scoring",
        "from backend.outputs",
        "from backend.personalization",
        "from backend.audit",
    )
    for sub in forbidden_models:
        assert sub not in text, f"service imports forbidden domain: {sub!r}"
