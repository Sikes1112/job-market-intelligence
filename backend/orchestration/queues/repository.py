"""Thin data-access layer for the Job table from the queue/runtime perspective.

Slice 14 is the only slice that writes execution-state fields on the Job
row. All upstream truth still goes through the existing per-domain
repositories.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, SessionTransaction

from backend.orchestration.jobs.models import Job
from backend.orchestration.jobs.types import JobStatus

# Statuses that are *active* in the queue sense — a duplicate-dedupe job
# should not be enqueued while one of these exists.
NON_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {JobStatus.QUEUED.value, JobStatus.RUNNING.value}
)


class QueueRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, job_id: str) -> Job | None:
        return self._session.get(Job, job_id)

    def exists(self, job_id: str) -> bool:
        return self.get(job_id) is not None

    def find_active_by_dedupe_key(self, dedupe_key: str) -> Job | None:
        """Return the existing non-terminal job with this dedupe key, if any."""
        stmt = (
            select(Job)
            .where(
                Job.dedupe_key == dedupe_key,
                Job.status.in_(list(NON_TERMINAL_STATUSES)),
            )
            .order_by(Job.created_at)
        )
        return self._session.execute(stmt).scalars().first()

    def next_queued(self, queue_name: str) -> Job | None:
        """Return the oldest queued job for ``queue_name``."""
        stmt = (
            select(Job)
            .where(
                Job.queue_name == queue_name,
                Job.status == JobStatus.QUEUED.value,
            )
            .order_by(Job.created_at)
        )
        return self._session.execute(stmt).scalars().first()

    def list_by_queue(
        self, queue_name: str, *, status: str | None = None
    ) -> list[Job]:
        stmt = select(Job).where(Job.queue_name == queue_name)
        if status is not None:
            stmt = stmt.where(Job.status == status)
        stmt = stmt.order_by(Job.created_at)
        return list(self._session.execute(stmt).scalars())

    def add(self, job: Job) -> None:
        self._session.add(job)

    def flush(self) -> None:
        self._session.flush()

    def begin_nested(self) -> SessionTransaction:
        return self._session.begin_nested()

    def rollback(self) -> None:
        self._session.rollback()
