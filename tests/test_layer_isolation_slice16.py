"""Static checks that Slice 16 audit modules stay layer-clean."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

SLICE_16_FILES = [
    BACKEND / "audit" / "types.py",
    BACKEND / "audit" / "exceptions.py",
    BACKEND / "audit" / "payloads.py",
    BACKEND / "audit" / "checks.py",
    BACKEND / "audit" / "service.py",
    BACKEND / "orchestration" / "jobs" / "audit.py",
]

FORBIDDEN_FRAGMENTS = (
    # Domain SERVICES (and scoring/personalization formulas) are forbidden.
    # The audit reads ORM models directly — never via service code.
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
    "backend.outputs.service",
    "backend.outputs.region_output",
    "backend.outputs.company_output",
    "backend.outputs.comparison_output",
    "backend.personalization.service",
    "backend.personalization.scoring",
    # Queue/runtime execution + event router/invalidation
    "backend.orchestration.queues.service",
    "backend.orchestration.workers.runner",
    "backend.orchestration.workers.registry",
    "backend.orchestration.events.router",
    "backend.orchestration.invalidation.service",
    "backend.orchestration.invalidation.rules",
    # API layer
    "backend.api",
    # External execution / scraping / NLP / chart libs / HTTP clients
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


def test_every_slice16_file_exists() -> None:
    for path in SLICE_16_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice16_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_16_FILES:
        bad = [
            name
            for name in _imports(path)
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS)
        ]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_audit_modules_define_no_routes_or_workers() -> None:
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
    for path in SLICE_16_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_audit_checks_module_only_imports_models_and_payloads() -> None:
    """The check functions must read ORM model classes only — no service
    or scoring imports anywhere in the call graph."""
    text = (BACKEND / "audit" / "checks.py").read_text()
    forbidden_imports = (
        "from backend.companies.service",
        "from backend.geography.service",
        "from backend.presence.service",
        "from backend.presence.evidence",
        "from backend.hiring.service",
        "from backend.entry_level.service",
        "from backend.entry_level.scoring",
        "from backend.scoring.service",
        "from backend.outputs.service",
        "from backend.personalization.service",
        "from backend.personalization.scoring",
    )
    for f in forbidden_imports:
        assert f not in text, f"checks.py imports {f!r}"


def test_audit_handler_not_in_default_worker_registry() -> None:
    """Slice 16 explicitly does not register JobType.AUDIT in Slice 14's
    default registry. The handler is callable directly; auto-dispatch via
    the runtime is deferred."""
    text = (BACKEND / "orchestration" / "workers" / "registry.py").read_text()
    assert "JobType.AUDIT" not in text
    assert "handle_audit" not in text
