"""Static checks that Slice 14 queue/worker modules stay layer-clean."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"

SLICE_14_FILES = [
    BACKEND / "orchestration" / "queues" / "types.py",
    BACKEND / "orchestration" / "queues" / "exceptions.py",
    BACKEND / "orchestration" / "queues" / "repository.py",
    BACKEND / "orchestration" / "queues" / "service.py",
    BACKEND / "orchestration" / "dependencies" / "checks.py",
    BACKEND / "orchestration" / "jobs" / "storage.py",
    BACKEND / "orchestration" / "workers" / "registry.py",
    BACKEND / "orchestration" / "workers" / "runner.py",
]

FORBIDDEN_FRAGMENTS = (
    # Slice 15 belongs to events / invalidation routing — Slice 14 must
    # not pre-build that machinery.
    "backend.orchestration.events.router",
    "backend.orchestration.events.invalidation",
    "backend.orchestration.invalidation",
    # Audit / contextual challenge / seed-demo
    "backend.audit",
    # API routes
    "backend.api",
    # External brokers / scraping / NLP / chart libs / HTTP clients
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
    # Threading / process pools / async event loops — single-threaded only
    "asyncio",
    "concurrent.futures",
    "multiprocessing",
    "threading",
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


def test_every_slice14_file_exists() -> None:
    for path in SLICE_14_FILES:
        assert path.exists(), f"missing: {path}"


def test_no_slice14_module_imports_a_forbidden_layer() -> None:
    violations: dict[str, list[str]] = {}
    for path in SLICE_14_FILES:
        bad = [
            name
            for name in _imports(path)
            if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS)
        ]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad
    assert not violations, violations


def test_no_slice14_module_imports_event_router_runtime() -> None:
    """The event router lives in backend/orchestration/events/. Slice 4
    contracts there (envelopes, errors, types, recommendations) are
    allowed; the router/invalidation runtime modules aren't."""
    forbidden_substrings = (
        "from backend.orchestration.events.router",
        "from backend.orchestration.events.invalidation",
        "from backend.orchestration.invalidation",
        "from backend.audit",
        "from backend.api",
    )
    for path in SLICE_14_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_no_slice14_module_uses_external_broker_or_daemon() -> None:
    """Defense in depth — text-level checks for accidental Celery/threading
    introduction."""
    forbidden_substrings = (
        "Celery(",
        "@celery.task",
        ".enqueue(",
        ".delay(",
        "Thread(",
        "Process(",
        "ThreadPoolExecutor",
        "ProcessPoolExecutor",
        "asyncio.run",
        "asyncio.create_task",
    )
    for path in SLICE_14_FILES:
        text = path.read_text()
        for sub in forbidden_substrings:
            assert sub not in text, f"{path.name}: contains {sub!r}"


def test_runtime_does_not_secretly_call_personalization() -> None:
    """Personalization is interactive (Slice 13). The Slice 14 runtime
    must not import personalization scoring or service."""
    for path in SLICE_14_FILES:
        text = path.read_text()
        assert "from backend.personalization" not in text


def test_storage_bridge_lives_in_orchestration_jobs() -> None:
    """The bridge is the documented seam between Slice 4 envelopes and
    Slice 2 ORM. Pin its location."""
    bridge = BACKEND / "orchestration" / "jobs" / "storage.py"
    assert bridge.exists()
    text = bridge.read_text()
    assert "request_to_job_kwargs" in text
    assert "job_to_request" in text
    assert "apply_response_to_job" in text
