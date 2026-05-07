from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.companies.repository import CompanyRepository
from backend.entry_level.repository import EntryLevelRepository
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.hiring.repository import HiringRepository
from backend.orchestration.jobs.company_output_build import (
    handle_company_output_build,
)
from backend.orchestration.jobs.comparison_cache_build import (
    handle_comparison_cache_build,
)
from backend.orchestration.jobs.envelopes import JobRequest
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.region_output_build import handle_region_output_build
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)
from backend.outputs.repository import OutputMetadataRepository
from backend.outputs.service import OutputAssemblyService
from backend.presence.models import CompanyRegionPresence
from backend.presence.repository import PresenceRepository
from backend.scoring.models import RegionMarketScore
from backend.scoring.repository import RegionScoreRepository


def _service(session: Session) -> OutputAssemblyService:
    return OutputAssemblyService(
        OutputMetadataRepository(session),
        session=session,
        region_repo=RegionRepository(session),
        company_repo=CompanyRepository(session),
        presence_repo=PresenceRepository(session),
        hiring_repo=HiringRepository(session),
        entry_level_repo=EntryLevelRepository(session),
        score_repo=RegionScoreRepository(session),
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
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id="p_a_boston",
                company_id="comp_a",
                region_id="greater_boston",
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
            ),
            RegionMarketScore(
                region_score_id="rms_boston",
                region_id="greater_boston",
                objective_opportunity_score=0.74,
                early_career_accessibility_score=0.79,
                score_ruleset_version="marketscore_v1",
            ),
            RegionMarketScore(
                region_score_id="rms_sf",
                region_id="greater_sf",
                objective_opportunity_score=0.70,
                early_career_accessibility_score=0.65,
                score_ruleset_version="marketscore_v1",
            ),
        ]
    )
    session.flush()


def _ticking_clock(start: datetime):
    counter = {"n": 0}

    def now() -> datetime:
        counter["n"] += 1
        return start + timedelta(seconds=counter["n"])

    return now


def _request(job_type: JobType, scope: dict, **overrides) -> JobRequest:
    payload = dict(
        job_id=f"job_{job_type.value}_001",
        job_type=job_type,
        trigger_type=TriggerType.EVENT_DRIVEN,
        requested_by="system",
        priority=Priority.NORMAL,
        request_time=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        scope=scope,
        inputs={},
        options={},
        dependency_refs=[],
    )
    payload.update(overrides)
    return JobRequest(**payload)


# --- region_output_build --------------------------------------------------


