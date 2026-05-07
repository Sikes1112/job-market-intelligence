from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.hiring.repository import HiringRepository
from backend.hiring.service import HiringService
from backend.orchestration.jobs.envelopes import JobRequest
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.hiring_refresh import handle_hiring_refresh
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)
from backend.presence.models import CompanyRegionPresence
from backend.presence.repository import PresenceRepository


def _seed(session: Session, *, presence_status: str = "present") -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Region(
                region_id="greater_sf",
                region_name="greater_sf",
                display_name="Greater SF",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_101",
                company_name="Example",
                normalized_company_name="example",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id="p1",
                company_id="comp_101",
                region_id="greater_boston",
                presence_status=presence_status,
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
            ),
            CompanyRegionPresence(
                presence_id="p2",
                company_id="comp_101",
                region_id="greater_sf",
                presence_status="present",
                presence_basis="office_plus_operations",
                office_evidence_flag=True,
                operations_evidence_flag=True,
            ),
        ]
    )
    session.flush()


def _service(session: Session) -> HiringService:
    return HiringService(
        HiringRepository(session),
        presence_repo=PresenceRepository(session),
    )


def _request(records: list[dict] | None = None, **overrides) -> JobRequest:
    payload = dict(
        job_id="job_hiring_001",
        job_type=JobType.HIRING_REFRESH,
        trigger_type=TriggerType.SCHEDULED,
        requested_by="system",
        priority=Priority.HIGH,
        request_time=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        scope={"region_ids": ["greater_boston"]},
        inputs={"hiring_records": records or []},
        options={},
        dependency_refs=["presence_v33"],
    )
    payload.update(overrides)
    return JobRequest(**payload)


def _record(
    hiring_id: str = "h1",
    *,
    company_id: str = "comp_101",
    region_id: str = "greater_boston",
    currently_hiring_flag: bool = True,
    active_posting_count_now: int | None = 12,
    role_family_summary: dict[str, int] | None = None,
) -> dict:
    snapshot: dict = {"currently_hiring_flag": currently_hiring_flag}
    if active_posting_count_now is not None:
        snapshot["active_posting_count_now"] = active_posting_count_now
    if role_family_summary is not None:
        snapshot["role_family_summary"] = role_family_summary
    return {
        "hiring_id": hiring_id,
        "company_id": company_id,
        "region_id": region_id,
        "snapshot": snapshot,
    }


def _ticking_clock(start: datetime):
    counter = {"n": 0}

    def now() -> datetime:
        counter["n"] += 1
        return start + timedelta(seconds=counter["n"])

    return now


def test_handler_succeeds_with_no_records(session: Session) -> None:
    _seed(session)
    response = handle_hiring_refresh(
        _request([]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.metrics["pairs_refreshed"] == 0


def test_handler_creates_hiring_record(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    response = handle_hiring_refresh(
        _request([_record()]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs["hiring_records_created"] == ["h1"]
    result = response.outputs["hiring_results"][0]
    assert result["currently_hiring_flag"] is True
    assert result["active_posting_count_now"] == 12


def test_handler_metrics_aggregate_changes_and_unchanged(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    handle_hiring_refresh(
        _request([_record()]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    response = handle_hiring_refresh(
        _request(
            [
                _record(),  # unchanged
                _record(
                    hiring_id="h2",
                    region_id="greater_sf",
                    active_posting_count_now=4,
                ),  # created
            ]
        ),
        svc,
        now=_ticking_clock(datetime(2026, 1, 2, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.metrics["pairs_refreshed"] == 2
    assert response.metrics["pairs_changed"] == 1
    assert response.metrics["pairs_unchanged"] == 1


def test_handler_unchanged_does_not_bump_version(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    handle_hiring_refresh(
        _request([_record()]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    response = handle_hiring_refresh(
        _request([_record()]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 2, tzinfo=UTC)),
    )
    assert response.outputs["hiring_records_unchanged"] == ["h1"]
    assert svc.get_hiring("h1").version == 1


def test_handler_rejects_missing_presence_pair(session: Session) -> None:
    _seed(session)
    response = handle_hiring_refresh(
        _request([_record(region_id="ghost_region")]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INTEGRITY_CHECK_FAILED


def test_handler_rejects_uncertain_pair(session: Session) -> None:
    _seed(session, presence_status="uncertain")
    response = handle_hiring_refresh(
        _request([_record()]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INTEGRITY_CHECK_FAILED


def test_handler_rejects_negative_count(session: Session) -> None:
    _seed(session)
    response = handle_hiring_refresh(
        _request([_record(active_posting_count_now=-1)]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_malformed_inputs(session: Session) -> None:
    _seed(session)
    response = handle_hiring_refresh(
        _request([{"hiring_id": "x"}]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_non_list_inputs(session: Session) -> None:
    _seed(session)
    req = _request().model_copy(update={"inputs": {"hiring_records": "nope"}})
    response = handle_hiring_refresh(
        req,
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_wrong_job_type(session: Session) -> None:
    _seed(session)
    response = handle_hiring_refresh(
        _request([], job_type=JobType.PRESENCE_MAPPING),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_returns_valid_envelope(session: Session) -> None:
    _seed(session)
    response = handle_hiring_refresh(
        _request([_record()]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.error_code is None
    assert response.completed_at >= response.started_at


def test_handler_does_not_run_a_queue(session: Session) -> None:
    _seed(session)
    response = handle_hiring_refresh(
        _request([_record()]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED


def test_handler_role_family_summary_round_trips(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    response = handle_hiring_refresh(
        _request(
            [_record(role_family_summary={"product": 3, "ai_cloud_adjacent": 5})]
        ),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    row = svc.get_hiring("h1")
    assert row.role_family_summary == {"product": 3, "ai_cloud_adjacent": 5}
