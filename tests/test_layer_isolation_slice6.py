"""Static checks that Slice 6 company-domain modules stay layer-clean."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

SLICE_6_FILES = [
    BACKEND / "companies" / "types.py",
    BACKEND / "companies" / "exceptions.py",
    BACKEND / "companies" / "overrides.py",
    BACKEND / "companies" / "repository.py",
    BACKEND / "companies" / "classification.py",
    BACKEND / "companies" / "service.py",
    BACKEND / "orchestration" / "jobs" / "eligibility_classification.py",
]

FORBIDDEN_FRAGMENTS = (
    # Other domain layers
    "backend.geography.service",
    "backend.geography.repository",
    "backend.presence",
    "backend.hiring",
    "backend.entry_level",
    "backend.scoring",
    "backend.outputs",
    "backend.personalization",
    "backend.audit",
    # API layer
    "backend.api",
    # Worker / queue runtime
    "backend.orchestration.queues",
    "backend.orchestration.workers",
    "backend.orchestration.scheduler",
    "backend.orchestration.invalidation",
    "backend.orchestration.state_machine",
    "backend.orchestration.events",  # event router runtime, not Slice 4 contract objects
    # External execution / ingestion
    "celery",
    "redis",
    "kombu",
    "fastapi",
    "uvicorn",
    "requests",
    "httpx",
)

# Slice 4 contract surface is allowed.
ALLOWED_ORCH_FRAGMENTS = (
    "backend.orchestration.jobs.envelopes",
    "backend.orchestration.jobs.errors",
    "backend.orchestration.jobs.types",
    "backend.orchestration.jobs.eligibility_classification",
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


def test_every_slice6_file_exists() -> None:
    for path in SLICE_6_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice6_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_6_FILES:
        bad = []
        for name in _imports(path):
            if any(allowed in name for allowed in ALLOWED_ORCH_FRAGMENTS):
                continue
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS):
                bad.append(name)
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_company_modules_define_no_routes_or_workers() -> None:
    forbidden_substrings = (
        "APIRouter",
        "@router.",
        "@app.",
        "FastAPI(",
        "Celery(",
        ".enqueue(",
        ".delay(",
    )
    for path in SLICE_6_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_company_service_stays_in_company_domain() -> None:
    """The service module must not reach into other domain models."""
    text = (BACKEND / "companies" / "service.py").read_text()
    forbidden_models = (
        "from backend.geography",
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
