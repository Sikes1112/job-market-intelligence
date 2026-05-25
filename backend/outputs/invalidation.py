"""Output cache invalidation and rebuild enqueue helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from backend.outputs.cache_repository import OutputCacheRepository
from backend.outputs.models import OutputMetadata
from backend.outputs.types import OutputType
from backend.refresh.job_types import RefreshJobType
from backend.refresh.queue import (
    RefreshEnqueueResult,
    RefreshQueueAdapter,
    make_refresh_job_request,
)


@dataclass(frozen=True)
class OutputInvalidationResult:
    stale_output_ids: tuple[str, ...]
    enqueue_results: tuple[RefreshEnqueueResult, ...]


class OutputCacheInvalidationService:
    def __init__(self, cache_repo: OutputCacheRepository, queue: RefreshQueueAdapter) -> None:
        self._cache = cache_repo
        self._queue = queue

    def mark_output_stale(
        self,
        output_id: str,
        *,
        reason: str,
        now: datetime | None = None,
        enqueue_rebuild: bool = True,
    ) -> OutputInvalidationResult:
        row = self._cache.get(output_id)
        if row is None:
            return OutputInvalidationResult(stale_output_ids=(), enqueue_results=())
        return self._mark_rows_stale(
            [row],
            reason=reason,
            now=now,
            enqueue_rebuild=enqueue_rebuild,
        )

    def mark_scope_stale(
        self,
        *,
        output_type: OutputType,
        subject_id: str,
        reason: str,
        now: datetime | None = None,
        enqueue_rebuild: bool = True,
    ) -> OutputInvalidationResult:
        row = self._cache.get_by_type_and_subject(output_type, subject_id)
        rows = [row] if row is not None else []
        return self._mark_rows_stale(
            rows,
            reason=reason,
            now=now,
            enqueue_rebuild=enqueue_rebuild,
        )

    def _mark_rows_stale(
        self,
        rows: list[OutputMetadata],
        *,
        reason: str,
        now: datetime | None,
        enqueue_rebuild: bool,
    ) -> OutputInvalidationResult:
        invalidated_at = now or datetime.now(UTC)
        stale_ids: list[str] = []
        enqueue_results: list[RefreshEnqueueResult] = []
        for row in rows:
            if row.state not in {"fresh", "stale"}:
                continue
            request = make_refresh_job_request(
                RefreshJobType.OUTPUT_REBUILD,
                target_scope={
                    "output_id": row.output_id,
                    "output_type": row.output_type,
                    "subject_id": row.subject_id,
                },
                target_id=row.output_id,
                requested_by="invalidation",
                source_version_refs=tuple(row.source_version_refs or ()),
                source_version_bundle_ref=row.source_bundle_ref,
            )
            self._cache.mark_stale(
                row,
                reason=reason,
                invalidated_at=invalidated_at,
                rebuild_job_key=request.stable_job_key,
            )
            stale_ids.append(row.output_id)
            if enqueue_rebuild:
                enqueue_results.append(self._queue.enqueue(request))
        return OutputInvalidationResult(
            stale_output_ids=tuple(stale_ids),
            enqueue_results=tuple(enqueue_results),
        )


__all__ = ["OutputCacheInvalidationService", "OutputInvalidationResult"]
