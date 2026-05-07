"""Queue admission service.

Responsibilities:

* validate the requested queue name (or pick the documented default);
* compute a deterministic ``dedupe_key`` if the caller didn't supply one;
* suppress duplicate non-terminal jobs by ``dedupe_key``;
* persist a fresh ``Job`` row in status ``queued`` ready for the runner.

Dependency resolution is **not** done here — the runner does it at
dispatch time, so a queued job with currently-unsatisfied dependencies
can become satisfied later without a polling loop. Slice 15 will add the
event-driven re-check.
"""

from __future__ import annotations

from typing import Literal, NamedTuple

from backend.orchestration.jobs.dedupe import dedupe_key as compute_dedupe_key
from backend.orchestration.jobs.dedupe import scope_hash
from backend.orchestration.jobs.envelopes import JobRequest
from backend.orchestration.jobs.models import Job
from backend.orchestration.jobs.storage import request_to_job_kwargs
from backend.orchestration.jobs.types import JobType
from backend.orchestration.queues.exceptions import InvalidQueueName
from backend.orchestration.queues.repository import QueueRepository
from backend.orchestration.queues.types import (
    QueueName,
    coerce_queue_name,
    default_queue_for,
)

EnqueueOutcome = Literal["enqueued", "suppressed"]


class EnqueueResult(NamedTuple):
    job: Job
    outcome: EnqueueOutcome


class QueueService:
    def __init__(self, repository: QueueRepository) -> None:
        self._repo = repository

    def enqueue(
        self,
        request: JobRequest,
        *,
        queue_name: QueueName | str | None = None,
        dedupe_key: str | None = None,
        max_retries: int = 3,
    ) -> EnqueueResult:
        # Determine queue.
        if queue_name is None:
            queue = default_queue_for(request.job_type)
        else:
            try:
                queue = coerce_queue_name(queue_name)
            except ValueError as e:
                raise InvalidQueueName(str(e)) from e

        # Compute dedupe key if not supplied. We mirror the documented
        # ``{job_type}::{scope_hash}`` shape from Slice 4.
        if dedupe_key is None:
            dedupe_key = compute_dedupe_key(request.job_type, dict(request.scope))
        scope_hash_value = scope_hash(dict(request.scope))

        # Suppress duplicates: if a non-terminal job exists with the same
        # dedupe_key, return it without enqueuing.
        existing = self._repo.find_active_by_dedupe_key(dedupe_key)
        if existing is not None:
            return EnqueueResult(job=existing, outcome="suppressed")

        kwargs = request_to_job_kwargs(
            request,
            queue_name=queue.value,
            dedupe_key=dedupe_key,
            scope_hash_value=scope_hash_value,
            max_retries=max_retries,
        )
        job = Job(**kwargs)
        self._repo.add(job)
        self._repo.flush()
        return EnqueueResult(job=job, outcome="enqueued")

    def get(self, job_id: str) -> Job | None:
        return self._repo.get(job_id)


# Re-export for convenience.
__all__ = [
    "EnqueueOutcome",
    "EnqueueResult",
    "JobType",
    "QueueService",
    "compute_dedupe_key",
]
