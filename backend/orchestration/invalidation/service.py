"""Thin facade over :mod:`backend.orchestration.invalidation.rules`.

Slice 15 keeps invalidation as *recommendations* — no rows are mutated.
This service exists so that future slices (audit, repair) can wire alternate
strategies (e.g. mark ``output_metadata`` stale) without rewriting the
event router. For MVP it just delegates.
"""

from __future__ import annotations

from backend.orchestration.events.payloads import Event
from backend.orchestration.invalidation.rules import (
    derive_invalidation_directives,
)
from backend.orchestration.invalidation.types import InvalidationDirective


class InvalidationService:
    """Stateless wrapper. Constructed once and reused by the scheduler."""

    def directives_for(self, event: Event) -> list[InvalidationDirective]:
        return derive_invalidation_directives(event)
