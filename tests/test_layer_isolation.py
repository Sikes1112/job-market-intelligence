"""Static checks that Slice 2 model modules do not reach into later-slice layers.

The model modules must remain pure schema declarations. They must not import
service code, scoring formulas, API routes, queue/worker runtime,
personalization, output assembly, or audit logic. Those layers do not exist
yet (and Slice 2 must not anticipate them with shims).
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

MODEL_FILES = [
    BACKEND / "geography" / "models.py",
    BACKEND / "companies" / "models.py",
    BACKEND / "presence" / "models.py",
    BACKEND / "hiring" / "models.py",
    BACKEND / "entry_level" / "models.py",
    BACKEND / "scoring" / "models.py",
    BACKEND / "orchestration" / "jobs" / "models.py",
    BACKEND / "outputs" / "models.py",
]

# Forbidden import-name fragments. If any model file imports from one of these,
# the layer separation is being violated.
FORBIDDEN_FRAGMENTS = (
    ".service",
    ".services",
    "backend.api",
    "backend.personalization",
    "backend.audit",
    "backend.orchestration.queues",
    "backend.orchestration.workers",
    "backend.orchestration.scheduler",
    "backend.orchestration.events",
    "backend.orchestration.invalidation",
    "backend.orchestration.state_machine",
    "backend.outputs.builder",
    "backend.outputs.region_output",
    "backend.outputs.company_output",
    "backend.outputs.comparison_output",
    "backend.scoring.service",
    "backend.scoring.rulesets",
    "backend.scoring.normalization",
    "fastapi",
    "uvicorn",
    "celery",
    "redis",
    "kombu",
)


def _module_imports(path: Path) -> list[str]:
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


def test_every_model_file_exists() -> None:
    for path in MODEL_FILES:
        assert path.exists(), f"missing model file: {path}"


def test_no_model_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in MODEL_FILES:
        bad = [
            name
            for name in _module_imports(path)
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS)
        ]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_models_do_not_define_routes_or_endpoints() -> None:
    forbidden_substrings = ("APIRouter", "@router.", "@app.", "FastAPI(")
    for path in MODEL_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_models_do_not_call_business_logic_modules_at_import_time() -> None:
    """Catch accidental cross-layer wiring (call-site, not just import)."""
    forbidden_call_targets = (
        "compute_score",
        "build_region_output",
        "build_company_output",
        "build_comparison",
        "personalize",
        "enqueue",
        "run_audit",
    )
    for path in MODEL_FILES:
        text = path.read_text()
        for target in forbidden_call_targets:
            assert f"{target}(" not in text, f"{path.name}: calls {target}()"
