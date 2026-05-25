from datetime import UTC, datetime, timedelta

from backend.refresh.adapters import LocalRefreshQueueAdapter
from backend.refresh.handlers import (
    RefreshHandlerDispatcher,
    RefreshHandlerResult,
    default_refresh_dispatcher,
)
from backend.refresh.job_types import REQUIRED_REFRESH_JOB_TYPES, RefreshJobType
from backend.refresh.queue import make_refresh_job_request
from backend.refresh.runner import RefreshWorkerRunner
from backend.refresh.status import RefreshJobStatus


class TickingClock:
    def __init__(self) -> None:
        self._value = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        current = self._value
        self._value = self._value + timedelta(seconds=5)
        return current


def test_every_refresh_job_type_has_dispatch_entry() -> None:
    dispatcher = default_refresh_dispatcher()

    assert dispatcher.registered_types() == REQUIRED_REFRESH_JOB_TYPES


def test_default_dispatch_entries_do_not_fake_successful_refreshes() -> None:
    dispatcher = default_refresh_dispatcher()
    request = make_refresh_job_request(
        RefreshJobType.COMPANY_UNIVERSE_REFRESH,
        target_scope={"scope": "all_markets"},
    )

    result = dispatcher.dispatch(request)

    assert result.status is RefreshJobStatus.FAILED
    assert result.failure_reason == "handler_not_wired_yet:company_universe_refresh"


def test_worker_executes_handler_through_dispatch_layer_and_records_success() -> None:
    clock = TickingClock()
    queue = LocalRefreshQueueAdapter(clock=clock)
    dispatcher = RefreshHandlerDispatcher()
    calls: list[str] = []

    def handler(request):
        calls.append(request.stable_job_key)
        return RefreshHandlerResult(
            status=RefreshJobStatus.SUCCEEDED,
            source_version_refs=("hiring:greater_boston@v1",),
            source_version_bundle_ref="bundle:hiring:greater_boston:v1",
            stale_output_count=2,
        )

    dispatcher.register(RefreshJobType.HIRING_REFRESH, handler)
    request = make_refresh_job_request(
        RefreshJobType.HIRING_REFRESH,
        target_scope={"region_id": "greater_boston"},
    )
    queue.enqueue(request)

    record = RefreshWorkerRunner(queue, dispatcher=dispatcher, clock=clock).run_next()

    assert record is not None
    assert calls == [request.stable_job_key]
    assert record.status is RefreshJobStatus.SUCCEEDED
    assert record.started_at is not None
    assert record.finished_at is not None
    assert record.duration_seconds == 5
    assert record.source_version_refs == ("hiring:greater_boston@v1",)
    assert record.source_version_bundle_ref == "bundle:hiring:greater_boston:v1"
    assert record.stale_output_count == 2


def test_worker_records_failure_reason_and_retry_count() -> None:
    clock = TickingClock()
    queue = LocalRefreshQueueAdapter(clock=clock)
    dispatcher = RefreshHandlerDispatcher()

    def handler(_request):
        raise RuntimeError("source unavailable")

    dispatcher.register(RefreshJobType.ENTRY_LEVEL_REFRESH, handler)
    request = make_refresh_job_request(
        RefreshJobType.ENTRY_LEVEL_REFRESH,
        target_scope={"region_id": "greater_boston"},
        retry_count=2,
    )
    queue.enqueue(request)

    record = RefreshWorkerRunner(queue, dispatcher=dispatcher, clock=clock).run_next()

    assert record is not None
    assert record.status is RefreshJobStatus.FAILED
    assert record.failure_reason == "handler_raised:RuntimeError:source unavailable"
    assert record.retry_count == 2
    assert record.duration_seconds == 5


def test_worker_summary_reports_last_successful_run() -> None:
    clock = TickingClock()
    queue = LocalRefreshQueueAdapter(clock=clock)
    dispatcher = RefreshHandlerDispatcher()
    dispatcher.register(
        RefreshJobType.AUDIT_RUN,
        lambda _request: RefreshHandlerResult(status=RefreshJobStatus.SUCCEEDED),
    )
    request = make_refresh_job_request(RefreshJobType.AUDIT_RUN, target_scope={"scope": "system"})
    queue.enqueue(request)

    record = RefreshWorkerRunner(queue, dispatcher=dispatcher, clock=clock).run_next()
    summary = queue.observability_summary(stale_output_count=4)

    assert record is not None
    assert summary.last_successful_job_key == request.stable_job_key
    assert summary.last_successful_run_at == record.finished_at
    assert summary.stale_output_count == 4
