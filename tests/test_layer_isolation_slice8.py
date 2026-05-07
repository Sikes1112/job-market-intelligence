"""Static checks that Slice 8 hiring-domain modules stay layer-clean."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

SLICE_8_FILES = [
    BACKEND / "hiring" / "types.py",
    BACKEND / "hiring" / "exceptions.py",
    BACKEND / "hiring" / "time_windows.py",
    BACKEND / "hiring" / "role_families.py",
    BACKEND / "hiring" / "repository.py",
    BACKEND / "hiring" / "service.py",
    BACKEND / "orchestration" / "jobs" / "hiring_refresh.py",
]

FORBIDDEN_FRAGMENTS = (
    # Downstream domains
    "backend.entry_level",
    "backend.scoring",
    "backend.outputs",
    "backend.personalization",
    "backend.audit",
    # Upstream service / classification logic — hiring uses repositories only
    "backend.companies.service",
    "backend.companies.classification",
    "backend.companies.overrides",
    "backend.geography.service",
    "backend.presence.service",
    "backend.presence.evidence",
    # API layer
    "backend.api",
    # Worker / queue runtime
    "backend.orchestration.queues",
    "backend.orchestration.workers",
    "backend.orchestration.scheduler",
    "backend.orchestration.invalidation",
    "backend.orchestration.state_machine",
    "backend.orchestration.events",
    # External execution / scraping / NLP
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
    "openai",
    "anthropic",
    "transformers",
    "spacy",
)

ALLOWED_ORCH_FRAGMENTS = (
    "backend.orchestration.jobs.envelopes",
    "backend.orchestration.jobs.errors",
    "backend.orchestration.jobs.types",
    "backend.orchestration.jobs.hiring_refresh",
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


def test_every_slice8_file_exists() -> None:
    for path in SLICE_8_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice8_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_8_FILES:
        bad = []
        for name in _imports(path):
            if any(allowed in name for allowed in ALLOWED_ORCH_FRAGMENTS):
                continue
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS):
                bad.append(name)
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_hiring_modules_define_no_routes_or_workers() -> None:
    forbidden_substrings = (
        "APIRouter",
        "@router.",
        "@app.",
        "FastAPI(",
        "Celery(",
        ".enqueue(",
        ".delay(",
    )
    for path in SLICE_8_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_hiring_service_uses_only_presence_repository_not_service() -> None:
    """The service may consult the presence repository for existence, but
    must not import the presence service or evidence module (which would
    re-run presence rule evaluation)."""
    text = (BACKEND / "hiring" / "service.py").read_text()
    assert "from backend.presence.service" not in text
    assert "from backend.presence.evidence" not in text
    assert "from backend.presence.repository" in text
