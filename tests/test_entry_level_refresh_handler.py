from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.repository import EntryLevelRepository
from backend.entry_level.service import EntryLevelService
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.hiring.repository import HiringRepository
from backend.orchestration.jobs.entry_level_refresh import (
    handle_entry_level_refresh,
)
from backend.orchestration.jobs.envelopes import JobRequest
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)


def _seed(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
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
    session.add(
        CompanyRegionHiring(
            hiring_id="h1",
            company_id="comp_101",
            region_id="greater_boston",
        )
    )
    session.flush()


def _service(session: Session) -> EntryLevelService:
    return EntryLevelService(
        EntryLevelRepository(session),
        hiring_repo=HiringRepository(session),
    )


def _request(records: list[dict] | None = None, **overrides) -> JobRequest:
    payload = dict(
        job_id="job_entry_001",
        job_type=JobType.ENTRY_LEVEL_REFRESH,
        trigger_type=TriggerType.EVENT_DRIVEN,
        requested_by="system",
        priority=Priority.HIGH,
        request_time=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        scope={"company_region_pairs": [{"company_id": "comp_101", "region_id": "greater_boston"}]},
        inputs={"entry_level_records": records or []},
        options={},
        dependency_refs=["hiring_v71"],
    )
    payload.update(overrides)
    return JobRequest(**payload)


def _record(
    entry_level_id: str = "e1",
    *,
    company_id: str = "comp_101",
    region_id: str = "greater_boston",
    internship_count: int | None = 3,
    coop_count: int | None = 2,
    entry_level_full_time_count: int | None = 4,
    formal_early_career_program_flag: bool = True,
    student_season_recurrence_signal: str | None = "strong",
) -> dict:
    snapshot: dict = {
        "formal_early_career_program_flag": formal_early_career_program_flag,
    }
    if internship_count is not None:
        snapshot["internship_count"] = internship_count
    if coop_count is not None:
        snapshot["coop_count"] = coop_count
    if entry_level_full_time_count is not None:
        snapshot["entry_level_full_time_count"] = entry_level_full_time_count
    if student_season_recurrence_signal is not None:
        snapshot["student_season_recurrence_signal"] = student_season_recurrence_signal
    return {
        "entry_level_id": entry_level_id,
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
    response = handle_entry_level_refresh(
        _request([]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.metrics["pairs_evaluated"] == 0


def test_handler_creates_entry_level_record(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    response = handle_entry_level_refresh(
        _request([_record()]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs["entry_level_records_created"] == ["e1"]
    result = response.outputs["entry_level_results"][0]
    assert result["internship_count"] == 3
    assert result["coop_count"] == 2
    assert result["entry_level_access_score"] is not None
    assert 0.0 <= result["entry_level_access_score"] <= 1.0


def test_handler_unchanged_does_not_bump_version(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    handle_entry_level_refresh(
        _request([_record()]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    response = handle_entry_level_refresh(
        _request([_record()]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 2, tzinfo=UTC)),
    )
    assert response.outputs["entry_level_records_unchanged"] == ["e1"]
    assert svc.get_entry_level("e1").version == 1


def test_handler_metrics_count_pairs_with_access(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    response = handle_entry_level_refresh(
        _request(
            [
                _record(
                    entry_level_id="e1",
                    internship_count=3,
                    coop_count=2,
                    entry_level_full_time_count=4,
                ),
            ]
        ),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.metrics["pairs_evaluated"] == 1
    assert response.metrics["pairs_with_entry_level_access"] == 1


def test_handler_rejects_missing_hiring_record(session: Session) -> None:
    _seed(session)
    response = handle_entry_level_refresh(
        _request([_record(region_id="ghost_region")]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INTEGRITY_CHECK_FAILED


def test_handler_rejects_negative_count(session: Session) -> None:
    _seed(session)
    response = handle_entry_level_refresh(
        _request([_record(internship_count=-1)]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_malformed_inputs(session: Session) -> None:
    _seed(session)
    response = handle_entry_level_refresh(
        _request([{"entry_level_id": "x"}]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_non_list_inputs(session: Session) -> None:
    _seed(session)
    req = _request().model_copy(update={"inputs": {"entry_level_records": "nope"}})
    response = handle_entry_level_refresh(
        req,
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_wrong_job_type(session: Session) -> None:
    _seed(session)
    response = handle_entry_level_refresh(
        _request([], job_type=JobType.HIRING_REFRESH),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_returns_valid_envelope(session: Session) -> None:
    _seed(session)
    response = handle_entry_level_refresh(
        _request([_record()]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.error_code is None
    assert response.completed_at >= response.started_at


def test_handler_does_not_run_a_queue(session: Session) -> None:
    _seed(session)
    response = handle_entry_level_refresh(
        _request([_record()]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED


def test_handler_partial_counts_persist_with_low_confidence(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    response = handle_entry_level_refresh(
        _request(
            [
                _record(
                    coop_count=None,
                    student_season_recurrence_signal=None,
                )
            ]
        ),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    result = response.outputs["entry_level_results"][0]
    assert result["coop_count"] is None
    assert result["entry_level_confidence"] == "low_confidence"