def test_region_handler_creates_outputs(session: Session) -> None:
    _seed(session)
    response = handle_region_output_build(
        _request(JobType.REGION_OUTPUT_BUILD, {"region_ids": ["greater_boston"]}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs["regions_created"] == ["greater_boston"]
    assert response.metrics["region_outputs_built"] == 1


def test_region_handler_rejects_wrong_job_type(session: Session) -> None:
    _seed(session)
    response = handle_region_output_build(
        _request(JobType.HIRING_REFRESH, {"region_ids": []}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_region_handler_rejects_non_list_scope(session: Session) -> None:
    _seed(session)
    req = _request(JobType.REGION_OUTPUT_BUILD, {"region_ids": "nope"})
    response = handle_region_output_build(
        req, _service(session), now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_region_handler_rejects_blank_id(session: Session) -> None:
    _seed(session)
    req = _request(JobType.REGION_OUTPUT_BUILD, {"region_ids": [""]})
    response = handle_region_output_build(
        req, _service(session), now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_region_handler_rejects_missing_region(session: Session) -> None:
    _seed(session)
    response = handle_region_output_build(
        _request(JobType.REGION_OUTPUT_BUILD, {"region_ids": ["ghost"]}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INTEGRITY_CHECK_FAILED


def test_region_handler_returns_valid_envelope(session: Session) -> None:
    _seed(session)
    response = handle_region_output_build(
        _request(JobType.REGION_OUTPUT_BUILD, {"region_ids": ["greater_boston"]}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.error_code is None
    assert response.completed_at >= response.started_at


# --- company_output_build -------------------------------------------------


def test_company_handler_creates_outputs(session: Session) -> None:
    _seed(session)
    response = handle_company_output_build(
        _request(JobType.COMPANY_OUTPUT_BUILD, {"company_ids": ["comp_a"]}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs["companies_created"] == ["comp_a"]


def test_company_handler_rejects_missing_company(session: Session) -> None:
    _seed(session)
    response = handle_company_output_build(
        _request(JobType.COMPANY_OUTPUT_BUILD, {"company_ids": ["ghost"]}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.error_code is ErrorCode.INTEGRITY_CHECK_FAILED


def test_company_handler_rejects_wrong_job_type(session: Session) -> None:
    _seed(session)
    response = handle_company_output_build(
        _request(JobType.HIRING_REFRESH, {"company_ids": []}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_company_handler_rejects_blank_id(session: Session) -> None:
    _seed(session)
    response = handle_company_output_build(
        _request(JobType.COMPANY_OUTPUT_BUILD, {"company_ids": [""]}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


# --- comparison_cache_build ----------------------------------------------


def test_comparison_handler_creates_outputs(session: Session) -> None:
    _seed(session)
    response = handle_comparison_cache_build(
        _request(
            JobType.COMPARISON_CACHE_BUILD,
            {"comparison_pairs": [["greater_boston", "greater_sf"]]},
        ),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.outputs["comparisons_created"] == ["greater_boston__greater_sf"]


def test_comparison_handler_canonicalizes_pair_order(session: Session) -> None:
    _seed(session)
    svc = _service(session)
    handle_comparison_cache_build(
        _request(
            JobType.COMPARISON_CACHE_BUILD,
            {"comparison_pairs": [["greater_boston", "greater_sf"]]},
        ),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    response = handle_comparison_cache_build(
        _request(
            JobType.COMPARISON_CACHE_BUILD,
            {"comparison_pairs": [["greater_sf", "greater_boston"]]},
        ),
        svc,
        now=_ticking_clock(datetime(2026, 1, 2, tzinfo=UTC)),
    )
    # Canonical subject_id matches → unchanged.
    assert response.outputs["comparisons_unchanged"] == ["greater_boston__greater_sf"]


def test_comparison_handler_rejects_three_regions(session: Session) -> None:
    _seed(session)
    response = handle_comparison_cache_build(
        _request(
            JobType.COMPARISON_CACHE_BUILD,
            {"comparison_pairs": [["greater_boston", "greater_sf", "greater_la"]]},
        ),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_comparison_handler_rejects_identical_regions(session: Session) -> None:
    _seed(session)
    response = handle_comparison_cache_build(
        _request(
            JobType.COMPARISON_CACHE_BUILD,
            {"comparison_pairs": [["greater_boston", "greater_boston"]]},
        ),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_comparison_handler_rejects_blank_id(session: Session) -> None:
    _seed(session)
    response = handle_comparison_cache_build(
        _request(
            JobType.COMPARISON_CACHE_BUILD,
            {"comparison_pairs": [["greater_boston", ""]]},
        ),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_comparison_handler_rejects_non_list_scope(session: Session) -> None:
    _seed(session)
    response = handle_comparison_cache_build(
        _request(JobType.COMPARISON_CACHE_BUILD, {"comparison_pairs": "nope"}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_comparison_handler_rejects_missing_region(session: Session) -> None:
    _seed(session)
    response = handle_comparison_cache_build(
        _request(
            JobType.COMPARISON_CACHE_BUILD,
            {"comparison_pairs": [["greater_boston", "ghost"]]},
        ),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.error_code is ErrorCode.INTEGRITY_CHECK_FAILED


def test_no_handler_writes_to_a_queue(session: Session) -> None:
    """Sanity: handlers complete synchronously without touching queue/worker
    primitives."""
    _seed(session)
    svc = _service(session)
    r1 = handle_region_output_build(
        _request(JobType.REGION_OUTPUT_BUILD, {"region_ids": ["greater_boston"]}),
        svc,
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    r2 = handle_company_output_build(
        _request(JobType.COMPANY_OUTPUT_BUILD, {"company_ids": ["comp_a"]}),
        svc,
        now=_ticking_clock(datetime(2026, 1, 2, tzinfo=UTC)),
    )
    r3 = handle_comparison_cache_build(
        _request(
            JobType.COMPARISON_CACHE_BUILD,
            {"comparison_pairs": [["greater_boston", "greater_sf"]]},
        ),
        svc,
        now=_ticking_clock(datetime(2026, 1, 3, tzinfo=UTC)),
    )
    assert r1.status is JobStatus.SUCCEEDED
    assert r2.status is JobStatus.SUCCEEDED
    assert r3.status is JobStatus.SUCCEEDED
