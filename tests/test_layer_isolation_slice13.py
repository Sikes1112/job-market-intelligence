"""Static checks that Slice 13 personalization modules stay layer-clean."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

SLICE_13_FILES = [
    BACKEND / "personalization" / "types.py",
    BACKEND / "personalization" / "exceptions.py",
    BACKEND / "personalization" / "payloads.py",
    BACKEND / "personalization" / "scoring.py",
    BACKEND / "personalization" / "service.py",
    BACKEND / "api" / "personalized.py",
]

FORBIDDEN_FRAGMENTS = (
    # Audit / contextual challenge — deferred slices
    "backend.audit",
    # Upstream domain SERVICES are forbidden — Slice 13 reads through
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
    "backend.entry_level.scoring",   # Slice 9 formula, must not leak in
    "backend.scoring.service",        # Slice 10 formula, must not leak in
    "backend.scoring.normalization",
    "backend.scoring.rulesets",
    # Worker / queue runtime
    "backend.orchestration.queues",
    "backend.orchestration.workers",
    "backend.orchestration.scheduler",
    "backend.orchestration.invalidation",
    "backend.orchestration.state_machine",
    "backend.orchestration.events",
    # External execution / scraping / NLP / ML / chart libs
    "celery",
    "redis",
    "kombu",
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


def test_every_slice13_file_exists() -> None:
    for path in SLICE_13_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice13_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_13_FILES:
        bad = [
            name
            for name in _imports(path)
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS)
        ]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_personalization_modules_define_no_routes_in_business_layer() -> None:
    """The personalization business layer must not declare web routes —
    those live in backend/api/personalized.py only."""
    business_files = [
        BACKEND / "personalization" / "types.py",
        BACKEND / "personalization" / "exceptions.py",
        BACKEND / "personalization" / "payloads.py",
        BACKEND / "personalization" / "scoring.py",
        BACKEND / "personalization" / "service.py",
    ]
    for path in business_files:
        text = path.read_text()
        for sub in ("APIRouter", "@router.", "@app.", "FastAPI("):
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_scoring_is_pure_python() -> None:
    """The personalization scoring module must not import the SQLAlchemy
    stack or any business layer — it's pure scalar math."""
    text = (BACKEND / "personalization" / "scoring.py").read_text()
    assert "from backend" not in text or "from backend.personalization" in text
    # specifically forbid SQLAlchemy and any non-personalization backend import
    assert "import sqlalchemy" not in text
    assert "from sqlalchemy" not in text
    forbidden_backend_imports = (
        "from backend.companies",
        "from backend.geography",
        "from backend.presence",
        "from backend.hiring",
        "from backend.entry_level",
        "from backend.scoring",
        "from backend.outputs",
        "from backend.api",
    )
    for f in forbidden_backend_imports:
        assert f not in text, f"scoring.py imports {f!r}"


def test_service_does_not_import_upstream_services() -> None:
    text = (BACKEND / "personalization" / "service.py").read_text()
    forbidden = (
        "from backend.companies.service",
        "from backend.geography.service",
        "from backend.presence.service",
        "from backend.hiring.service",
        "from backend.entry_level.service",
        "from backend.entry_level.scoring",
        "from backend.scoring.service",
        "from backend.scoring.normalization",
        "from backend.scoring.rulesets",
    )
    for f in forbidden:
        assert f not in text, f"personalization service imports {f!r}"


def test_personalization_does_not_emit_personalized_output_metadata() -> None:
    """The service must not write OutputMetadata rows. We check by ensuring
    service.py does not import OutputMetadataRepository or the Slice 11
    OutputAssemblyService."""
    text = (BACKEND / "personalization" / "service.py").read_text()
    assert "OutputMetadataRepository" not in text
    assert "OutputAssemblyService" not in text
