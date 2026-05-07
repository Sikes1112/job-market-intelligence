"""Static checks that Slice 11 output-assembly modules stay layer-clean."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

SLICE_11_FILES = [
    BACKEND / "outputs" / "types.py",
    BACKEND / "outputs" / "exceptions.py",
    BACKEND / "outputs" / "hashing.py",
    BACKEND / "outputs" / "metadata.py",
    BACKEND / "outputs" / "payloads.py",
    BACKEND / "outputs" / "repository.py",
    BACKEND / "outputs" / "region_output.py",
    BACKEND / "outputs" / "company_output.py",
    BACKEND / "outputs" / "comparison_output.py",
    BACKEND / "outputs" / "service.py",
    BACKEND / "orchestration" / "jobs" / "region_output_build.py",
    BACKEND / "orchestration" / "jobs" / "company_output_build.py",
    BACKEND / "orchestration" / "jobs" / "comparison_cache_build.py",
]

FORBIDDEN_FRAGMENTS = (
    # Downstream slices
    "backend.personalization",
    "backend.audit",
    # Upstream domain SERVICES are forbidden — Slice 11 reads through
    # repositories only.
    "backend.companies.service",
    "backend.companies.classification",
    "backend.companies.overrides",
    "backend.geography.service",
    "backend.presence.service",
    "backend.presence.evidence",
    "backend.hiring.service",
    "backend.hiring.role_families",
    "backend.entry_level.service",
    "backend.entry_level.scoring",   # Slice 9 formula must not leak in
    "backend.scoring.service",       # Slice 10 formula must not leak in
    "backend.scoring.normalization",
    "backend.scoring.rulesets",
    # API + queue/worker runtime
    "backend.api",
    "backend.orchestration.queues",
    "backend.orchestration.workers",
    "backend.orchestration.scheduler",
    "backend.orchestration.invalidation",
    "backend.orchestration.state_machine",
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
    "backend.orchestration.jobs.region_output_build",
    "backend.orchestration.jobs.company_output_build",
    "backend.orchestration.jobs.comparison_cache_build",
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


def test_every_slice11_file_exists() -> None:
    for path in SLICE_11_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice11_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_11_FILES:
        bad = []
        for name in _imports(path):
            if any(allowed in name for allowed in ALLOWED_ORCH_FRAGMENTS):
                continue
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS):
                bad.append(name)
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_output_modules_define_no_routes_or_workers() -> None:
    forbidden_substrings = (
        "APIRouter",
        "@router.",
        "@app.",
        "FastAPI(",
        "Celery(",
        ".enqueue(",
        ".delay(",
    )
    for path in SLICE_11_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_hashing_is_pure_python() -> None:
    """Hashing must not import the SQLAlchemy stack or any business layer."""
    text = (BACKEND / "outputs" / "hashing.py").read_text()
    assert "from backend" not in text
    assert "import sqlalchemy" not in text


def test_payloads_module_only_imports_pydantic_and_warning_schema() -> None:
    """Payload models stay pure Pydantic; the only cross-layer import is
    JobWarning (Slice 4) for the warning vocabulary."""
    text = (BACKEND / "outputs" / "payloads.py").read_text()
    forbidden = (
        "backend.scoring",
        "backend.entry_level",
        "backend.hiring",
        "backend.presence",
        "backend.companies",
        "backend.geography",
        "sqlalchemy",
    )
    for f in forbidden:
        assert f not in text, f"payloads.py imports {f!r}"


def test_service_does_not_import_scoring_or_entry_level_formulas() -> None:
    text = (BACKEND / "outputs" / "service.py").read_text()
    assert "backend.scoring.service" not in text
    assert "backend.entry_level.scoring" not in text
    assert "backend.scoring.normalization" not in text
    assert "backend.scoring.rulesets" not in text


def test_builders_do_not_import_upstream_services() -> None:
    for builder in ("region_output.py", "company_output.py", "comparison_output.py"):
        text = (BACKEND / "outputs" / builder).read_text()
        for upstream_service in (
            "from backend.companies.service",
            "from backend.geography.service",
            "from backend.presence.service",
            "from backend.hiring.service",
            "from backend.entry_level.service",
            "from backend.scoring.service",
        ):
            assert upstream_service not in text, f"{builder}: imports {upstream_service}"
