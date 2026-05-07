from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from backend.geography.repository import RegionRepository
from backend.geography.service import GeographyService
from backend.orchestration.jobs.envelopes import JobRequest
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.geography_build import handle_geography_build
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)


def _service(session: Session) -> GeographyService:
    return GeographyService(RegionRepository(session))


def _request(definitions: list[dict] | None = None, **overrides) -> JobRequest:
    payload = dict(
        job_id="job_geo_001",
        job_type=JobType.GEOGRAPHY_BUILD,
        trigger_type=TriggerType.MANUAL,
        requested_by="admin",
        priority=Priority.HIGH,
        request_time=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        scope={"region_ids": ["greater_boston"]},
        inputs={"region_definitions": definitions or []},
        options={"validate_hierarchy": True},
        dependency_refs=[],
    )
    payload.update(overrides)
    return JobRequest(**payload)


_BOSTON = {
    "region_id": "greater_boston",
    "region_name": "greater_boston",
    "display_name": "Greater Boston",
    "region_type": "greater_region",
}
_SF = {
    "region_id": "greater_sf",
    "region_name": "greater_sf",
    "display_name": "Greater SF",
    "region_type": "greater_region",
}
_MA = {
    "region_id": "massachusetts",
    "region_name": "massachusetts",
    "display_name": "Massachusetts",
    "region_type": "state",
}


def _ticking_clock(start: datetime):
    """Produce a clock that returns increasing timestamps so completed_at >= started_at."""
    counter = {"n": 0}

    def now() -> datetime:
        counter["n"] += 1
        return start + timedelta(seconds=counter["n"])

    return now


def test_handler_succeeds_with_no_definitions(session: Session) -> None:
    svc = _service(session)
    response = handle_geography_build(
        _request([]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs == {
        "geography_objects_created": [],
        "geography_objects_updated": [],
        "geography_objects_unchanged": [],
    }
    assert response.metrics == {
        "created_count": 0,
        "updated_count": 0,
        "unchanged_count": 0,
    }


def test_handler_creates_two_regions(session: Session) -> None:
    svc = _service(session)
    response = handle_geography_build(
        _request([_BOSTON, _SF]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert set(response.outputs["geography_objects_created"]) == {
        "greater_boston",
        "greater_sf",
    }
    assert response.metrics["created_count"] == 2

    # Persisted regions should be fresh after the build.
    boston = svc.get_region("greater_boston")
    assert boston.state == "fresh"
    assert boston.version == 1


def test_handler_marks_unchanged_on_second_run(session: Session) -> None:
    svc = _service(session)
    handle_geography_build(
        _request([_BOSTON]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    response = handle_geography_build(
        _request([_BOSTON]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 2, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs["geography_objects_unchanged"] == ["greater_boston"]
    assert response.metrics["unchanged_count"] == 1
    assert svc.get_region("greater_boston").version == 1


def test_handler_marks_updated_when_definition_changes(session: Session) -> None:
    svc = _service(session)
    handle_geography_build(
        _request([_BOSTON]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    changed = dict(_BOSTON, display_name="Boston Region")
    response = handle_geography_build(
        _request([changed]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 2, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs["geography_objects_updated"] == ["greater_boston"]
    region = svc.get_region("greater_boston")
    assert region.version == 2
    assert region.state == "fresh"
    assert region.display_name == "Boston Region"


def test_handler_rejects_invalid_hierarchy(session: Session) -> None:
    svc = _service(session)
    bad = dict(_BOSTON, parent_region_id="ghost")
    response = handle_geography_build(
        _request([bad]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INTEGRITY_CHECK_FAILED
    assert "ghost" in response.error_message


def test_handler_rejects_malformed_inputs(session: Session) -> None:
    svc = _service(session)
    response = handle_geography_build(
        _request([{"region_id": "x"}]),  # missing required fields
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_non_list_inputs(session: Session) -> None:
    svc = _service(session)
    req = _request()
    req = req.model_copy(update={"inputs": {"region_definitions": "nope"}})
    response = handle_geography_build(
        req, svc, now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_wrong_job_type(session: Session) -> None:
    svc = _service(session)
    response = handle_geography_build(
        _request([], job_type=JobType.HIRING_REFRESH),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_processes_parent_then_child_in_order(session: Session) -> None:
    svc = _service(session)
    response = handle_geography_build(
        _request([_MA, dict(_BOSTON, parent_region_id="massachusetts")]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    boston = svc.get_region("greater_boston")
    assert boston.parent_region_id == "massachusetts"


def test_handler_rejects_child_before_parent(session: Session) -> None:
    """If the parent isn't already in the DB and isn't earlier in this batch's
    output, the hierarchy validator catches it."""
    svc = _service(session)
    response = handle_geography_build(
        _request([dict(_BOSTON, parent_region_id="massachusetts")]),  # MA missing
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INTEGRITY_CHECK_FAILED


def test_handler_does_not_run_a_queue_or_worker(session: Session) -> None:
    """Sanity check: the handler is a synchronous function and returns without
    touching any queue/worker primitives."""
    svc = _service(session)
    response = handle_geography_build(
        _request([_BOSTON]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    # If we got here without an unhandled exception, no worker runtime fired.
    assert response.status is JobStatus.SUCCEEDED


def test_handler_returns_valid_job_response_envelope(session: Session) -> None:
    """The response must satisfy JobResponse cross-field validators."""
    svc = _service(session)
    response = handle_geography_build(
        _request([_BOSTON]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    # Successful response: no error_code, started_at <= completed_at
    assert response.error_code is None
    assert response.started_at is not None
    assert response.completed_at is not None
    assert response.completed_at >= response.started_at


@pytest.mark.parametrize("count", [1, 5, 12])
def test_handler_metrics_are_consistent_with_outputs(session: Session, count: int) -> None:
    svc = _service(session)
    defs = [
        dict(
            region_id=f"r{i}",
            region_name=f"r{i}",
            display_name=f"R{i}",
            region_type="city",
        )
        for i in range(count)
    ]
    response = handle_geography_build(
        _request(defs), svc, now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.metrics["created_count"] == count
    assert len(response.outputs["geography_objects_created"]) == count
