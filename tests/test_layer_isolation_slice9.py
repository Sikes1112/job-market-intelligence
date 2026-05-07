"""Static checks that Slice 9 entry-level modules stay layer-clean."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

SLICE_9_FILES = [
    BACKEND / "entry_level" / "types.py",
    BACKEND / "entry_level" / "exceptions.py",
    BACKEND / "entry_level" / "scoring.py",
    BACKEND / "entry_level" / "repository.py",
    BACKEND / "entry_level" / "service.py",
    BACKEND / "orchestration" / "jobs" / "entry_level_refresh.py",
]

FORBIDDEN_FRAGMENTS = (
    # Downstream domains
    "backend.scoring",
    "backend.outputs",
    "backend.personalization",
    "backend.audit",
    # Upstream service / classification logic
    "backend.companies.service",
    "backend.companies.classification",
    "backend.companies.overrides",
    "backend.geography.service",
    "backend.presence.service",
    "backend.presence.evidence",
    "backend.hiring.service",
    "backend.hiring.role_families",
    # API layer
    "backend.api",
    # Worker / queue runtime
    "backend.orchestration.queues",
    "backend.orchestration.workers",
    "backend.orchestration.scheduler",
    "backend.orchestration.invalidation",
    "backend.orchestration.state_machine",
    "backend.orchestration.events",
    # External execution / NLP / scraping
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
    "backend.orchestration.jobs.entry_level_refresh",
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


def test_every_slice9_file_exists() -> None:
    for path in SLICE_9_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice9_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_9_FILES:
        bad = []
        for name in _imports(path):
            if any(allowed in name for allowed in ALLOWED_ORCH_FRAGMENTS):
                continue
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS):
                bad.append(name)
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_entry_level_modules_define_no_routes_or_workers() -> None:
    forbidden_substrings = (
        "APIRouter",
        "@router.",
        "@app.",
        "FastAPI(",
        "Celery(",
        ".enqueue(",
        ".delay(",
    )
    for path in SLICE_9_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_scoring_module_does_not_import_business_layers() -> None:
    """Slice 9 scoring formula must be isolated."""
    text = (BACKEND / "entry_level" / "scoring.py").read_text()
    assert "from backend.scoring" not in text
    assert "from backend.outputs" not in text
    assert "from backend.personalization" not in text
    assert "from backend.hiring" not in text
    assert "from backend.audit" not in text


def test_service_uses_only_hiring_repository_not_service() -> None:
    """Slice 9 service must use HiringRepository, not HiringService."""
    text = (BACKEND / "entry_level" / "service.py").read_text()
    assert "from backend.hiring.service" not in text
    assert "from backend.hiring.role_families" not in text
    assert "from backend.hiring.repository" in text
