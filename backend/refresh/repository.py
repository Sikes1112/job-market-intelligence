"""Local/test refresh job repository.

This repository is intentionally in-memory. It supports local tests and process
boundary checks; it is not a production queue, distributed lock, or durable
status store.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime

from backend.refresh.queue import (
    ACTIVE_REFRESH_STATUSES,
    ClaimedRefreshJob,
    RefreshEnqueueResult,
    RefreshJobRequest,
)
from backend.refresh.status import RefreshJobStatus, RefreshJobStatusRecord


class LocalRefreshJobRepository:
    """In-memory queue/status storage for tests and local smoke checks only."""

    def __init__(self) -> None:
        self._requests: OrderedDict[str, RefreshJobRequest] = OrderedDict()
        self._records: OrderedDict[str, RefreshJobStatusRecord] = OrderedDict()

    def enqueue(
        self,
        request: RefreshJobRequest,
        *,
        enqueued_at: datetime,
    ) -> RefreshEnqueueResult:
        existing = self._records.get(request.stable_job_key)
        if existing is not None and existing.status in ACTIVE_REFRESH_STATUSES:
            return RefreshEnqueueResult(
                request=request,
                status_record=existing,
                outcome="already_active",
            )

        record = RefreshJobStatusRecord(
            stable_job_key=request.stable_job_key,
            job_type=request.job_type,
            target_scope=dict(request.target_scope),
            target_id=request.target_id,
            status=RefreshJobStatus.QUEUED,
            enqueued_at=enqueued_at,
            retry_count=request.retry_count,
            source_version_refs=request.source_version_refs,
            source_version_bundle_ref=request.source_version_bundle_ref,
        )
        self._requests[request.stable_job_key] = request
        self._records[request.stable_job_key] = record
        return RefreshEnqueueResult(
            request=request,
            status_record=record,
            outcome="enqueued",
        )

    def get_status(self, stable_job_key: str) -> RefreshJobStatusRecord | None:
        return self._records.get(stable_job_key)

    def all_status_records(self) -> tuple[RefreshJobStatusRecord, ...]:
        return tuple(self._records.values())

    def claim_next(self, *, started_at: datetime) -> ClaimedRefreshJob | None:
        for stable_job_key, record in self._records.items():
            if record.status is RefreshJobStatus.QUEUED:
                request = self._requests[stable_job_key]
                record.status = RefreshJobStatus.RUNNING
                record.started_at = started_at
                return ClaimedRefreshJob(request=request, status_record=record)
        return None

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
        record = self._records[stable_job_key]
        record.status = status
        record.finished_at = finished_at
        record.failure_reason = failure_reason
        if retry_count is not None:
            record.retry_count = retry_count
        if source_version_refs is not None:
            record.source_version_refs = source_version_refs
        if source_version_bundle_ref is not None:
            record.source_version_bundle_ref = source_version_bundle_ref
        if stale_output_count is not None:
            record.stale_output_count = stale_output_count
        if record.started_at is not None:
            record.duration_seconds = (record.finished_at - record.started_at).total_seconds()
        return record


__all__ = ["LocalRefreshJobRepository"]
