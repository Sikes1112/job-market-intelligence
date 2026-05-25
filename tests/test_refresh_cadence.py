from backend.refresh.cadence import (
    CADENCE_BY_JOB_TYPE,
    CadenceClass,
    TriggerPosture,
    cadence_for,
)
from backend.refresh.job_types import REQUIRED_REFRESH_JOB_TYPES, RefreshJobType


def test_every_required_refresh_job_type_has_cadence_and_trigger_posture() -> None:
    assert frozenset(CADENCE_BY_JOB_TYPE) == REQUIRED_REFRESH_JOB_TYPES
    for job_type, policy in CADENCE_BY_JOB_TYPE.items():
        assert policy.job_type is job_type
        assert isinstance(policy.cadence_class, CadenceClass)
        assert isinstance(policy.trigger_posture, TriggerPosture)
        assert policy.default_queue_group


def test_required_cadence_concepts_are_encoded() -> None:
    assert (
        cadence_for(RefreshJobType.HIRING_REFRESH).cadence_class
        is CadenceClass.FREQUENT
    )
    assert (
        cadence_for(RefreshJobType.ENTRY_LEVEL_REFRESH).cadence_class
        is CadenceClass.SEASONAL_FREQUENT
    )
    assert (
        cadence_for(RefreshJobType.PRESENCE_REFRESH).cadence_class
        is CadenceClass.SLOWER
    )
    assert (
        cadence_for(RefreshJobType.COMPANY_UNIVERSE_REFRESH).cadence_class
        is CadenceClass.MEDIUM
    )
    assert (
        cadence_for(RefreshJobType.SCORE_RECOMPUTE).cadence_class
        is CadenceClass.AFTER_DATA_CHANGES
    )
    assert (
        cadence_for(RefreshJobType.OUTPUT_REBUILD).cadence_class
        is CadenceClass.AFTER_DATA_CHANGES
    )
    assert (
        cadence_for(RefreshJobType.AUDIT_RUN).cadence_class
        is CadenceClass.SCHEDULED_OR_MANUAL
    )


def test_data_change_driven_jobs_are_event_driven() -> None:
    assert (
        cadence_for(RefreshJobType.SCORE_RECOMPUTE).trigger_posture
        is TriggerPosture.EVENT_DRIVEN
    )
    assert (
        cadence_for(RefreshJobType.OUTPUT_REBUILD).trigger_posture
        is TriggerPosture.EVENT_DRIVEN
    )


def test_cadence_lookup_accepts_stable_string_values() -> None:
    policy = cadence_for("hiring_refresh")

    assert policy.job_type is RefreshJobType.HIRING_REFRESH
    assert policy == CADENCE_BY_JOB_TYPE[RefreshJobType.HIRING_REFRESH]
