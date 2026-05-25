"""Default refresh cadence posture.

The cadence map is deterministic policy metadata. It does not schedule jobs or
decide source freshness; those concerns remain with future scheduler and
existing provenance/freshness code.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from backend.refresh.job_types import (
    REQUIRED_REFRESH_JOB_TYPES,
    RefreshJobType,
    coerce_refresh_job_type,
)


class CadenceClass(StrEnum):
    FREQUENT = "frequent"
    SEASONAL_FREQUENT = "seasonal_frequent"
    SLOWER = "slower"
    MEDIUM = "medium"
    AFTER_DATA_CHANGES = "after_data_changes"
    SCHEDULED_OR_MANUAL = "scheduled_or_manual"


class TriggerPosture(StrEnum):
    SCHEDULED = "scheduled"
    EVENT_DRIVEN = "event_driven"
    SCHEDULED_AND_EVENT_DRIVEN = "scheduled_and_event_driven"
    MANUAL = "manual"
    SCHEDULED_OR_MANUAL = "scheduled_or_manual"


class RefreshCadencePolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_type: RefreshJobType
    cadence_class: CadenceClass
    trigger_posture: TriggerPosture
    default_queue_group: str = Field(min_length=1)
    notes: str = Field(min_length=1)


CADENCE_BY_JOB_TYPE: dict[RefreshJobType, RefreshCadencePolicy] = {
    RefreshJobType.COMPANY_UNIVERSE_REFRESH: RefreshCadencePolicy(
        job_type=RefreshJobType.COMPANY_UNIVERSE_REFRESH,
        cadence_class=CadenceClass.MEDIUM,
        trigger_posture=TriggerPosture.SCHEDULED_AND_EVENT_DRIVEN,
        default_queue_group="foundational",
        notes="Company-universe refresh is medium cadence and may also follow source changes.",
    ),
    RefreshJobType.PRESENCE_REFRESH: RefreshCadencePolicy(
        job_type=RefreshJobType.PRESENCE_REFRESH,
        cadence_class=CadenceClass.SLOWER,
        trigger_posture=TriggerPosture.SCHEDULED_AND_EVENT_DRIVEN,
        default_queue_group="foundational",
        notes="Presence changes slower than hiring, with targeted event-driven repair allowed.",
    ),
    RefreshJobType.HIRING_REFRESH: RefreshCadencePolicy(
        job_type=RefreshJobType.HIRING_REFRESH,
        cadence_class=CadenceClass.FREQUENT,
        trigger_posture=TriggerPosture.SCHEDULED_AND_EVENT_DRIVEN,
        default_queue_group="refresh",
        notes="Hiring signals are frequent refresh inputs.",
    ),
    RefreshJobType.ENTRY_LEVEL_REFRESH: RefreshCadencePolicy(
        job_type=RefreshJobType.ENTRY_LEVEL_REFRESH,
        cadence_class=CadenceClass.SEASONAL_FREQUENT,
        trigger_posture=TriggerPosture.SCHEDULED_AND_EVENT_DRIVEN,
        default_queue_group="refresh",
        notes="Entry-level refresh is seasonal, frequent during recruiting windows.",
    ),
    RefreshJobType.SCORE_RECOMPUTE: RefreshCadencePolicy(
        job_type=RefreshJobType.SCORE_RECOMPUTE,
        cadence_class=CadenceClass.AFTER_DATA_CHANGES,
        trigger_posture=TriggerPosture.EVENT_DRIVEN,
        default_queue_group="refresh",
        notes="Scores recompute after upstream canonical data changes.",
    ),
    RefreshJobType.OUTPUT_REBUILD: RefreshCadencePolicy(
        job_type=RefreshJobType.OUTPUT_REBUILD,
        cadence_class=CadenceClass.AFTER_DATA_CHANGES,
        trigger_posture=TriggerPosture.EVENT_DRIVEN,
        default_queue_group="output",
        notes="Prepared outputs rebuild after score or canonical data changes.",
    ),
    RefreshJobType.AUDIT_RUN: RefreshCadencePolicy(
        job_type=RefreshJobType.AUDIT_RUN,
        cadence_class=CadenceClass.SCHEDULED_OR_MANUAL,
        trigger_posture=TriggerPosture.SCHEDULED_OR_MANUAL,
        default_queue_group="audit",
        notes="Audits may run on a schedule or manually, matching the existing audit posture.",
    ),
}


def cadence_for(job_type: RefreshJobType | str) -> RefreshCadencePolicy:
    return CADENCE_BY_JOB_TYPE[coerce_refresh_job_type(job_type)]


assert frozenset(CADENCE_BY_JOB_TYPE) == REQUIRED_REFRESH_JOB_TYPES


__all__ = [
    "CADENCE_BY_JOB_TYPE",
    "CadenceClass",
    "RefreshCadencePolicy",
    "TriggerPosture",
    "cadence_for",
]
