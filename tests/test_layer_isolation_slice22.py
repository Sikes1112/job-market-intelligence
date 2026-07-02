"""Static checks that Layer 22A institutional decision infrastructure stays bounded."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

LAYER_22_FILES = [
    BACKEND / "institutions" / "privacy.py",
    BACKEND / "institutions" / "decision_infrastructure.py",
]

FORBIDDEN_IMPORT_FRAGMENTS = (
    "backend.users",
    "backend.recommendations",
    "backend.public_reports",
    "backend.public_benchmarks",
    "backend.ingestion",
    "backend.refresh",
    "backend.orchestration",
    "backend.scraping",
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


def test_layer22_files_exist() -> None:
    for path in LAYER_22_FILES:
        assert path.exists(), f"missing: {path}"


def test_layer22_does_not_import_private_student_or_external_fetching_layers() -> None:
    violations: dict[str, list[str]] = {}
    for path in LAYER_22_FILES:
        bad = [
            name
            for name in _imports(path)
            if any(fragment in name for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
        ]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_layer22_decision_builder_defines_no_routes_or_persistence() -> None:
    forbidden_substrings = (
        "APIRouter",
        "@router.",
        "@app.",
        "FastAPI(",
        "session.add(",
        "self._repo.add_",
        "self._repo.flush(",
        "InstitutionalReport(",
        "SavedMarketArtifact",
        "UserPreferenceProfile",
    )
    for path in LAYER_22_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_layer22_payloads_do_not_define_individual_student_fields() -> None:
    text = (BACKEND / "institutions" / "decision_infrastructure.py").read_text()
    forbidden_field_names = (
        "student_user_id:",
        "user_id:",
        "saved_artifact_id:",
        "recommendation_snapshot_id:",
        "application_id:",
        "search_history:",
        "raw_student_records:",
        "private_activity:",
        "preferences:",
    )
    for field_name in forbidden_field_names:
        assert field_name not in text
