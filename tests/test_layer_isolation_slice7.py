"""Static checks that Slice 7 presence-domain modules stay layer-clean."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

SLICE_7_FILES = [
    BACKEND / "presence" / "types.py",
    BACKEND / "presence" / "exceptions.py",
    BACKEND / "presence" / "evidence.py",
    BACKEND / "presence" / "repository.py",
    BACKEND / "presence" / "service.py",
    BACKEND / "orchestration" / "jobs" / "presence_mapping.py",
]

FORBIDDEN_FRAGMENTS = (
    # Other domain layers downstream of presence
    "backend.hiring",
    "backend.entry_level",
    "backend.scoring",
    "backend.outputs",
    "backend.personalization",
    "backend.audit",
    # Service modules from upstream domains: presence is allowed to use the
    # repositories of company/geography for existence checks but must not call
    # their service classes (no classification, no geography building).
    "backend.companies.service",
    "backend.companies.classification",
    "backend.companies.overrides",
    "backend.geography.service",
    # API layer
    "backend.api",
    # Worker / queue runtime
    "backend.orchestration.queues",
    "backend.orchestration.workers",
    "backend.orchestration.scheduler",
    "backend.orchestration.invalidation",
    "backend.orchestration.state_machine",
    "backend.orchestration.events",
    # External execution / scraping / ingestion
    "celery",
    "redis",
    "kombu",
    "fastapi",
    "uvicorn",
    "requests",
    "httpx",
    "bs4",
    "selenium",
    "playwright",
)

# Slice 4 contract surface is allowed.
ALLOWED_ORCH_FRAGMENTS = (
    "backend.orchestration.jobs.envelopes",
    "backend.orchestration.jobs.errors",
    "backend.orchestration.jobs.types",
    "backend.orchestration.jobs.presence_mapping",
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


def test_every_slice7_file_exists() -> None:
    for path in SLICE_7_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice7_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_7_FILES:
        bad = []
        for name in _imports(path):
            if any(allowed in name for allowed in ALLOWED_ORCH_FRAGMENTS):
                continue
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS):
                bad.append(name)
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_presence_modules_define_no_routes_or_workers() -> None:
    forbidden_substrings = (
        "APIRouter",
        "@router.",
        "@app.",
        "FastAPI(",
        "Celery(",
        ".enqueue(",
        ".delay(",
    )
    for path in SLICE_7_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_presence_service_uses_only_repositories_from_upstream_domains() -> None:
    """The service may consult company/region repositories for existence,
    but must not call their services (which would do classification or
    geography-building work)."""
    text = (BACKEND / "presence" / "service.py").read_text()
    assert "from backend.companies.service" not in text
    assert "from backend.companies.classification" not in text
    assert "from backend.geography.service" not in text
    # Repositories are allowed.
    assert "from backend.companies.repository" in text
    assert "from backend.geography.repository" in text
