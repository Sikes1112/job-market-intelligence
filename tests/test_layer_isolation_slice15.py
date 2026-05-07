"""Static checks that Slice 15 modules respect layer boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

SLICE_15_FILES = [
    BACKEND / "orchestration" / "events" / "types.py",
    BACKEND / "orchestration" / "events" / "exceptions.py",
    BACKEND / "orchestration" / "events" / "payloads.py",
    BACKEND / "orchestration" / "events" / "router.py",
    BACKEND / "orchestration" / "invalidation" / "types.py",
    BACKEND / "orchestration" / "invalidation" / "rules.py",
    BACKEND / "orchestration" / "invalidation" / "service.py",
    BACKEND / "orchestration" / "scheduler" / "router.py",
    BACKEND / "orchestration" / "scheduler" / "enqueue.py",
]

# Domain services / output builders / personalization / audit / contextual
# / seed-demo / API routes / external clients are off-limits everywhere in
# Slice 15 except the explicit ``QueueService`` integration in scheduler/.
GLOBAL_FORBIDDEN_FRAGMENTS = (
    # Domain services — Slice 15 must not perform writes.
    "backend.companies.service",
    "backend.geography.service",
    "backend.presence.service",
    "backend.hiring.service",
    "backend.entry_level.service",
    "backend.scoring.service",
    "backend.entry_level.scoring",
    "backend.scoring.normalization",
    "backend.outputs.service",
    "backend.outputs.region_output",
    "backend.outputs.company_output",
    # comparison_output is allowed only via duplicate helper, not import
    "backend.outputs.comparison_output",
    "backend.personalization",
    # Later slices.
    "backend.audit",
    "backend.contextual",
    "backend.seeds",
    # API routes.
    "backend.api.routes",
    "backend.api.app",
    "backend.api.dependencies",
    # External brokers / scraping / NLP / chart libs / HTTP clients.
    "celery",
    "redis",
    "kombu",
    "pika",
    "boto3",
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
    "fastapi",
    "uvicorn",
    # Threading / process pools / async event loops — single-threaded only.
    "asyncio",
    "concurrent.futures",
    "multiprocessing",
    "threading",
    # Worker execution loop must not be wired here — Slice 14 owns dispatch.
    "backend.orchestration.workers.runner",
)

# Most Slice 15 files are pure. The enqueue adapter is the *only* one
# allowed to touch QueueService.
QUEUE_FORBIDDEN_FOR = {
    BACKEND / "orchestration" / "events" / "types.py",
    BACKEND / "orchestration" / "events" / "exceptions.py",
    BACKEND / "orchestration" / "events" / "payloads.py",
    BACKEND / "orchestration" / "events" / "router.py",
    BACKEND / "orchestration" / "invalidation" / "types.py",
    BACKEND / "orchestration" / "invalidation" / "rules.py",
    BACKEND / "orchestration" / "invalidation" / "service.py",
    BACKEND / "orchestration" / "scheduler" / "router.py",
}


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


def test_every_slice15_file_exists() -> None:
    for path in SLICE_15_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice15_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_15_FILES:
        bad = [
            name
            for name in _imports(path)
            if any(fragment in name for fragment in GLOBAL_FORBIDDEN_FRAGMENTS)
        ]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_pure_slice15_modules_do_not_touch_queue_service() -> None:
    """Only the enqueue adapter may import QueueService."""
    for path in QUEUE_FORBIDDEN_FOR:
        names = _imports(path)
        for name in names:
            assert "queues.service" not in name, (path.name, name)
            assert "queues.repository" not in name, (path.name, name)


def test_slice15_does_not_invent_new_queue_runtime() -> None:
    forbidden_substrings = (
        "Celery(",
        "@celery.task",
        "Thread(",
        "Process(",
        "ThreadPoolExecutor",
        "ProcessPoolExecutor",
        "asyncio.run",
        "asyncio.create_task",
    )
    for path in SLICE_15_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_slice15_does_not_run_workers() -> None:
    """No code path inside Slice 15 may call .run_one or .run_next.

    The runner is invoked separately by callers; Slice 15 only enqueues.
    """
    for path in SLICE_15_FILES:
        text = path.read_text()
        assert "run_one(" not in text, path.name
        assert "run_next(" not in text, path.name
        assert "WorkerRunner" not in text, path.name


def test_slice15_does_not_mutate_canonical_truth() -> None:
    """Slice 15 must not import canonical-truth repositories (they write rows)."""
    forbidden = (
        "backend.companies.repository",
        "backend.geography.repository",
        "backend.presence.repository",
        "backend.hiring.repository",
        "backend.entry_level.repository",
        "backend.scoring.repository",
        "backend.outputs.repository",
    )
    for path in SLICE_15_FILES:
        text = path.read_text()
        for sub in forbidden:
            assert sub not in text, f"{path.name}: imports {sub}"


def test_invalidation_module_does_not_import_output_metadata_writer() -> None:
    """Slice 15 returns directives only; it must not mark OutputMetadata stale."""
    rules_path = BACKEND / "orchestration" / "invalidation" / "rules.py"
    service_path = BACKEND / "orchestration" / "invalidation" / "service.py"
    for path in (rules_path, service_path):
        text = path.read_text()
        assert "OutputMetadataRepository" not in text
        assert "mark_stale" not in text
        assert "delete" not in text or path.name == ""
