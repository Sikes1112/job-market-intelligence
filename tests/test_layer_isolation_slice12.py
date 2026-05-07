"""Static checks that Slice 12 API-layer modules stay layer-clean."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

SLICE_12_FILES = [
    BACKEND / "api" / "app.py",
    BACKEND / "api" / "dependencies.py",
    BACKEND / "api" / "envelope.py",
    BACKEND / "api" / "routes.py",
]

FORBIDDEN_FRAGMENTS = (
    # Personalization, audit, contextual challenge — all deferred slices
    "backend.personalization",
    "backend.audit",
    # Upstream domain SERVICES are forbidden in API routes — Slice 12 reads
    # through Slice 11 and through narrow read repositories.
    "backend.companies.service",
    "backend.companies.classification",
    "backend.companies.overrides",
    "backend.geography.service",
    "backend.presence.service",
    "backend.presence.evidence",
    "backend.hiring.service",
    "backend.hiring.role_families",
    "backend.entry_level.service",
    "backend.entry_level.scoring",
    "backend.scoring.service",
    "backend.scoring.normalization",
    "backend.scoring.rulesets",
    # Worker / queue runtime
    "backend.orchestration.queues",
    "backend.orchestration.workers",
    "backend.orchestration.scheduler",
    "backend.orchestration.invalidation",
    "backend.orchestration.state_machine",
    "backend.orchestration.events",
    # External execution / scraping / NLP / chart libs
    "celery",
    "redis",
    "kombu",
    "uvicorn",  # uvicorn is a runtime, not imported by the app module
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
    "matplotlib",
    "plotly",
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


def test_every_slice12_file_exists() -> None:
    for path in SLICE_12_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice12_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_12_FILES:
        bad = [
            name
            for name in _imports(path)
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS)
        ]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_routes_use_output_assembly_service_for_full_payloads() -> None:
    """Routes for /regions/{id}, /companies/{id}, /compare must route
    through OutputAssemblyService — they must not assemble payloads
    inline."""
    text = (BACKEND / "api" / "routes.py").read_text()
    assert "OutputAssemblyService" in text
    assert "build_region" in text
    assert "build_company" in text
    assert "build_comparison" in text


def test_api_does_not_import_upstream_services() -> None:
    """Specifically forbid all six upstream service modules in any API file."""
    for path in SLICE_12_FILES:
        text = path.read_text()
        for forbidden in (
            "from backend.companies.service",
            "from backend.geography.service",
            "from backend.presence.service",
            "from backend.hiring.service",
            "from backend.entry_level.service",
            "from backend.scoring.service",
            "from backend.entry_level.scoring",
            "from backend.scoring.normalization",
            "from backend.scoring.rulesets",
        ):
            assert forbidden not in text, f"{path.name}: {forbidden!r}"
