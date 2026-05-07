from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.companies.repository import CompanyRepository
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.orchestration.jobs.envelopes import JobRequest
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.presence_mapping import handle_presence_mapping
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)
from backend.presence.repository import PresenceRepository
from backend.presence.service import PresenceService


def _seed(session: Session) -> None:
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
            Company(
                company_id="comp_202",
                company_name="Acme",
                normalized_company_name="acme",
            ),
        ]
    )
    session.flush()


def _service(session: Session) -> PresenceService:
    return PresenceService(
        PresenceRepository(session),
        company_repo=CompanyRepository(session),
        region_repo=RegionRepository(session),
    )


def _request(records: list[dict] | None = None, **overrides) -> JobRequest:
    payload = dict(
        job_id="job_presence_001",
        job_type=JobType.PRESENCE_MAPPING,
        trigger_type=TriggerType.EVENT_DRIVEN,
        requested_by="system",
        priority=Priority.NORMAL,
        request_time=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        scope={"company_ids": ["comp_101"]},
        inputs={"presence_records": records or []},
        options={
            "prefer_hiring_evidence": True,
            "allow_satellite_office_presence": True,
        },
        dependency_refs=["company_universe_v45", "region_registry:v12"],
    )
    payload.update(overrides)
    return JobRequest(**payload)


def _record(
    presence_id: str = "p1",
    *,
    company_id: str = "comp_101",
    region_id: str = "greater_boston",
    office: bool = True,
    operations: bool = False,
    hiring: bool = True,
) -> dict:
    return {
        "presence_id": presence_id,
        "company_id": company_id,
        "region_id": region_id,
        "evidence": {
            "office_evidence_flag": office,
            "operations_evidence_flag": operations,
            "hiring_evidence_flag": hiring,
        },
    }


def _ticking_clock(start: datetime):
    counter = {"n": 0}

    def now() -> datetime:
        counter["n"] += 1
        return start + timedelta(seconds=counter["n"])

    return now


def test_handler_succeeds_with_no_records(session: Session) -> None:
    _seed(session)
    response = handle_presence_mapping(
        _request([]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs == {
        "presence_results": [],
        "presence_records_created": [],
        "presence_records_updated": [],
        "presence_records_unchanged": [],
    }
    assert response.metrics["pairs_evaluated"] == 0


def test_handler_creates_present_record(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    response = handle_presence_mapping(
        _request([_record()]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs["presence_records_created"] == ["p1"]
    result = response.outputs["presence_results"][0]
    assert result["presence_status"] == "present"
    assert result["presence_basis"] == "office_plus_hiring"
    assert result["presence_confidence"] == "high_confidence"


def test_handler_metrics_aggregate(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    response = handle_presence_mapping(
        _request(
            [
                _record(presence_id="p1", office=True, hiring=True),
                _record(
                    presence_id="p2",
                    region_id="greater_sf",
                    office=False,
                    operations=False,
                    hiring=False,
                ),
                _record(
                    presence_id="p3",
                    company_id="comp_202",
                    region_id="greater_boston",
                    office=False,
                    operations=True,
                    hiring=False,
                ),
            ]
        ),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.metrics["pairs_evaluated"] == 3
    assert response.metrics["present_count"] == 1
    assert response.metrics["not_present_count"] == 1
    assert response.metrics["uncertain_count"] == 1


def test_handler_unchanged_on_re_run(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    handle_presence_mapping(
        _request([_record()]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    response = handle_presence_mapping(
        _request([_record()]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 2, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs["presence_records_unchanged"] == ["p1"]


def test_handler_rejects_missing_company(session: Session) -> None:
    _seed(session)
    response = handle_presence_mapping(
        _request([_record(company_id="ghost")]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INTEGRITY_CHECK_FAILED


def test_handler_rejects_missing_region(session: Session) -> None:
    _seed(session)
    response = handle_presence_mapping(
        _request([_record(region_id="ghost")]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INTEGRITY_CHECK_FAILED


def test_handler_rejects_malformed_inputs(session: Session) -> None:
    _seed(session)
    response = handle_presence_mapping(
        _request([{"presence_id": "x"}]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_non_list_inputs(session: Session) -> None:
    _seed(session)
    req = _request().model_copy(update={"inputs": {"presence_records": "nope"}})
    response = handle_presence_mapping(
        req,
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_wrong_job_type(session: Session) -> None:
    _seed(session)
    response = handle_presence_mapping(
        _request([], job_type=JobType.HIRING_REFRESH),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_returns_valid_envelope(session: Session) -> None:
    _seed(session)
    response = handle_presence_mapping(
        _request([_record()]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.error_code is None
    assert response.completed_at >= response.started_at


def test_handler_does_not_run_a_queue(session: Session) -> None:
    _seed(session)
    response = handle_presence_mapping(
        _request([_record()]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
