from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.companies.classification import (
    DefaultEligibilityRule,
    DefaultMajorTechRule,
    Mag7List,
    MajorTechResult,
)
from backend.companies.repository import CompanyRepository
from backend.companies.service import CompanyService
from backend.orchestration.jobs.eligibility_classification import (
    handle_eligibility_classification,
)
from backend.orchestration.jobs.envelopes import JobRequest
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)


def _service(session: Session, *, mag7: Mag7List | None = None) -> CompanyService:
    return CompanyService(
        CompanyRepository(session),
        eligibility_rule=DefaultEligibilityRule(),
        major_tech_rule=DefaultMajorTechRule(),
        mag7_list=mag7 or Mag7List.default(),
    )


def _request(records: list[dict] | None = None, **overrides) -> JobRequest:
    payload = dict(
        job_id="job_classify_001",
        job_type=JobType.ELIGIBILITY_CLASSIFICATION,
        trigger_type=TriggerType.EVENT_DRIVEN,
        requested_by="system",
        priority=Priority.HIGH,
        request_time=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        scope={"candidate_pool_id": "candidate_pool_v45"},
        inputs={"company_records": records or []},
        options={"allow_override": True},
        dependency_refs=["candidate_pool_v45"],
    )
    payload.update(overrides)
    return JobRequest(**payload)


def _ticking_clock(start: datetime):
    counter = {"n": 0}

    def now() -> datetime:
        counter["n"] += 1
        return start + timedelta(seconds=counter["n"])

    return now


_AI_RECORD = {
    "company_id": "comp_101",
    "company_name": "Example AI",
    "normalized_company_name": "example ai",
    "sector_primary": "ai",
    "public_or_private": "private",
}
_BIOTECH_RECORD = {
    "company_id": "comp_bio",
    "company_name": "Bio Co",
    "normalized_company_name": "bio co",
    "sector_primary": "biotech",
}
_APPLE_RECORD = {
    "company_id": "comp_apple",
    "company_name": "Apple",
    "normalized_company_name": "apple",
    "sector_primary": "hardware",
}


def test_handler_succeeds_with_no_records(session: Session) -> None:
    response = handle_eligibility_classification(
        _request([]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs == {
        "company_results": [],
        "company_records_created": [],
        "company_records_updated": [],
        "company_records_unchanged": [],
    }
    assert response.metrics["created_count"] == 0


def test_handler_classifies_eligible_company(session: Session) -> None:
    svc = _service(session)
    response = handle_eligibility_classification(
        _request([_AI_RECORD]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs["company_records_created"] == ["comp_101"]
    result = response.outputs["company_results"][0]
    assert result["eligibility_status"] == "eligible"
    assert result["is_mag7"] is False
    assert result["classification_confidence"] == "high_confidence"

    # Persisted row reflects classification.
    company = svc.get_company("comp_101")
    assert company.eligibility_status == "eligible"
    assert company.state == "fresh"


def test_handler_classifies_mag7_company(session: Session) -> None:
    svc = _service(session)
    response = handle_eligibility_classification(
        _request([_APPLE_RECORD]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    result = response.outputs["company_results"][0]
    assert result["is_mag7"] is True
    assert result["is_major_tech"] is True
    assert result["eligibility_status"] == "eligible"


def test_handler_handles_override(session: Session) -> None:
    svc = _service(session)
    record = dict(
        _BIOTECH_RECORD,
        eligibility_override={"reason": "credible edge case", "decided_by": "admin"},
    )
    response = handle_eligibility_classification(
        _request([record]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    result = response.outputs["company_results"][0]
    assert result["eligibility_status"] == "override_included"
    assert result["eligibility_override_flag"] is True
    assert result["classification_confidence"] == "override_edge_case"


def test_handler_metrics_aggregate_across_records(session: Session) -> None:
    svc = _service(session)
    response = handle_eligibility_classification(
        _request([_AI_RECORD, _BIOTECH_RECORD, _APPLE_RECORD]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.metrics["created_count"] == 3
    assert response.metrics["eligible_count"] == 2  # ai + apple
    assert response.metrics["ineligible_count"] == 1  # biotech
    assert response.metrics["major_tech_count"] == 1  # apple


def test_handler_unchanged_on_re_run(session: Session) -> None:
    svc = _service(session)
    handle_eligibility_classification(
        _request([_AI_RECORD]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    response = handle_eligibility_classification(
        _request([_AI_RECORD]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 2, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs["company_records_unchanged"] == ["comp_101"]
    assert svc.get_company("comp_101").version == 1


def test_handler_rejects_malformed_inputs(session: Session) -> None:
    response = handle_eligibility_classification(
        _request([{"company_id": "x"}]),  # missing required fields
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_non_list_inputs(session: Session) -> None:
    req = _request().model_copy(update={"inputs": {"company_records": "nope"}})
    response = handle_eligibility_classification(
        req,
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_wrong_job_type(session: Session) -> None:
    response = handle_eligibility_classification(
        _request([], job_type=JobType.HIRING_REFRESH),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_returns_integrity_error_on_contradiction(session: Session) -> None:
    """Custom major-tech rule that returns is_major_tech=True even for non-Mag7
    companies in excluded sectors triggers the consistency validator."""

    class LiarRule:
        def evaluate(self, definition, *, is_mag7):
            return MajorTechResult(is_major_tech=True, score=1.0)

    svc = CompanyService(
        CompanyRepository(session),
        eligibility_rule=DefaultEligibilityRule(),
        major_tech_rule=LiarRule(),
        mag7_list=Mag7List.from_iterable([]),
    )
    response = handle_eligibility_classification(
        _request([_BIOTECH_RECORD]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INTEGRITY_CHECK_FAILED


def test_handler_returns_valid_envelope(session: Session) -> None:
    response = handle_eligibility_classification(
        _request([_AI_RECORD]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.error_code is None
    assert response.started_at is not None
    assert response.completed_at is not None
    assert response.completed_at >= response.started_at


def test_handler_does_not_run_a_queue(session: Session) -> None:
    """Sanity check: the handler returns synchronously without touching any
    queue/worker primitives."""
    response = handle_eligibility_classification(
        _request([_AI_RECORD]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
