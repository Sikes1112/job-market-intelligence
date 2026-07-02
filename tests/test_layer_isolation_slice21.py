"""Static checks that Layer 21A predictive modules stay layer-clean."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

LAYER_21A_FILES = [
    BACKEND / "predictive" / "__init__.py",
    BACKEND / "predictive" / "contracts.py",
    BACKEND / "predictive" / "confidence.py",
    BACKEND / "predictive" / "reports.py",
    BACKEND / "predictive" / "signals.py",
    BACKEND / "predictive" / "service.py",
]

FORBIDDEN_FRAGMENTS = (
    "backend.api",
    "backend.companies",
    "backend.geography",
    "backend.hiring",
    "backend.presence",
    "backend.entry_level",
    "backend.scoring",
    "backend.outputs",
    "backend.recommendations",
    "backend.public_reports",
    "backend.public_benchmarks",
    "backend.institutions",
    "backend.platform_intelligence.models",
    "backend.platform_intelligence.history_repository",
    "backend.platform_intelligence.reports",
    "backend.platform_intelligence.predictive_signals",
    "backend.platform.public_api_service",
    "backend.ingestion",
    "backend.refresh",
    "backend.orchestration",
    "fastapi",
    "uvicorn",
    "requests",
    "httpx",
    "aiohttp",
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


def test_every_layer21a_file_exists() -> None:
    for path in LAYER_21A_FILES:
        assert path.exists(), f"missing: {path}"


def test_layer21a_does_not_import_domain_owned_internals_or_route_layers() -> None:
    violations: dict[str, list[str]] = {}
    for path in LAYER_21A_FILES:
        bad = [
            name
            for name in _imports(path)
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS)
        ]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_layer21a_defines_no_routes_workers_or_external_fetching() -> None:
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
        "requests.",
        "httpx.",
    )
    for path in LAYER_21A_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_layer21a_payloads_do_not_define_raw_source_or_private_fields() -> None:
    text = (BACKEND / "predictive" / "contracts.py").read_text()
    forbidden_field_names = (
        "source_id:",
        "source_ids:",
        "raw_source_refs:",
        "raw_scrape_records:",
        "admin_metadata:",
        "private_metadata:",
        "internal_formula_weights:",
    )
    for field_name in forbidden_field_names:
        assert field_name not in text
