"""Scheduler-side wrapper around the event router.

The event router (:mod:`backend.orchestration.events.router`) is pure —
its output is a :class:`RouteResult` describing recommendations and
invalidations. The scheduler layer is the place where those recommendations
turn into real :class:`JobRequest` objects.

Slice 15 keeps this file very narrow: it builds :class:`JobRequest` envelopes
from :class:`DownstreamTriggerRecommendation` values, but does **not**
enqueue them. Enqueueing is :mod:`backend.orchestration.scheduler.enqueue`.
Splitting the two keeps the recommendation→envelope translation testable
without a database session.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime

from backend.orchestration.events.payloads import Event
from backend.orchestration.events.recommendations import (
    DownstreamTriggerRecommendation,
)
from backend.orchestration.jobs.envelopes import JobRequest
from backend.orchestration.jobs.types import JobType, Priority, TriggerType


def _stable_job_id(event: Event, recommendation: DownstreamTriggerRecommendation) -> str:
    """Derive a deterministic job_id for ``(event, recommendation)``.

    Same event id + job type + scope → same job id. Combined with the
    QueueService dedupe rule (``{job_type}::{scope_hash}``) this keeps
    repeated routing of the same event idempotent at both the envelope and
    queue layers.
    """
    import json

    canonical_scope = json.dumps(
        recommendation.scope,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(
        f"{event.event_id}::{recommendation.job_type.value}::{canonical_scope}".encode()
    ).hexdigest()
    return f"job_{recommendation.job_type.value}_{digest[:16]}"


def build_job_request(
    event: Event,
    recommendation: DownstreamTriggerRecommendation,
) -> JobRequest:
    """Translate a recommendation into a :class:`JobRequest` envelope.

    MVP event recommendations do not carry version-aware dependency refs. The
    dependency list is left empty until a post-MVP dependency graph can resolve
    concrete source-version references.
    """
    return JobRequest(
        job_id=_stable_job_id(event, recommendation),
        job_type=JobType(recommendation.job_type),
        trigger_type=TriggerType.EVENT_DRIVEN,
        requested_by=event.source,
        priority=Priority(recommendation.priority),
        request_time=datetime.now(UTC),
        scope=dict(recommendation.scope),
        inputs={},
        options={},
        dependency_refs=[],
    )


def build_job_requests(
    event: Event,
    recommendations: Sequence[DownstreamTriggerRecommendation],
) -> list[JobRequest]:
    return [build_job_request(event, rec) for rec in recommendations]


__all__ = [
    "build_job_request",
    "build_job_requests",
]
