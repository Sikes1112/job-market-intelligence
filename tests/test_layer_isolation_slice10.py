"""Static checks that Slice 10 scoring modules stay layer-clean."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

SLICE_10_FILES = [
    BACKEND / "scoring" / "types.py",
    BACKEND / "scoring" / "exceptions.py",
    BACKEND / "scoring" / "rulesets.py",
    BACKEND / "scoring" / "normalization.py",
    BACKEND / "scoring" / "repository.py",
    BACKEND / "scoring" / "service.py",
    BACKEND / "orchestration" / "jobs" / "region_score_recompute.py",
]

FORBIDDEN_FRAGMENTS = (
    # Downstream domains
    "backend.outputs",
    "backend.personalization",
    "backend.audit",
    # Upstream services — scoring reads through repositories only
    "backend.companies.service",
    "backend.companies.classification",
    "backend.companies.overrides",
    "backend.geography.service",
    "backend.presence.service",
    "backend.presence.evidence",
    "backend.hiring.service",
    "backend.hiring.role_families",
    "backend.entry_level.service",
    "backend.entry_level.scoring",  # Slice 9 formula, must not be a hidden dependency
    # API layer
    "backend.api",
    # Worker / queue runtime
    "backend.orchestration.queues",
    "backend.orchestration.workers",
    "backend.orchestration.scheduler",
    "backend.orchestration.invalidation",
    "backend.orchestration.state_machine",
    "backend.orchestration.events",
    # External execution
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
    "sklearn",
    "torch",
)

ALLOWED_ORCH_FRAGMENTS = (
    "backend.orchestration.jobs.envelopes",
    "backend.orchestration.jobs.errors",
    "backend.orchestration.jobs.types",
    "backend.orchestration.jobs.region_score_recompute",
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


def test_every_slice10_file_exists() -> None:
    for path in SLICE_10_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice10_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_10_FILES:
        bad = []
        for name in _imports(path):
            if any(allowed in name for allowed in ALLOWED_ORCH_FRAGMENTS):
                continue
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS):
                bad.append(name)
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_scoring_modules_define_no_routes_or_workers() -> None:
    forbidden_substrings = (
        "APIRouter",
        "@router.",
        "@app.",
        "FastAPI(",
        "Celery(",
        ".enqueue(",
        ".delay(",
    )
    for path in SLICE_10_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_normalization_is_pure_python() -> None:
    """The normalization module must not import the SQLAlchemy stack or any
    business layer — it's pure scalar math."""
    text = (BACKEND / "scoring" / "normalization.py").read_text()
    assert "import sqlalchemy" not in text
    assert "from sqlalchemy" not in text
    assert "from backend.companies" not in text
    assert "from backend.hiring" not in text
    assert "from backend.entry_level" not in text


def test_service_does_not_import_entry_level_scoring_formula() -> None:
    """Slice 10 must read stored entry_level_access_score, never recompute
    via Slice 9's scoring formula."""
    text = (BACKEND / "scoring" / "service.py").read_text()
    assert "from backend.entry_level.scoring" not in text


def test_service_uses_only_repositories_from_upstream_domains() -> None:
    text = (BACKEND / "scoring" / "service.py").read_text()
    forbidden_services = (
        "from backend.companies.service",
        "from backend.presence.service",
        "from backend.hiring.service",
        "from backend.entry_level.service",
    )
    for sub in forbidden_services:
        assert sub not in text, f"service imports forbidden upstream service: {sub!r}"
