"""Static checks that Slice 17 contextual-challenge modules stay layer-clean."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

SLICE_17_FILES = [
    BACKEND / "outputs" / "contextual_challenge.py",
    BACKEND / "orchestration" / "jobs" / "contextual_challenge_build.py",
]

FORBIDDEN_FRAGMENTS = (
    # Downstream / sibling slices
    "backend.personalization",
    "backend.audit",
    # Upstream domain SERVICES are forbidden — Slice 17 reads through
    # repositories only and consumes stored RegionMarketScore values.
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
    "backend.scoring.service",       # Slice 10 formula must not leak in
    "backend.scoring.normalization",
    "backend.scoring.rulesets",
    # Slice 11 output service must not be consulted: contextual challenge
    # is its own writer of OutputMetadata rows.
    "backend.outputs.service",
    "backend.outputs.region_output",
    "backend.outputs.company_output",
    # API + queue/worker runtime + event router/invalidation
    "backend.api",
    "backend.orchestration.queues",
    "backend.orchestration.workers",
    "backend.orchestration.scheduler",
    "backend.orchestration.invalidation",
    "backend.orchestration.events",
    # External execution / NLP / scraping / ML / chart libs
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
    "matplotlib",
    "plotly",
)

ALLOWED_ORCH_FRAGMENTS = (
    "backend.orchestration.jobs.envelopes",
    "backend.orchestration.jobs.errors",
    "backend.orchestration.jobs.types",
    "backend.orchestration.jobs.contextual_challenge_build",
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


def test_every_slice17_file_exists() -> None:
    for path in SLICE_17_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice17_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_17_FILES:
        bad = []
        for name in _imports(path):
            if any(allowed in name for allowed in ALLOWED_ORCH_FRAGMENTS):
                continue
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS):
                bad.append(name)
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_contextual_modules_define_no_routes_or_workers() -> None:
    forbidden_substrings = (
        "APIRouter",
        "@router.",
        "@app.",
        "FastAPI(",
        "Celery(",
        ".enqueue(",
        ".delay(",
        "Thread(",
        "Process(",
    )
    for path in SLICE_17_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_contextual_module_does_not_import_scoring_or_outputs_service() -> None:
    """The pure builder + service must read RegionMarketScore via the
    scoring repository only — never via Slice 10's formula modules or
    Slice 11's output service."""
    text = (BACKEND / "outputs" / "contextual_challenge.py").read_text()
    for forbidden in (
        "from backend.scoring.service",
        "from backend.scoring.normalization",
        "from backend.scoring.rulesets",
        "from backend.outputs.service",
        "from backend.outputs.region_output",
        "from backend.outputs.company_output",
        "from backend.entry_level.scoring",
    ):
        assert forbidden not in text, f"contextual_challenge.py imports {forbidden!r}"


def test_contextual_handler_not_in_default_worker_registry() -> None:
    """Slice 17 explicitly does not register CONTEXTUAL_CHALLENGE_BUILD in
    Slice 14's default registry. The handler is callable directly;
    auto-dispatch via the runtime is deferred."""
    text = (BACKEND / "orchestration" / "workers" / "registry.py").read_text()
    assert "JobType.CONTEXTUAL_CHALLENGE_BUILD" not in text
    assert "handle_contextual_challenge_build" not in text
