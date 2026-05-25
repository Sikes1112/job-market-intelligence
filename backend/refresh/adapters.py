"""Refresh queue adapters.

``LocalRefreshQueueAdapter`` is local/test only. ``RQRedisRefreshQueueAdapter``
keeps the Batch 1 production posture explicit while importing Redis/RQ lazily,
so API startup and normal tests do not require broker packages or a live Redis
server.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from backend.refresh.queue import (
    ClaimedRefreshJob,
    RefreshEnqueueResult,
    RefreshJobRequest,
)
from backend.refresh.repository import LocalRefreshJobRepository
from backend.refresh.status import (
    RefreshJobStatus,
    RefreshJobStatusRecord,
    RefreshObservabilitySummary,
    summarize_refresh_observability,
)


class RefreshQueueConfigurationError(RuntimeError):
    """Raised when a configured production queue adapter cannot be created."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


class LocalRefreshQueueAdapter:
    """In-memory adapter for tests and local smoke checks only."""

    is_production_ready = False

    def __init__(
        self,
        repository: LocalRefreshJobRepository | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo = repository or LocalRefreshJobRepository()
        self._clock = clock or _utc_now

    def enqueue(self, request: RefreshJobRequest) -> RefreshEnqueueResult:
        return self._repo.enqueue(request, enqueued_at=self._clock())

    def get_status(self, stable_job_key: str) -> RefreshJobStatusRecord | None:
        return self._repo.get_status(stable_job_key)

    def claim_next(self, *, started_at: datetime) -> ClaimedRefreshJob | None:
        return self._repo.claim_next(started_at=started_at)

    def finish(
        self,
        stable_job_key: str,
        *,
        status: RefreshJobStatus,
        finished_at: datetime,
        failure_reason: str | None = None,
        retry_count: int | None = None,
        source_version_refs: tuple[str, ...] | None = None,
        source_version_bundle_ref: str | None = None,
        stale_output_count: int | None = None,
    ) -> RefreshJobStatusRecord:
        return self._repo.finish(
            stable_job_key,
            status=status,
            finished_at=finished_at,
            failure_reason=failure_reason,
            retry_count=retry_count,
            source_version_refs=source_version_refs,
            source_version_bundle_ref=source_version_bundle_ref,
            stale_output_count=stale_output_count,
        )

    def all_status_records(self) -> tuple[RefreshJobStatusRecord, ...]:
        return self._repo.all_status_records()

    def observability_summary(
        self,
        *,
        stale_output_count: int = 0,
    ) -> RefreshObservabilitySummary:
        return summarize_refresh_observability(
            self.all_status_records(),
            stale_output_count=stale_output_count,
        )


class RQRedisRefreshQueueAdapter:
    """Production adapter boundary for RQ + Redis.

    The dependency is intentionally optional in this batch. Constructing this
    adapter imports ``redis`` and ``rq`` lazily and raises a configuration error
    if the packages are not installed.
    """

    is_production_ready = True

    def __init__(
        self,
        *,
        redis_url: str,
        queue_name: str = "refresh",
        enqueue_function: str = "backend.refresh.runner.execute_refresh_job_payload",
    ) -> None:
        try:
            from redis import Redis
            from rq import Queue
        except ImportError as exc:
            raise RefreshQueueConfigurationError(
                "RQ/Redis refresh runtime requires the optional production "
                "packages 'rq' and 'redis'. They are intentionally not required "
                "for API startup or normal tests in this batch."
            ) from exc

        self._redis = Redis.from_url(redis_url)
        self._queue = Queue(queue_name, connection=self._redis)
        self._enqueue_function = enqueue_function

    def enqueue(self, request: RefreshJobRequest) -> RefreshEnqueueResult:
        payload = request.model_dump(mode="json")
        rq_job = self._queue.enqueue(
            self._enqueue_function,
            payload,
            job_id=request.stable_job_key,
        )
        enqueued_at = rq_job.enqueued_at or datetime.now(UTC)
        record = RefreshJobStatusRecord(
            stable_job_key=request.stable_job_key,
            job_id=rq_job.id,
            job_type=request.job_type,
            target_scope=dict(request.target_scope),
            target_id=request.target_id,
            status=RefreshJobStatus.QUEUED,
            enqueued_at=enqueued_at,
            retry_count=request.retry_count,
            source_version_refs=request.source_version_refs,
            source_version_bundle_ref=request.source_version_bundle_ref,
        )
        return RefreshEnqueueResult(
            request=request,
            status_record=record,
            outcome="enqueued",
        )

    def get_status(self, stable_job_key: str) -> RefreshJobStatusRecord | None:
        return None

    def claim_next(self, *, started_at: datetime) -> ClaimedRefreshJob | None:
        raise NotImplementedError("RQ workers claim jobs through rq.Worker, not this adapter")

    def finish(
        self,
        stable_job_key: str,
        *,
        status: RefreshJobStatus,
        finished_at: datetime,
        failure_reason: str | None = None,
        retry_count: int | None = None,
        source_version_refs: tuple[str, ...] | None = None,
        source_version_bundle_ref: str | None = None,
        stale_output_count: int | None = None,
    ) -> RefreshJobStatusRecord:
        raise NotImplementedError("RQ job completion is recorded by the worker execution payload")


def create_refresh_queue_adapter(
    *,
    adapter: str,
    redis_url: str | None = None,
    queue_name: str = "refresh",
    clock: Callable[[], datetime] | None = None,
) -> LocalRefreshQueueAdapter | RQRedisRefreshQueueAdapter:
    if adapter == "local":
        return LocalRefreshQueueAdapter(clock=clock)
    if adapter == "rq":
        if not redis_url:
            raise RefreshQueueConfigurationError("redis_url is required for the RQ adapter")
        return RQRedisRefreshQueueAdapter(redis_url=redis_url, queue_name=queue_name)
    raise RefreshQueueConfigurationError(f"unknown refresh queue adapter: {adapter!r}")


def run_rq_worker(*, redis_url: str, queue_names: list[str]) -> None:
    """Start an RQ worker process. Imports broker packages only when called."""

    try:
        from redis import Redis
        from rq import Queue, Worker
    except ImportError as exc:
        raise RefreshQueueConfigurationError(
            "Running the production refresh worker requires 'rq' and 'redis'."
        ) from exc

    connection = Redis.from_url(redis_url)
    queues: list[Any] = [Queue(name, connection=connection) for name in queue_names]
    Worker(queues, connection=connection).work()


__all__ = [
    "LocalRefreshQueueAdapter",
    "RQRedisRefreshQueueAdapter",
    "RefreshQueueConfigurationError",
    "create_refresh_queue_adapter",
    "run_rq_worker",
]
