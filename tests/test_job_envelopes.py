from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from backend.orchestration.events.recommendations import (
    DownstreamTriggerRecommendation,
)
from backend.orchestration.jobs.envelopes import JobRequest, JobResponse
from backend.orchestration.jobs.errors import (
    ErrorCode,
    JobWarning,
    WarningSeverity,
)
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)


def _request(**overrides) -> JobRequest:
    payload = dict(
        job_id="job_geo_001",
        job_type=JobType.GEOGRAPHY_BUILD,
        trigger_type=TriggerType.MANUAL,
        requested_by="admin",
        priority=Priority.HIGH,
        request_time=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        scope={"region_ids": ["greater_boston"]},
        inputs={"region_definitions": []},
        options={"validate_hierarchy": True},
        dependency_refs=[],
    )
    payload.update(overrides)
    return JobRequest(**payload)


def test_request_envelope_round_trips_documented_payload() -> None:
    req = _request()
    dumped = req.model_dump()
    assert dumped["job_type"] == "geography_build"
    assert dumped["trigger_type"] == "manual"
    assert dumped["scope"] == {"region_ids": ["greater_boston"]}
    again = JobRequest.model_validate(dumped)
    assert again == req


def test_request_envelope_requires_job_id_and_type() -> None:
    with pytest.raises(ValidationError):
        JobRequest(
            job_id="",
            job_type=JobType.GEOGRAPHY_BUILD,
            trigger_type=TriggerType.MANUAL,
            requested_by="admin",
            request_time=datetime(2026, 5, 6, tzinfo=UTC),
        )


def test_request_envelope_rejects_naive_request_time() -> None:
    with pytest.raises(ValidationError):
        JobRequest(
            job_id="job_x",
            job_type=JobType.HIRING_REFRESH,
            trigger_type=TriggerType.SCHEDULED,
            requested_by="system",
            request_time=datetime(2026, 5, 6, 16, 0),  # naive
        )


def test_request_envelope_rejects_blank_dependency_ref() -> None:
    with pytest.raises(ValidationError):
        _request(dependency_refs=["presence_v33", "  "])


def test_request_envelope_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        JobRequest.model_validate(
            {
                "job_id": "j1",
                "job_type": "geography_build",
                "trigger_type": "manual",
                "requested_by": "admin",
                "request_time": "2026-05-06T16:00:00+00:00",
                "rogue_field": True,
            }
        )


def test_response_succeeded_envelope() -> None:
    resp = JobResponse(
        job_id="job_x",
        job_type=JobType.HIRING_REFRESH,
        status=JobStatus.SUCCEEDED,
        started_at=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        completed_at=datetime(2026, 5, 6, 16, 0, 30, tzinfo=UTC),
        outputs={"hiring_map_version": "hiring_v71"},
        metrics={"pairs_refreshed": 2},
    )
    assert resp.status is JobStatus.SUCCEEDED
    assert resp.error_code is None


def test_response_succeeded_with_warnings_requires_warnings() -> None:
    with pytest.raises(ValidationError):
        JobResponse(
            job_id="job_x",
            job_type=JobType.HIRING_REFRESH,
            status=JobStatus.SUCCEEDED_WITH_WARNINGS,
        )

    # With a warning present, validation should pass.
    resp = JobResponse(
        job_id="job_x",
        job_type=JobType.HIRING_REFRESH,
        status=JobStatus.SUCCEEDED_WITH_WARNINGS,
        warnings=[
            JobWarning(
                warning_code="LOW_CONFIDENCE_ENTRY_LEVEL",
                severity=WarningSeverity.LOW,
                message="entry-level recurrence uncertain",
            )
        ],
    )
    assert len(resp.warnings) == 1


def test_response_failed_requires_error_code_and_message() -> None:
    with pytest.raises(ValidationError):
        JobResponse(
            job_id="job_x",
            job_type=JobType.HIRING_REFRESH,
            status=JobStatus.FAILED,
        )

    with pytest.raises(ValidationError):
        JobResponse(
            job_id="job_x",
            job_type=JobType.HIRING_REFRESH,
            status=JobStatus.FAILED,
            error_code=ErrorCode.SOURCE_UNAVAILABLE,
            # missing error_message
        )

    resp = JobResponse(
        job_id="job_x",
        job_type=JobType.HIRING_REFRESH,
        status=JobStatus.FAILED,
        error_code=ErrorCode.SOURCE_UNAVAILABLE,
        error_message="hiring source 503",
        retry_recommended=True,
    )
    assert resp.error_code is ErrorCode.SOURCE_UNAVAILABLE
    assert resp.retry_recommended is True


def test_response_succeeded_must_not_carry_error_code() -> None:
    with pytest.raises(ValidationError):
        JobResponse(
            job_id="job_x",
            job_type=JobType.HIRING_REFRESH,
            status=JobStatus.SUCCEEDED,
            error_code=ErrorCode.TIMEOUT,
            error_message="leftover from earlier attempt",
        )


def test_response_completed_at_cannot_precede_started_at() -> None:
    started = datetime(2026, 5, 6, 16, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        JobResponse(
            job_id="job_x",
            job_type=JobType.HIRING_REFRESH,
            status=JobStatus.SUCCEEDED,
            started_at=started,
            completed_at=started - timedelta(seconds=1),
        )


def test_response_carries_downstream_trigger_recommendations() -> None:
    rec = DownstreamTriggerRecommendation(
        job_type=JobType.ENTRY_LEVEL_REFRESH,
        reason="Hiring records changed for 4 company-region pairs",
        scope={"company_region_pairs": [{"company_id": "comp_101", "region_id": "greater_boston"}]},
        priority=Priority.HIGH,
    )
    resp = JobResponse(
        job_id="job_x",
        job_type=JobType.HIRING_REFRESH,
        status=JobStatus.SUCCEEDED,
        downstream_trigger_recommendations=[rec],
    )
    dumped = resp.model_dump()
    assert dumped["downstream_trigger_recommendations"][0]["job_type"] == "entry_level_refresh"
    assert dumped["downstream_trigger_recommendations"][0]["priority"] == "high"
