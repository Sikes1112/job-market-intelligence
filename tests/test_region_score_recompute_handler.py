from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.orchestration.jobs.envelopes import JobRequest
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.region_score_recompute import (
    handle_region_score_recompute,
)
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)
from backend.presence.models import CompanyRegionPresence
from backend.scoring.repository import RegionScoreRepository
from backend.scoring.service import RegionScoringService


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
                company_id="comp_a",
                company_name="A",
                normalized_company_name="a",
                eligibility_status="eligible",
                is_major_tech=True,
                prestige_score=0.6,
            ),
        ]
    )
    session.flush()
    session.add(
        CompanyRegionPresence(
            presence_id="p_a_boston",
            company_id="comp_a",
            region_id="greater_boston",
            presence_status="present",
            presence_basis="office_plus_hiring",
            office_evidence_flag=True,
            hiring_evidence_flag=True,
        )
    )
    session.flush()


def _service(session: Session) -> RegionScoringService:
    return RegionScoringService(
        RegionScoreRepository(session),
        region_repo=RegionRepository(session),
    )


def _request(region_ids: list[str] | None = None, **overrides) -> JobRequest:
    payload = dict(
        job_id="job_score_001",
        job_type=JobType.REGION_SCORE_RECOMPUTE,
        trigger_type=TriggerType.EVENT_DRIVEN,
        requested_by="system",
        priority=Priority.HIGH,
        request_time=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        scope={"region_ids": region_ids if region_ids is not None else []},
        inputs={},
        options={},
        dependency_refs=[],
    )
    payload.update(overrides)
    return JobRequest(**payload)


def _ticking_clock(start: datetime):
    counter = {"n": 0}

    def now() -> datetime:
        counter["n"] += 1
        return start + timedelta(seconds=counter["n"])

    return now


def test_handler_succeeds_with_no_regions(session: Session) -> None:
    _seed(session)
    response = handle_region_score_recompute(
        _request([]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.metrics["regions_recomputed"] == 0


def test_handler_creates_score_row(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    response = handle_region_score_recompute(
        _request(["greater_boston"]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs["regions_created"] == ["greater_boston"]
    result = response.outputs["region_scores"][0]
    assert result["state"] == "fresh"
    assert result["score_ruleset_version"] == "marketscore_v1"
    assert result["structural_ecosystem_score"] is not None
    assert result["raw_total_score"] is not None
    assert result["general_density_score"] is not None
    assert result["tech_market_density_score"] is not None
    # No hiring or entry-level rows were seeded, so those score inputs are
    # unknown/not-collected rather than forced to numeric zero.
    assert result["live_market_score"] is None
    # Objective can still be computed from the known prestige input; missing
    # live/entry-level inputs are omitted rather than zeroed.
    assert result["objective_opportunity_score"] == 0.6
    assert result["early_career_accessibility_score"] is None


def test_handler_unchanged_does_not_bump_version(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    handle_region_score_recompute(
        _request(["greater_boston"]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    response = handle_region_score_recompute(
        _request(["greater_boston"]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 2, tzinfo=UTC)),
    )
    assert response.outputs["regions_unchanged"] == ["greater_boston"]
    assert svc.get_score_by_region("greater_boston").version == 1


def test_handler_metrics_aggregate(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    response = handle_region_score_recompute(
        _request(["greater_boston", "greater_sf"]),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.metrics["regions_recomputed"] == 2
    assert response.metrics["created_count"] == 2


def test_handler_rejects_missing_region(session: Session) -> None:
    _seed(session)
    response = handle_region_score_recompute(
        _request(["ghost"]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INTEGRITY_CHECK_FAILED


def test_handler_rejects_non_list_scope(session: Session) -> None:
    _seed(session)
    req = _request().model_copy(update={"scope": {"region_ids": "nope"}})
    response = handle_region_score_recompute(
        req,
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_blank_region_id(session: Session) -> None:
    _seed(session)
    req = _request().model_copy(update={"scope": {"region_ids": [""]}})
    response = handle_region_score_recompute(
        req,
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_wrong_job_type(session: Session) -> None:
    _seed(session)
    response = handle_region_score_recompute(
        _request([], job_type=JobType.HIRING_REFRESH),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_returns_valid_envelope(session: Session) -> None:
    _seed(session)
    response = handle_region_score_recompute(
        _request(["greater_boston"]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.error_code is None
    assert response.completed_at >= response.started_at


def test_handler_does_not_run_a_queue(session: Session) -> None:
    _seed(session)
    response = handle_region_score_recompute(
        _request(["greater_boston"]),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
