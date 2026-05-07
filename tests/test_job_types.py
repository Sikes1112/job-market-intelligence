from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)
from backend.shared.state import ObjectState

EXPECTED_JOB_TYPES = {
    "geography_build",
    "company_universe_intake",
    "eligibility_classification",
    "presence_mapping",
    "hiring_refresh",
    "entry_level_refresh",
    "region_score_recompute",
    "region_output_build",
    "company_output_build",
    "comparison_cache_build",
    "personal_overlay_query",
    "contextual_challenge_build",
    "audit",
}

EXPECTED_JOB_STATUSES = {
    "queued",
    "running",
    "succeeded",
    "succeeded_with_warnings",
    "partial",
    "failed",
    "cancelled",
}


def test_all_documented_job_types_present() -> None:
    assert JobType.values() == EXPECTED_JOB_TYPES


def test_all_documented_job_statuses_present() -> None:
    assert JobStatus.values() == EXPECTED_JOB_STATUSES


def test_job_status_and_object_state_are_distinct_enum_classes() -> None:
    """JobStatus describes a *job*'s execution lifecycle; ObjectState describes a
    canonical *object*'s usable state. The docs (DATA_MODEL.md §9 and
    OBJECT_STATE_MODEL.md §3) deliberately reuse a few string values across the
    two lifecycles (e.g. ``partial`` and ``failed``), but the enums are
    type-distinct and must not be silently substituted for one another.
    """
    assert JobStatus is not ObjectState
    assert not isinstance(JobStatus.PARTIAL, ObjectState)
    assert not isinstance(ObjectState.FRESH, JobStatus)
    # The intentional overlap on string values is documented, not accidental.
    assert JobStatus.values() & ObjectState.values() == {"partial", "failed"}


def test_trigger_type_enum_values() -> None:
    assert {t.value for t in TriggerType} == {
        "scheduled",
        "event_driven",
        "manual",
        "user_query",
    }


def test_priority_enum_values() -> None:
    assert {p.value for p in Priority} == {"low", "normal", "high", "urgent"}


def test_terminal_statuses_are_complete() -> None:
    terminal = JobStatus.terminal()
    assert JobStatus.SUCCEEDED in terminal
    assert JobStatus.SUCCEEDED_WITH_WARNINGS in terminal
    assert JobStatus.PARTIAL in terminal
    assert JobStatus.FAILED in terminal
    assert JobStatus.CANCELLED in terminal
    assert JobStatus.QUEUED not in terminal
    assert JobStatus.RUNNING not in terminal


def test_successful_statuses_match_spec() -> None:
    successful = JobStatus.successful()
    assert successful == {JobStatus.SUCCEEDED, JobStatus.SUCCEEDED_WITH_WARNINGS}
    # PARTIAL is intentionally not "successful" per JOB_CONTRACT_SPEC.md §21.
    assert JobStatus.PARTIAL not in successful
