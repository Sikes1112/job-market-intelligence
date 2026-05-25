"""Refresh worker runner.

The worker process owns execution. Web/API routes should enqueue or read only;
the scheduler process may enqueue planned work; only this runner dispatches
refresh handlers.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from backend.refresh.adapters import LocalRefreshQueueAdapter
from backend.refresh.handlers import (
    RefreshHandlerDispatcher,
    RefreshHandlerResult,
    default_refresh_dispatcher,
)
from backend.refresh.queue import RefreshJobRequest, RefreshQueueAdapter
from backend.refresh.status import RefreshJobStatus, RefreshJobStatusRecord


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RefreshWorkerRunner:
    def __init__(
        self,
        queue: RefreshQueueAdapter,
        *,
        dispatcher: RefreshHandlerDispatcher | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._queue = queue
        self._dispatcher = dispatcher or default_refresh_dispatcher()
        self._clock = clock or _utc_now

    def run_next(self) -> RefreshJobStatusRecord | None:
        started_at = self._clock()
        claimed = self._queue.claim_next(started_at=started_at)
        if claimed is None:
            return None

        request = claimed.request
        try:
            result = self._dispatcher.dispatch(request)
        except Exception as exc:
            result = RefreshHandlerResult(
                status=RefreshJobStatus.FAILED,
                failure_reason=f"handler_raised:{type(exc).__name__}:{exc!s}",
                source_version_refs=request.source_version_refs,
                source_version_bundle_ref=request.source_version_bundle_ref,
            )

        if result.status is RefreshJobStatus.FAILED and not result.failure_reason:
            result = RefreshHandlerResult(
                status=RefreshJobStatus.FAILED,
                failure_reason="handler_failed_without_reason",
                source_version_refs=result.source_version_refs,
                source_version_bundle_ref=result.source_version_bundle_ref,
                stale_output_count=result.stale_output_count,
            )

        finished_at = self._clock()
        return self._queue.finish(
            request.stable_job_key,
            status=result.status,
            finished_at=finished_at,
            failure_reason=result.failure_reason,
            retry_count=request.retry_count,
            source_version_refs=result.source_version_refs or request.source_version_refs,
            source_version_bundle_ref=(
                result.source_version_bundle_ref or request.source_version_bundle_ref
            ),
            stale_output_count=result.stale_output_count,
        )

    def run_until_empty(self, *, max_jobs: int | None = None) -> tuple[RefreshJobStatusRecord, ...]:
        records: list[RefreshJobStatusRecord] = []
        while max_jobs is None or len(records) < max_jobs:
            record = self.run_next()
            if record is None:
                break
            records.append(record)
        return tuple(records)


def execute_refresh_job_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """RQ worker target.

    RQ executes one payload at a time in a worker process. This function uses a
    single-job local adapter to apply the same lifecycle and dispatcher behavior
    used by tests. Durable production status storage remains a later batch.
    """

    request = RefreshJobRequest.model_validate(payload)
    queue = LocalRefreshQueueAdapter()
    queue.enqueue(request)
    record = RefreshWorkerRunner(queue).run_next()
    if record is None:
        raise RuntimeError("refresh worker could not claim the enqueued payload")
    return record.model_dump(mode="json")


__all__ = [
    "RefreshWorkerRunner",
    "execute_refresh_job_payload",
]
