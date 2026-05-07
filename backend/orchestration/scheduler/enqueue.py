"""Event-driven enqueue adapter.

Bridges the pure event router (:mod:`backend.orchestration.events.router`)
to the existing Slice 14 :class:`QueueService`. This is the *only* place in
Slice 15 that touches the database, and it does so through QueueService —
no manual ``Job`` row inserts. Dedupe is delegated to QueueService, so
re-routing the same event reuses the existing queued/running row instead
of creating duplicates.

No worker execution happens here. Enqueue is enqueue: the Slice 14 runner
is started separately by callers that own retry / dispatch policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from backend.orchestration.events.payloads import Event
from backend.orchestration.events.router import (
    EventRouter,
    RouteResult,
    route_event,
)
from backend.orchestration.invalidation.types import InvalidationDirective
from backend.orchestration.queues.service import EnqueueResult, QueueService
from backend.orchestration.scheduler.router import build_job_request


class EnqueuedFromEvent(NamedTuple):
    """One queue admission decision tied back to the event that produced it."""

    enqueue_result: EnqueueResult
    job_type: str
    reason: str


@dataclass(frozen=True)
class EventDispatchResult:
    """Combined output of routing + enqueueing one event.

    Mirrors :class:`RouteResult` plus the queue outcome so callers (admin
    triggers, integration tests) can audit what happened without re-running
    the router.
    """

    event: Event
    route: RouteResult
    enqueued: tuple[EnqueuedFromEvent, ...]
    invalidations: tuple[InvalidationDirective, ...]
    suppressed: bool
    suppression_reason: str | None


class EventEnqueueService:
    """Routes an event and enqueues each recommendation through QueueService.

    The router stays pure; this service is the narrow adapter that touches
    the queue. Tests can substitute a fake :class:`EventRouter` or stub
    :class:`QueueService` independently.
    """

    def __init__(
        self,
        queue_service: QueueService,
        *,
        router: EventRouter | None = None,
    ) -> None:
        self._queue = queue_service
        self._router = router or EventRouter()

    def dispatch(self, event: Event) -> EventDispatchResult:
        route = self._router.route(event)
        if route.suppressed:
            return EventDispatchResult(
                event=event,
                route=route,
                enqueued=(),
                invalidations=route.invalidations,
                suppressed=True,
                suppression_reason=route.suppression_reason,
            )

        enqueued: list[EnqueuedFromEvent] = []
        for recommendation in route.recommendations:
            request = build_job_request(event, recommendation)
            result = self._queue.enqueue(request)
            enqueued.append(
                EnqueuedFromEvent(
                    enqueue_result=result,
                    job_type=recommendation.job_type.value,
                    reason=recommendation.reason,
                )
            )
        return EventDispatchResult(
            event=event,
            route=route,
            enqueued=tuple(enqueued),
            invalidations=route.invalidations,
            suppressed=False,
            suppression_reason=None,
        )


# Module-level convenience for callers that don't want a service object.
def dispatch_event(
    event: Event,
    queue_service: QueueService,
) -> EventDispatchResult:
    return EventEnqueueService(queue_service).dispatch(event)


# Re-exports for convenience.
__all__ = [
    "EnqueuedFromEvent",
    "EventDispatchResult",
    "EventEnqueueService",
    "dispatch_event",
    "route_event",
]
