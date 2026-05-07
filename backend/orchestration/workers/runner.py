"""In-process worker runner.

Synchronous, single-threaded, no background loops, no external broker.
The runner holds a registry, a session, and an optional dependency
resolver. Calling code drives execution — typically tests, scripts, or
(in production) an admin-triggered loop.

Lifecycle for a single dispatch:

1. Load the ``Job`` row.
2. Transition status ``queued`` → ``running``.
3. Run dependency check. Missing deps → ``failed`` + ``DEPENDENCY_MISSING``.
4. Look up the handler factory in the registry. Missing → ``failed`` +
   ``INTERNAL_EXCEPTION``.
5. Build the per-request handler from the factory and the runner's
   session, call it with a ``JobRequest`` derived from the row.
6. Apply the ``JobResponse`` to the row (status, error, warnings,
   timestamps, hashes).
7. Return the ``JobResponse`` to the caller.

Retry is a separate explicit operation: ``runner.retry(job_id)`` resets a
failed-with-retryable-error job to ``queued`` (within ``max_retries``).
The caller decides when to actually rerun.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.orchestration.dependencies.checks import (
    DependencyResolver,
    check_dependencies,
)
from backend.orchestration.jobs.envelopes import JobResponse
from backend.orchestration.jobs.errors import ErrorCode, is_retryable
from backend.orchestration.jobs.models import Job
from backend.orchestration.jobs.storage import (
    apply_response_to_job,
    job_to_request,
    make_failure_response,
)
from backend.orchestration.jobs.types import JobStatus, JobType
from backend.orchestration.queues.exceptions import (
    HandlerNotRegistered,
    JobNotFoundInQueue,
    RetryNotEligible,
)
from backend.orchestration.queues.repository import QueueRepository
from backend.orchestration.queues.types import coerce_queue_name
from backend.orchestration.workers.registry import WorkerRegistry


def _utc_now() -> datetime:
    return datetime.now(UTC)


class WorkerRunner:
    def __init__(
        self,
        registry: WorkerRegistry,
        *,
        session: Session,
        dependency_resolver: DependencyResolver | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._registry = registry
        self._session = session
        self._repo = QueueRepository(session)
        self._resolver = dependency_resolver
        self._now = clock or _utc_now

    # --- single-job dispatch --------------------------------------------

    def run_one(self, job_id: str) -> JobResponse:
        job = self._repo.get(job_id)
        if job is None:
            raise JobNotFoundInQueue(job_id)

        started_at = self._now()
        job.status = JobStatus.RUNNING.value
        job.started_at = started_at
        self._repo.flush()

        request = job_to_request(job)

        # Dependency check
        unsatisfied = check_dependencies(
            request.dependency_refs, resolver=self._resolver
        )
        if unsatisfied:
            response = make_failure_response(
                request,
                code=ErrorCode.DEPENDENCY_MISSING,
                message=f"unsatisfied dependency_refs: {unsatisfied!r}",
                started_at=started_at,
                completed_at=self._now(),
            )
            apply_response_to_job(job, response)
            self._repo.flush()
            return response

        # Find handler
        factory = self._registry.get(JobType(job.job_type))
        if factory is None:
            response = make_failure_response(
                request,
                code=ErrorCode.INTERNAL_EXCEPTION,
                message=(
                    f"no handler registered for job_type "
                    f"{job.job_type!r} (Slice 14 default registry)"
                ),
                started_at=started_at,
                completed_at=self._now(),
            )
            apply_response_to_job(job, response)
            self._repo.flush()
            return response

        # Build handler and execute
        try:
            handler = factory(self._session)
            response = handler(request)
        except Exception as exc:
            # Handler raised an unhandled exception — convert to a clean
            # failed response without bubbling, so the queue stays sane.
            response = make_failure_response(
                request,
                code=ErrorCode.INTERNAL_EXCEPTION,
                message=f"handler raised {type(exc).__name__}: {exc!s}",
                started_at=started_at,
                completed_at=self._now(),
            )

        apply_response_to_job(job, response)
        self._repo.flush()
        return response

    # --- queue-driven dispatch ------------------------------------------

    def run_next(self, queue_name) -> JobResponse | None:
        """Run the oldest queued job in ``queue_name``. Returns ``None`` if
        the queue has no queued jobs."""
        queue = coerce_queue_name(queue_name)
        job = self._repo.next_queued(queue.value)
        if job is None:
            return None
        return self.run_one(job.job_id)

    # --- retry ----------------------------------------------------------

    def retry(self, job_id: str) -> Job:
        """Re-queue a failed job if its error is retryable and attempts remain.

        Returns the updated ``Job`` row (still in ``queued`` state). The
        caller decides when to actually re-execute via ``run_one`` /
        ``run_next``. There is no background retry loop.
        """
        job = self._repo.get(job_id)
        if job is None:
            raise JobNotFoundInQueue(job_id)
        if job.status != JobStatus.FAILED.value:
            raise RetryNotEligible(
                f"job {job_id!r} is in status {job.status!r}, not failed"
            )
        if job.error_code is None:
            raise RetryNotEligible(
                f"job {job_id!r} has no error_code recorded"
            )
        if not is_retryable(job.error_code):
            raise RetryNotEligible(
                f"job {job_id!r} error_code {job.error_code!r} is not retryable"
            )
        if job.retry_count >= job.max_retries:
            raise RetryNotEligible(
                f"job {job_id!r} exhausted retries "
                f"({job.retry_count}/{job.max_retries})"
            )

        job.retry_count = job.retry_count + 1
        job.status = JobStatus.QUEUED.value
        job.error_code = None
        job.error_message = None
        job.started_at = None
        job.completed_at = None
        # warnings stay so the operator can audit prior attempts
        self._repo.flush()
        return job


# Convenience: the runner doesn't surface HandlerNotRegistered itself
# (it converts the missing-handler case to a JobResponse failure), but
# tests / callers may want to import it for explicit reference.
__all__ = ["HandlerNotRegistered", "JobNotFoundInQueue", "RetryNotEligible", "WorkerRunner"]
