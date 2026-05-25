import ast
from datetime import UTC, datetime
from pathlib import Path

from backend.refresh.adapters import LocalRefreshQueueAdapter
from backend.refresh.cadence import CADENCE_BY_JOB_TYPE, TriggerPosture
from backend.refresh.job_types import RefreshJobType
from backend.refresh.scheduler import (
    SCHEDULED_TRIGGER_POSTURES,
    RefreshSchedulerPlanner,
    RefreshSchedulerRunner,
)
from backend.refresh.status import RefreshJobStatus

REPO_ROOT = Path(__file__).resolve().parent.parent
API_FILES = [
    REPO_ROOT / "backend" / "api" / "app.py",
    REPO_ROOT / "backend" / "api" / "routes.py",
    REPO_ROOT / "backend" / "api" / "personalized.py",
    REPO_ROOT / "backend" / "api" / "user.py",
]


def test_scheduler_enqueues_planned_jobs_without_executing_handlers() -> None:
    queue = LocalRefreshQueueAdapter()
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)

    result = RefreshSchedulerRunner(queue).enqueue_due(now=now)

    assert result.plan.requests
    assert all(item.outcome == "enqueued" for item in result.enqueue_results)
    for request in result.plan.requests:
        record = queue.get_status(request.stable_job_key)
        assert record is not None
        assert record.status is RefreshJobStatus.QUEUED
        assert record.started_at is None
        assert record.finished_at is None


def test_scheduler_duplicate_runs_report_already_active() -> None:
    queue = LocalRefreshQueueAdapter()
    runner = RefreshSchedulerRunner(queue)
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)

    first = runner.enqueue_due(now=now)
    second = runner.enqueue_due(now=now)

    assert first.enqueue_results
    assert all(item.outcome == "enqueued" for item in first.enqueue_results)
    assert all(item.outcome == "already_active" for item in second.enqueue_results)


def test_every_scheduled_cadence_job_maps_to_known_job_type() -> None:
    plan = RefreshSchedulerPlanner().plan(now=datetime(2026, 5, 24, 12, 0, tzinfo=UTC))
    scheduled_policy_types = {
        job_type
        for job_type, policy in CADENCE_BY_JOB_TYPE.items()
        if policy.trigger_posture in SCHEDULED_TRIGGER_POSTURES
    }

    assert {request.job_type for request in plan.requests} == scheduled_policy_types
    assert all(isinstance(request.job_type, RefreshJobType) for request in plan.requests)


def test_event_driven_only_cadences_are_not_scheduled_by_cadence_runner() -> None:
    plan = RefreshSchedulerPlanner().plan(now=datetime(2026, 5, 24, 12, 0, tzinfo=UTC))
    planned_types = {request.job_type for request in plan.requests}
    event_driven_only = {
        job_type
        for job_type, policy in CADENCE_BY_JOB_TYPE.items()
        if policy.trigger_posture is TriggerPosture.EVENT_DRIVEN
    }

    assert event_driven_only
    assert planned_types.isdisjoint(event_driven_only)


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


def test_api_routes_do_not_import_or_execute_refresh_runtime() -> None:
    forbidden_imports = (
        "backend.refresh.runner",
        "backend.refresh.handlers",
        "backend.refresh.scheduler",
        "backend.refresh.adapters",
    )
    forbidden_text = (
        "RefreshWorkerRunner",
        "execute_refresh_job_payload",
        ".run_next(",
        ".run_until_empty(",
    )

    for path in API_FILES:
        imports = _imports(path)
        assert not [
            name for name in imports if any(fragment in name for fragment in forbidden_imports)
        ]
        text = path.read_text()
        for fragment in forbidden_text:
            assert fragment not in text
