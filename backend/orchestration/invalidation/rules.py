"""Per-event invalidation rules.

Pure functions. Given an :class:`Event`, return the structured
:class:`InvalidationDirective` list per ``EVENT_TRIGGER_MAP.md`` §3 / §8.

Scoping conventions (deterministic, alphabetically ordered within target):

* region-level events emit one directive per ``region_id``;
* company-level events emit one directive per ``company_id``;
* company-region-pair events emit one directive per ``(company_id,
  region_id)`` pair.

Rules **never** import domain services or output builders — they only know
about events and invalidation targets.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from backend.orchestration.events.exceptions import (
    EventValidationError,
    UnsupportedEventType,
)
from backend.orchestration.events.payloads import Event
from backend.orchestration.events.types import EventType
from backend.orchestration.invalidation.types import (
    InvalidationDirective,
    InvalidationTarget,
)

# ---------------------------------------------------------------------------
# Scope-extraction helpers — kept here (not in payloads) so the model stays
# generic and future event types can reuse the same helpers.
# ---------------------------------------------------------------------------


def _require_region_id(event: Event) -> str:
    region_id = event.scope.get("region_id")
    if not isinstance(region_id, str) or not region_id.strip():
        raise EventValidationError(
            f"{event.event_type.value}: scope.region_id must be a non-empty string"
        )
    return region_id


def _require_region_ids(event: Event) -> tuple[str, ...]:
    raw = event.scope.get("region_ids")
    if not isinstance(raw, list) or not raw:
        raise EventValidationError(
            f"{event.event_type.value}: scope.region_ids must be a non-empty list"
        )
    out: list[str] = []
    for value in raw:
        if not isinstance(value, str) or not value.strip():
            raise EventValidationError(
                f"{event.event_type.value}: scope.region_ids entries must be "
                "non-empty strings"
            )
        out.append(value)
    return tuple(sorted(set(out)))


def _require_company_id(event: Event) -> str:
    company_id = event.scope.get("company_id")
    if not isinstance(company_id, str) or not company_id.strip():
        raise EventValidationError(
            f"{event.event_type.value}: scope.company_id must be a non-empty string"
        )
    return company_id


def _require_company_region_pairs(
    event: Event,
) -> tuple[tuple[str, str], ...]:
    raw = event.scope.get("company_region_pairs")
    if not isinstance(raw, list) or not raw:
        raise EventValidationError(
            f"{event.event_type.value}: scope.company_region_pairs must be a "
            "non-empty list"
        )
    seen: set[tuple[str, str]] = set()
    pairs: list[tuple[str, str]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise EventValidationError(
                f"{event.event_type.value}: each company_region_pair must be "
                "an object with company_id and region_id"
            )
        company_id = entry.get("company_id")
        region_id = entry.get("region_id")
        if (
            not isinstance(company_id, str)
            or not company_id.strip()
            or not isinstance(region_id, str)
            or not region_id.strip()
        ):
            raise EventValidationError(
                f"{event.event_type.value}: each company_region_pair must "
                "contain non-empty company_id and region_id"
            )
        key = (company_id, region_id)
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)
    pairs.sort()
    return tuple(pairs)


def _require_optional_region_ids(event: Event) -> tuple[str, ...]:
    raw = event.scope.get("region_ids", [])
    if not isinstance(raw, list):
        raise EventValidationError(
            f"{event.event_type.value}: scope.region_ids must be a list"
        )
    out: list[str] = []
    for value in raw:
        if not isinstance(value, str) or not value.strip():
            raise EventValidationError(
                f"{event.event_type.value}: scope.region_ids entries must be "
                "non-empty strings"
            )
        out.append(value)
    return tuple(sorted(set(out)))


def _require_comparison_pair(event: Event) -> tuple[str, str]:
    region_a = event.scope.get("region_a")
    region_b = event.scope.get("region_b")
    if (
        not isinstance(region_a, str)
        or not region_a.strip()
        or not isinstance(region_b, str)
        or not region_b.strip()
    ):
        raise EventValidationError(
            f"{event.event_type.value}: scope.region_a and scope.region_b "
            "must be non-empty strings"
        )
    if region_a == region_b:
        raise EventValidationError(
            f"{event.event_type.value}: comparison requires two distinct "
            f"regions; got {region_a!r} twice"
        )
    return region_a, region_b


def canonical_comparison_id(a: str, b: str) -> str:
    """Order-independent subject_id for a region pair.

    Mirrors :func:`backend.outputs.comparison_output.canonical_comparison_id`
    *intentionally* — the slice prompt allows duplicating a tiny pure helper
    rather than importing the outputs layer. The shape (``min__max``) and the
    rejection of blank/identical IDs match Slice 11 so subject IDs stay
    consistent across layers. Validate via the helper above before calling.
    """
    return f"{min(a, b)}__{max(a, b)}"


# ---------------------------------------------------------------------------
# Directive builders, per event type.
# ---------------------------------------------------------------------------


def _per_region(
    target: InvalidationTarget,
    region_ids: Sequence[str],
    *,
    reason: str,
) -> list[InvalidationDirective]:
    return [
        InvalidationDirective(
            target=target,
            scope={"region_id": region_id},
            reason=reason,
        )
        for region_id in region_ids
    ]


def _per_pair(
    target: InvalidationTarget,
    pairs: Sequence[tuple[str, str]],
    *,
    reason: str,
) -> list[InvalidationDirective]:
    return [
        InvalidationDirective(
            target=target,
            scope={"company_id": company_id, "region_id": region_id},
            reason=reason,
        )
        for (company_id, region_id) in pairs
    ]


def _flatten(items: Iterable[Iterable[InvalidationDirective]]) -> list[InvalidationDirective]:
    out: list[InvalidationDirective] = []
    for chunk in items:
        out.extend(chunk)
    return out


# ---------------------------------------------------------------------------
# Per-event-type rules.
# ---------------------------------------------------------------------------


def _region_added(event: Event) -> list[InvalidationDirective]:
    region_id = _require_region_id(event)
    return [
        InvalidationDirective(
            target=InvalidationTarget.REGION_OUTPUT,
            scope={"region_id": region_id},
            reason="region added — bootstrap region output",
        ),
    ]


def _region_definition_changed(event: Event) -> list[InvalidationDirective]:
    region_id = _require_region_id(event)
    return [
        InvalidationDirective(
            target=InvalidationTarget.REGION_SCORE,
            scope={"region_id": region_id},
            reason="region definition changed — recompute scores",
        ),
        InvalidationDirective(
            target=InvalidationTarget.REGION_OUTPUT,
            scope={"region_id": region_id},
            reason="region definition changed — rebuild output",
        ),
        InvalidationDirective(
            target=InvalidationTarget.COMPARISON_OUTPUT,
            scope={"region_id": region_id},
            reason="region definition changed — invalidate comparisons "
            "involving region",
        ),
    ]


def _new_company_candidate_added(event: Event) -> list[InvalidationDirective]:
    company_id = _require_company_id(event)
    return [
        InvalidationDirective(
            target=InvalidationTarget.COMPANY_CLASSIFICATION,
            scope={"company_id": company_id},
            reason="new candidate — classify before any downstream work",
        ),
    ]


def _company_classification_corrected(event: Event) -> list[InvalidationDirective]:
    company_id = _require_company_id(event)
    region_ids = _require_optional_region_ids(event)
    directives: list[InvalidationDirective] = [
        InvalidationDirective(
            target=InvalidationTarget.PRESENCE_MAPPING,
            scope={"company_id": company_id},
            reason="classification corrected — re-map presence",
        ),
        InvalidationDirective(
            target=InvalidationTarget.COMPANY_OUTPUT,
            scope={"company_id": company_id},
            reason="classification corrected — rebuild company output",
        ),
    ]
    directives.extend(
        _per_region(
            InvalidationTarget.REGION_SCORE,
            region_ids,
            reason="classification corrected — recompute region scores",
        )
    )
    directives.extend(
        _per_region(
            InvalidationTarget.REGION_OUTPUT,
            region_ids,
            reason="classification corrected — rebuild region output",
        )
    )
    directives.extend(
        _per_region(
            InvalidationTarget.COMPARISON_OUTPUT,
            region_ids,
            reason="classification corrected — invalidate comparisons involving region",
        )
    )
    return directives


def _company_presence_updated(event: Event) -> list[InvalidationDirective]:
    pairs = _require_company_region_pairs(event)
    affected_regions = tuple(sorted({region_id for (_, region_id) in pairs}))
    affected_companies = tuple(sorted({company_id for (company_id, _) in pairs}))
    return _flatten(
        [
            _per_pair(
                InvalidationTarget.HIRING_REFRESH,
                pairs,
                reason="presence updated — refresh hiring for pair",
            ),
            _per_pair(
                InvalidationTarget.ENTRY_LEVEL_REFRESH,
                pairs,
                reason="presence updated — refresh entry-level for pair",
            ),
            _per_region(
                InvalidationTarget.REGION_SCORE,
                affected_regions,
                reason="presence updated — recompute region score",
            ),
            _per_region(
                InvalidationTarget.REGION_OUTPUT,
                affected_regions,
                reason="presence updated — rebuild region output",
            ),
            _per_region(
                InvalidationTarget.COMPARISON_OUTPUT,
                affected_regions,
                reason="presence updated — invalidate comparisons involving region",
            ),
            [
                InvalidationDirective(
                    target=InvalidationTarget.COMPANY_OUTPUT,
                    scope={"company_id": company_id},
                    reason="presence updated — rebuild company output",
                )
                for company_id in affected_companies
            ],
        ]
    )


def _hiring_data_updated(event: Event) -> list[InvalidationDirective]:
    pairs = _require_company_region_pairs(event)
    affected_regions = tuple(sorted({region_id for (_, region_id) in pairs}))
    affected_companies = tuple(sorted({company_id for (company_id, _) in pairs}))
    return _flatten(
        [
            _per_pair(
                InvalidationTarget.ENTRY_LEVEL_REFRESH,
                pairs,
                reason="hiring updated — refresh entry-level for pair",
            ),
            _per_region(
                InvalidationTarget.REGION_SCORE,
                affected_regions,
                reason="hiring updated — recompute region score",
            ),
            _per_region(
                InvalidationTarget.REGION_OUTPUT,
                affected_regions,
                reason="hiring updated — rebuild region output",
            ),
            _per_region(
                InvalidationTarget.COMPARISON_OUTPUT,
                affected_regions,
                reason="hiring updated — invalidate comparisons involving region",
            ),
            [
                InvalidationDirective(
                    target=InvalidationTarget.COMPANY_OUTPUT,
                    scope={"company_id": company_id},
                    reason="hiring updated — rebuild company output",
                )
                for company_id in affected_companies
            ],
        ]
    )


def _entry_level_signal_updated(event: Event) -> list[InvalidationDirective]:
    pairs = _require_company_region_pairs(event)
    affected_regions = tuple(sorted({region_id for (_, region_id) in pairs}))
    affected_companies = tuple(sorted({company_id for (company_id, _) in pairs}))
    return _flatten(
        [
            _per_region(
                InvalidationTarget.REGION_SCORE,
                affected_regions,
                reason="entry-level updated — recompute region score",
            ),
            _per_region(
                InvalidationTarget.REGION_OUTPUT,
                affected_regions,
                reason="entry-level updated — rebuild region output",
            ),
            _per_region(
                InvalidationTarget.COMPARISON_OUTPUT,
                affected_regions,
                reason="entry-level updated — invalidate comparisons involving region",
            ),
            [
                InvalidationDirective(
                    target=InvalidationTarget.COMPANY_OUTPUT,
                    scope={"company_id": company_id},
                    reason="entry-level updated — rebuild company output",
                )
                for company_id in affected_companies
            ],
        ]
    )


def _normalization_inputs_updated(event: Event) -> list[InvalidationDirective]:
    region_ids = _require_region_ids(event)
    return _flatten(
        [
            _per_region(
                InvalidationTarget.REGION_SCORE,
                region_ids,
                reason="normalization inputs updated — recompute region score",
            ),
            _per_region(
                InvalidationTarget.REGION_OUTPUT,
                region_ids,
                reason="normalization inputs updated — rebuild region output",
            ),
            _per_region(
                InvalidationTarget.COMPARISON_OUTPUT,
                region_ids,
                reason="normalization inputs updated — invalidate comparisons involving region",
            ),
        ]
    )


def _comparison_requested(event: Event) -> list[InvalidationDirective]:
    region_a, region_b = _require_comparison_pair(event)
    comparison_id = canonical_comparison_id(region_a, region_b)
    return [
        InvalidationDirective(
            target=InvalidationTarget.COMPARISON_OUTPUT,
            scope={
                "comparison_id": comparison_id,
                "region_a": min(region_a, region_b),
                "region_b": max(region_a, region_b),
            },
            reason="comparison requested — ensure cache is fresh",
        )
    ]


_RULES: dict[EventType, Any] = {
    EventType.REGION_ADDED: _region_added,
    EventType.REGION_DEFINITION_CHANGED: _region_definition_changed,
    EventType.NEW_COMPANY_CANDIDATE_ADDED: _new_company_candidate_added,
    EventType.COMPANY_CLASSIFICATION_CORRECTED: _company_classification_corrected,
    EventType.COMPANY_PRESENCE_UPDATED: _company_presence_updated,
    EventType.HIRING_DATA_UPDATED: _hiring_data_updated,
    EventType.ENTRY_LEVEL_SIGNAL_UPDATED: _entry_level_signal_updated,
    EventType.NORMALIZATION_INPUTS_UPDATED: _normalization_inputs_updated,
    EventType.COMPARISON_REQUESTED: _comparison_requested,
}


def derive_invalidation_directives(event: Event) -> list[InvalidationDirective]:
    """Return the deterministic invalidation directives for ``event``.

    Order is stable: per-target rule order is fixed inside each handler, and
    region/company iteration is sorted. Re-running this function with the
    same event yields the same list.
    """
    rule = _RULES.get(event.event_type)
    if rule is None:
        raise UnsupportedEventType(
            f"no invalidation rule for event_type {event.event_type.value!r}"
        )
    return rule(event)


__all__ = [
    "canonical_comparison_id",
    "derive_invalidation_directives",
]
