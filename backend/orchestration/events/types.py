"""Event vocabulary for Slice 15.

Source: ``EVENT_TRIGGER_MAP.md`` §3 and §10.

Slice 15 owns *event* concerns. ``EventType`` is intentionally separate from
:class:`backend.orchestration.jobs.types.JobType` (job classes) and
:class:`backend.orchestration.jobs.types.TriggerType` (how a *job* was
launched). An :class:`EventType` is what happened in the system; the router
maps each one to the jobs that should run as a result.

Only the events the slice prompt requires for MVP V1 are listed. Future
events (sector-scope changed, eligibility-rules changed, audit-failure
detected, etc.) belong to later slices.
"""

from __future__ import annotations

from enum import StrEnum


class EventType(StrEnum):
    """Events that the orchestration layer routes to jobs / invalidation."""

    REGION_ADDED = "REGION_ADDED"
    REGION_DEFINITION_CHANGED = "REGION_DEFINITION_CHANGED"
    NEW_COMPANY_CANDIDATE_ADDED = "NEW_COMPANY_CANDIDATE_ADDED"
    COMPANY_CLASSIFICATION_CORRECTED = "COMPANY_CLASSIFICATION_CORRECTED"
    COMPANY_PRESENCE_UPDATED = "COMPANY_PRESENCE_UPDATED"
    HIRING_DATA_UPDATED = "HIRING_DATA_UPDATED"
    ENTRY_LEVEL_SIGNAL_UPDATED = "ENTRY_LEVEL_SIGNAL_UPDATED"
    NORMALIZATION_INPUTS_UPDATED = "NORMALIZATION_INPUTS_UPDATED"
    COMPARISON_REQUESTED = "COMPARISON_REQUESTED"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)
