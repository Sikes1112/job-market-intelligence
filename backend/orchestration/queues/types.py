"""Queue vocabulary and default JobType → queue routing.

Source: ``QUEUE_AND_WORKER_MODEL.md`` §20 (MVP four-queue layout).
"""

from __future__ import annotations

from enum import StrEnum

from backend.orchestration.jobs.types import JobType


class QueueName(StrEnum):
    FOUNDATIONAL = "foundational"
    REFRESH = "refresh"
    OUTPUT = "output"
    INTERACTIVE = "interactive"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


# Default queue placement per JobType. Callers may override at enqueue time
# to handle scope-aware routing (e.g. medium-scope presence mapping in
# refresh queue), but the defaults match the documented "natural" home
# from QUEUE_AND_WORKER_MODEL.md §3.
DEFAULT_QUEUE_FOR_JOB_TYPE: dict[JobType, QueueName] = {
    JobType.GEOGRAPHY_BUILD: QueueName.FOUNDATIONAL,
    JobType.COMPANY_UNIVERSE_INTAKE: QueueName.FOUNDATIONAL,
    JobType.ELIGIBILITY_CLASSIFICATION: QueueName.FOUNDATIONAL,
    JobType.PRESENCE_MAPPING: QueueName.FOUNDATIONAL,
    JobType.HIRING_REFRESH: QueueName.REFRESH,
    JobType.ENTRY_LEVEL_REFRESH: QueueName.REFRESH,
    JobType.REGION_SCORE_RECOMPUTE: QueueName.REFRESH,
    JobType.REGION_OUTPUT_BUILD: QueueName.OUTPUT,
    JobType.COMPANY_OUTPUT_BUILD: QueueName.OUTPUT,
    JobType.COMPARISON_CACHE_BUILD: QueueName.OUTPUT,
    JobType.PERSONAL_OVERLAY_QUERY: QueueName.INTERACTIVE,
    JobType.CONTEXTUAL_CHALLENGE_BUILD: QueueName.INTERACTIVE,
    # ``JobType.AUDIT`` intentionally not mapped — Slice 16 will add it.
}


def coerce_queue_name(value: QueueName | str) -> QueueName:
    if isinstance(value, QueueName):
        return value
    if not isinstance(value, str):
        raise ValueError(f"queue name must be str or QueueName, got {type(value).__name__}")
    return QueueName(value)


def default_queue_for(job_type: JobType) -> QueueName:
    if job_type not in DEFAULT_QUEUE_FOR_JOB_TYPE:
        raise ValueError(f"no default queue mapping for job_type {job_type.value!r}")
    return DEFAULT_QUEUE_FOR_JOB_TYPE[job_type]
