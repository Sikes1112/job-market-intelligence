"""Invalidation facade over :mod:`backend.orchestration.invalidation.rules`.

The pure rules still produce deterministic directives. This service can also
apply those directives narrowly to existing ``OutputMetadata`` rows by marking
fresh rows stale. It does not delete rows, rebuild outputs, enqueue jobs, or
run workers.
"""

from __future__ import annotations

from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.orchestration.events.payloads import Event
from backend.orchestration.events.types import EventType
from backend.orchestration.invalidation.rules import (
    derive_invalidation_directives,
)
from backend.orchestration.invalidation.types import (
    InvalidationDirective,
    InvalidationTarget,
)
from backend.outputs.models import OutputMetadata
from backend.outputs.types import OutputType
from backend.shared.state import ObjectState, validate_transition


class InvalidationApplyResult(NamedTuple):
    directives: list[InvalidationDirective]
    stale_output_ids: list[str]


class InvalidationService:
    """Stateless wrapper. Constructed once and reused by the scheduler."""

    def directives_for(self, event: Event) -> list[InvalidationDirective]:
        return derive_invalidation_directives(event)

    def mark_stale_for(
        self, event: Event, *, session: Session
    ) -> InvalidationApplyResult:
        """Apply scoped output invalidation for events that changed source data.

        ``COMPARISON_REQUESTED`` is a cache-warm request, not source-data
        invalidation, so it returns directives without mutating rows.
        """
        directives = self.directives_for(event)
        if event.no_meaningful_change or event.event_type is EventType.COMPARISON_REQUESTED:
            return InvalidationApplyResult(directives=directives, stale_output_ids=[])

        changed: dict[str, OutputMetadata] = {}
        for directive in directives:
            for row in _rows_for_directive(session, directive):
                if row.output_id in changed:
                    continue
                if row.state == ObjectState.STALE.value:
                    continue
                if row.state != ObjectState.FRESH.value:
                    continue
                validate_transition(row.state, ObjectState.STALE)
                row.state = ObjectState.STALE.value
                changed[row.output_id] = row

        if changed:
            session.flush()
        return InvalidationApplyResult(
            directives=directives,
            stale_output_ids=sorted(changed),
        )


def _rows_for_directive(
    session: Session, directive: InvalidationDirective
) -> list[OutputMetadata]:
    target = directive.target
    if target is InvalidationTarget.REGION_OUTPUT:
        region_id = directive.scope.get("region_id")
        if isinstance(region_id, str) and region_id:
            row = _output_by_type_and_subject(
                session, OutputType.REGION_OUTPUT.value, region_id
            )
            return [row] if row is not None else []
    if target is InvalidationTarget.COMPANY_OUTPUT:
        company_id = directive.scope.get("company_id")
        if isinstance(company_id, str) and company_id:
            row = _output_by_type_and_subject(
                session, OutputType.COMPANY_OUTPUT.value, company_id
            )
            return [row] if row is not None else []
    if target is InvalidationTarget.COMPARISON_OUTPUT:
        comparison_id = directive.scope.get("comparison_id")
        if isinstance(comparison_id, str) and comparison_id:
            row = _output_by_type_and_subject(
                session, OutputType.COMPARISON_OUTPUT.value, comparison_id
            )
            return [row] if row is not None else []
        region_id = directive.scope.get("region_id")
        if isinstance(region_id, str) and region_id:
            return _comparison_outputs_for_region(session, region_id)
    return []


def _output_by_type_and_subject(
    session: Session, output_type: str, subject_id: str
) -> OutputMetadata | None:
    stmt = select(OutputMetadata).where(
        OutputMetadata.output_type == output_type,
        OutputMetadata.subject_id == subject_id,
    )
    return session.execute(stmt).scalar_one_or_none()


def _comparison_outputs_for_region(
    session: Session, region_id: str
) -> list[OutputMetadata]:
    stmt = (
        select(OutputMetadata)
        .where(OutputMetadata.output_type == OutputType.COMPARISON_OUTPUT.value)
        .order_by(OutputMetadata.subject_id)
    )
    rows = session.execute(stmt).scalars()
    return [
        row
        for row in rows
        if region_id in {part for part in row.subject_id.split("__") if part}
    ]
