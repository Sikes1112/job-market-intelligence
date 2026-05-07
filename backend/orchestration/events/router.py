"""Event-to-job router.

Pure function. Given an :class:`Event`, returns a deterministic list of
:class:`DownstreamTriggerRecommendation` that the scheduler should consider
enqueueing, plus the invalidation directives for the same event.

Routing rules follow ``EVENT_TRIGGER_MAP.md`` §3, scoped to MVP V1:

* foundational job types are never recommended by dynamic events
  (``HIRING_DATA_UPDATED``, ``ENTRY_LEVEL_SIGNAL_UPDATED``,
  ``NORMALIZATION_INPUTS_UPDATED``, ``COMPARISON_REQUESTED``);
* ``REGION_ADDED`` is treated narrowly — it bootstraps the region's *output*
  shell. Hiring/entry-level/score recompute happen only after the
  corresponding domain events fire (presence updated, hiring updated,
  etc.). This honors the slice prompt's "scoped output rebuild for the
  affected region if enough prerequisites exist" guidance and avoids
  speculative full-region rebuild before any data arrives.
* ``no_meaningful_change`` events are visibly suppressed: the router
  returns no recommendations and no invalidation directives, but reports
  ``suppressed=True`` and a structured reason string so callers can audit.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from backend.orchestration.events.exceptions import UnsupportedEventType
from backend.orchestration.events.payloads import Event
from backend.orchestration.events.recommendations import (
    DownstreamTriggerRecommendation,
)
from backend.orchestration.events.types import EventType
from backend.orchestration.invalidation.rules import (
    canonical_comparison_id,
    derive_invalidation_directives,
)
from backend.orchestration.invalidation.types import InvalidationDirective
from backend.orchestration.jobs.types import JobType, Priority

# Job types Slice 15 must never propose — they are foundational rebuilds
# that belong to admin/manual slices, not dynamic event paths.
_FOUNDATIONAL_JOB_TYPES: frozenset[JobType] = frozenset(
    {
        JobType.GEOGRAPHY_BUILD,
        JobType.COMPANY_UNIVERSE_INTAKE,
    }
)

# Job types Slice 15 must never propose because they belong to later slices
# (audit = Slice 16, contextual = Slice 17, personalization = interactive
# only / Slice 13).
_DEFERRED_JOB_TYPES: frozenset[JobType] = frozenset(
    {
        JobType.AUDIT,
        JobType.CONTEXTUAL_CHALLENGE_BUILD,
        JobType.PERSONAL_OVERLAY_QUERY,
    }
)


@dataclass(frozen=True)
class RouteResult:
    """Output of :func:`route_event` and :meth:`EventRouter.route`."""

    event: Event
    recommendations: tuple[DownstreamTriggerRecommendation, ...]
    invalidations: tuple[InvalidationDirective, ...]
    suppressed: bool = False
    suppression_reason: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Per-event recommendation builders.
# ---------------------------------------------------------------------------


def _rec(
    job_type: JobType,
    *,
    reason: str,
    scope: dict,
    priority: Priority = Priority.NORMAL,
) -> DownstreamTriggerRecommendation:
    if job_type in _FOUNDATIONAL_JOB_TYPES:
        raise AssertionError(
            f"Slice 15 must not recommend foundational job_type "
            f"{job_type.value!r}"
        )
    if job_type in _DEFERRED_JOB_TYPES:
        raise AssertionError(
            f"Slice 15 must not recommend deferred job_type "
            f"{job_type.value!r}"
        )
    return DownstreamTriggerRecommendation(
        job_type=job_type,
        reason=reason,
        scope=scope,
        priority=priority,
    )


def _region_added_recs(event: Event) -> list[DownstreamTriggerRecommendation]:
    region_id = event.scope["region_id"]
    # Output build only — the region exists, but no presence/hiring/
    # entry-level data has been gathered yet. Those rebuilds fire when the
    # corresponding domain events arrive. The output handler honors
    # partial / unavailable input by returning the appropriate state.
    return [
        _rec(
            JobType.REGION_OUTPUT_BUILD,
            reason="region added — bootstrap region output shell",
            scope={"region_ids": [region_id]},
        )
    ]


def _region_definition_changed_recs(
    event: Event,
) -> list[DownstreamTriggerRecommendation]:
    region_id = event.scope["region_id"]
    return [
        _rec(
            JobType.REGION_SCORE_RECOMPUTE,
            reason="region definition changed — recompute scores",
            scope={"region_ids": [region_id]},
        ),
        _rec(
            JobType.REGION_OUTPUT_BUILD,
            reason="region definition changed — rebuild output",
            scope={"region_ids": [region_id]},
        ),
    ]


def _new_company_candidate_added_recs(
    event: Event,
) -> list[DownstreamTriggerRecommendation]:
    company_id = event.scope["company_id"]
    return [
        _rec(
            JobType.ELIGIBILITY_CLASSIFICATION,
            reason="new candidate — classify before any downstream work",
            scope={"company_ids": [company_id]},
        )
    ]


def _company_classification_corrected_recs(
    event: Event,
) -> list[DownstreamTriggerRecommendation]:
    company_id = event.scope["company_id"]
    region_ids = sorted(set(event.scope.get("region_ids", [])))
    out: list[DownstreamTriggerRecommendation] = [
        _rec(
            JobType.PRESENCE_MAPPING,
            reason="classification corrected — re-map presence",
            scope={"company_ids": [company_id], "region_ids": region_ids},
        ),
        _rec(
            JobType.COMPANY_OUTPUT_BUILD,
            reason="classification corrected — rebuild company output",
            scope={"company_ids": [company_id]},
        ),
    ]
    if region_ids:
        out.append(
            _rec(
                JobType.REGION_SCORE_RECOMPUTE,
                reason="classification corrected — recompute region scores",
                scope={"region_ids": region_ids},
            )
        )
        out.append(
            _rec(
                JobType.REGION_OUTPUT_BUILD,
                reason="classification corrected — rebuild region outputs",
                scope={"region_ids": region_ids},
            )
        )
    return out


def _company_presence_updated_recs(
    event: Event,
) -> list[DownstreamTriggerRecommendation]:
    pairs = _sorted_pairs(event.scope["company_region_pairs"])
    affected_regions = sorted({region_id for (_, region_id) in pairs})
    affected_companies = sorted({company_id for (company_id, _) in pairs})
    return [
        _rec(
            JobType.HIRING_REFRESH,
            reason="presence updated — refresh hiring",
            scope={
                "company_region_pairs": [
                    {"company_id": c, "region_id": r} for (c, r) in pairs
                ]
            },
        ),
        _rec(
            JobType.ENTRY_LEVEL_REFRESH,
            reason="presence updated — refresh entry-level",
            scope={
                "company_region_pairs": [
                    {"company_id": c, "region_id": r} for (c, r) in pairs
                ]
            },
        ),
        _rec(
            JobType.REGION_SCORE_RECOMPUTE,
            reason="presence updated — recompute region scores",
            scope={"region_ids": affected_regions},
        ),
        _rec(
            JobType.REGION_OUTPUT_BUILD,
            reason="presence updated — rebuild region outputs",
            scope={"region_ids": affected_regions},
        ),
        _rec(
            JobType.COMPANY_OUTPUT_BUILD,
            reason="presence updated — rebuild company outputs",
            scope={"company_ids": affected_companies},
        ),
    ]


def _hiring_data_updated_recs(
    event: Event,
) -> list[DownstreamTriggerRecommendation]:
    pairs = _sorted_pairs(event.scope["company_region_pairs"])
    affected_regions = sorted({region_id for (_, region_id) in pairs})
    affected_companies = sorted({company_id for (company_id, _) in pairs})
    return [
        _rec(
            JobType.ENTRY_LEVEL_REFRESH,
            reason="hiring updated — refresh entry-level",
            scope={
                "company_region_pairs": [
                    {"company_id": c, "region_id": r} for (c, r) in pairs
                ]
            },
        ),
        _rec(
            JobType.REGION_SCORE_RECOMPUTE,
            reason="hiring updated — recompute region scores",
            scope={"region_ids": affected_regions},
        ),
        _rec(
            JobType.REGION_OUTPUT_BUILD,
            reason="hiring updated — rebuild region outputs",
            scope={"region_ids": affected_regions},
        ),
        _rec(
            JobType.COMPANY_OUTPUT_BUILD,
            reason="hiring updated — rebuild company outputs",
            scope={"company_ids": affected_companies},
        ),
    ]


def _entry_level_signal_updated_recs(
    event: Event,
) -> list[DownstreamTriggerRecommendation]:
    pairs = _sorted_pairs(event.scope["company_region_pairs"])
    affected_regions = sorted({region_id for (_, region_id) in pairs})
    affected_companies = sorted({company_id for (company_id, _) in pairs})
    return [
        _rec(
            JobType.REGION_SCORE_RECOMPUTE,
            reason="entry-level updated — recompute region scores",
            scope={"region_ids": affected_regions},
        ),
        _rec(
            JobType.REGION_OUTPUT_BUILD,
            reason="entry-level updated — rebuild region outputs",
            scope={"region_ids": affected_regions},
        ),
        _rec(
            JobType.COMPANY_OUTPUT_BUILD,
            reason="entry-level updated — rebuild company outputs",
            scope={"company_ids": affected_companies},
        ),
    ]


def _normalization_inputs_updated_recs(
    event: Event,
) -> list[DownstreamTriggerRecommendation]:
    region_ids = sorted(set(event.scope["region_ids"]))
    return [
        _rec(
            JobType.REGION_SCORE_RECOMPUTE,
            reason="normalization inputs updated — recompute region scores",
            scope={"region_ids": region_ids},
        ),
        _rec(
            JobType.REGION_OUTPUT_BUILD,
            reason="normalization inputs updated — rebuild region outputs",
            scope={"region_ids": region_ids},
        ),
    ]


def _comparison_requested_recs(
    event: Event,
) -> list[DownstreamTriggerRecommendation]:
    region_a = event.scope["region_a"]
    region_b = event.scope["region_b"]
    a, b = sorted([region_a, region_b])
    return [
        _rec(
            JobType.COMPARISON_CACHE_BUILD,
            reason="comparison requested — build/refresh cache",
            scope={"comparison_pairs": [[a, b]]},
            priority=Priority.HIGH,
        )
    ]


def _sorted_pairs(raw: Sequence[dict]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    pairs: list[tuple[str, str]] = []
    for entry in raw:
        key = (entry["company_id"], entry["region_id"])
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)
    pairs.sort()
    return pairs


_BUILDERS = {
    EventType.REGION_ADDED: _region_added_recs,
    EventType.REGION_DEFINITION_CHANGED: _region_definition_changed_recs,
    EventType.NEW_COMPANY_CANDIDATE_ADDED: _new_company_candidate_added_recs,
    EventType.COMPANY_CLASSIFICATION_CORRECTED: _company_classification_corrected_recs,
    EventType.COMPANY_PRESENCE_UPDATED: _company_presence_updated_recs,
    EventType.HIRING_DATA_UPDATED: _hiring_data_updated_recs,
    EventType.ENTRY_LEVEL_SIGNAL_UPDATED: _entry_level_signal_updated_recs,
    EventType.NORMALIZATION_INPUTS_UPDATED: _normalization_inputs_updated_recs,
    EventType.COMPARISON_REQUESTED: _comparison_requested_recs,
}


def route_event(event: Event) -> RouteResult:
    """Return the deterministic :class:`RouteResult` for ``event``.

    The function is pure — no DB access, no enqueue. Use
    :class:`backend.orchestration.scheduler.enqueue.EventEnqueueService` to
    actually persist queued jobs.
    """
    if event.event_type not in _BUILDERS:
        raise UnsupportedEventType(
            f"no router rule for event_type {event.event_type.value!r}"
        )

    if event.no_meaningful_change:
        return RouteResult(
            event=event,
            recommendations=(),
            invalidations=(),
            suppressed=True,
            suppression_reason=(
                f"event {event.event_type.value} carried "
                "no_meaningful_change=True; downstream work suppressed per "
                "EVENT_TRIGGER_MAP.md §8"
            ),
        )

    # Validate scope via invalidation rules first; they share helpers.
    invalidations = tuple(derive_invalidation_directives(event))
    recommendations = tuple(_BUILDERS[event.event_type](event))
    notes: tuple[str, ...] = ()
    if event.event_type is EventType.COMPARISON_REQUESTED:
        a = event.scope["region_a"]
        b = event.scope["region_b"]
        notes = (
            f"canonical_comparison_id={canonical_comparison_id(a, b)}",
        )
    return RouteResult(
        event=event,
        recommendations=recommendations,
        invalidations=invalidations,
        notes=notes,
    )


class EventRouter:
    """Stateless wrapper around :func:`route_event` for DI-friendly callers."""

    def route(self, event: Event) -> RouteResult:
        return route_event(event)


__all__ = [
    "EventRouter",
    "RouteResult",
    "route_event",
]
