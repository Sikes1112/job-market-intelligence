import importlib
import sys
from datetime import UTC, datetime, timedelta

from backend.refresh.adapters import LocalRefreshQueueAdapter
from backend.refresh.job_types import RefreshJobType
from backend.refresh.queue import make_refresh_job_request
from backend.refresh.queue_decision import SELECTED_QUEUE_DECISION, QueueBackend
from backend.refresh.status import RefreshJobStatus


class TickingClock:
    def __init__(self) -> None:
        self._value = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        current = self._value
        self._value = self._value + timedelta(seconds=1)
        return current


def test_web_api_import_does_not_require_redis_or_rq() -> None:
    sys.modules.pop("redis", None)
    sys.modules.pop("rq", None)

    importlib.import_module("backend.api.app")

    assert "redis" not in sys.modules
    assert "rq" not in sys.modules


def test_local_queue_suppresses_duplicate_active_stable_job_key() -> None:
    queue = LocalRefreshQueueAdapter(clock=TickingClock())
    request = make_refresh_job_request(
        RefreshJobType.HIRING_REFRESH,
        target_scope={"region_id": "greater_boston"},
    )

    first = queue.enqueue(request)
    duplicate = queue.enqueue(request)

    assert first.outcome == "enqueued"
    assert duplicate.outcome == "already_active"
    assert duplicate.status_record.stable_job_key == first.status_record.stable_job_key


def test_local_queue_allows_reenqueue_after_terminal_status() -> None:
    queue = LocalRefreshQueueAdapter(clock=TickingClock())
    request = make_refresh_job_request(
        RefreshJobType.PRESENCE_REFRESH,
        target_scope={"company_id": "acme", "region_id": "greater_boston"},
    )
    first = queue.enqueue(request)
    claimed = queue.claim_next(started_at=datetime(2026, 5, 24, 12, 1, tzinfo=UTC))
    assert claimed is not None
    queue.finish(
        request.stable_job_key,
        status=RefreshJobStatus.FAILED,
        finished_at=datetime(2026, 5, 24, 12, 2, tzinfo=UTC),
        failure_reason="handler_not_wired_yet",
    )

    second = queue.enqueue(request)

    assert first.outcome == "enqueued"
    assert second.outcome == "enqueued"


def test_production_queue_decision_remains_rq_redis_and_rejects_kafka() -> None:
    assert SELECTED_QUEUE_DECISION.selected_backend is QueueBackend.RQ_REDIS
    assert SELECTED_QUEUE_DECISION.broker == "redis"
    assert SELECTED_QUEUE_DECISION.external_process_compatible is True
    assert SELECTED_QUEUE_DECISION.rejects_kafka is True


def test_local_queue_is_not_documented_as_production_ready() -> None:
    assert LocalRefreshQueueAdapter.is_production_ready is False
