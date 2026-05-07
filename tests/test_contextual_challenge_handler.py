"""Contextual challenge handler tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.orchestration.jobs.contextual_challenge_build import (
    handle_contextual_challenge_build,
)
from backend.orchestration.jobs.envelopes import JobRequest
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)
from backend.orchestration.workers.registry import default_registry
from backend.outputs.contextual_challenge import ContextualChallengeService
from backend.outputs.repository import OutputMetadataRepository
from backend.scoring.models import RegionMarketScore
from backend.scoring.repository import RegionScoreRepository


def _service(session: Session) -> ContextualChallengeService:
    return ContextualChallengeService(
        OutputMetadataRepository(session),
        session=session,
        region_repo=RegionRepository(session),
        score_repo=RegionScoreRepository(session),
    )


def _request(scope: dict | None = None, **overrides) -> JobRequest:
    payload = dict(
        job_id="job_contextual_001",
        job_type=JobType.CONTEXTUAL_CHALLENGE_BUILD,
        trigger_type=TriggerType.SCHEDULED,
        requested_by="system",
        priority=Priority.NORMAL,
        request_time=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        scope=scope or {"comparison_pairs": []},
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


def _seed_region(session: Session, region_id: str) -> None:
    session.add(
        Region(
            region_id=region_id,
            region_name=region_id,
            display_name=region_id.replace("_", " ").title(),
            region_type="greater_region",
        )
    )
    session.flush()


def _seed_score(
    session: Session,
    *,
    region_id: str,
    objective: float = 0.7,
    live: float = 0.5,
) -> None:
    session.add(
        RegionMarketScore(
            region_score_id=f"rms_{region_id}",
            region_id=region_id,
            objective_opportunity_score=objective,
            live_market_score=live,
            score_ruleset_version="marketscore_v1",
        )
    )
    session.flush()


# --- happy path -----------------------------------------------------------


def test_handler_builds_one_contextual_challenge(session: Session) -> None:
    _seed_region(session, "greater_boston")
    _seed_region(session, "greater_sf")
    _seed_score(session, region_id="greater_boston", objective=0.8, live=0.8)
    _seed_score(session, region_id="greater_sf", objective=0.4, live=0.4)

    response = handle_contextual_challenge_build(
        _request(
            scope={
                "comparison_pairs": [["greater_boston", "greater_sf"]]
            }
        ),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.SUCCEEDED
    assert response.error_code is None
    assert response.metrics["challenges_built"] == 1
    assert response.metrics["created_count"] == 1
    [entry] = response.outputs["contextual_challenges"]
    assert entry["challenge_status"] == "reinforced"
    assert entry["primary_winner_region_id"] == "greater_boston"
    assert entry["state"] == "fresh"


def test_handler_processes_multiple_pairs_and_unchanged_rebuilds(
    session: Session,
) -> None:
    for rid in ("greater_boston", "greater_sf", "greater_nyc"):
        _seed_region(session, rid)
    _seed_score(session, region_id="greater_boston", objective=0.8, live=0.8)
    _seed_score(session, region_id="greater_sf", objective=0.4, live=0.4)
    _seed_score(session, region_id="greater_nyc", objective=0.6, live=0.6)

    pairs = [
        ["greater_boston", "greater_sf"],
        ["greater_boston", "greater_nyc"],
    ]
    response_one = handle_contextual_challenge_build(
        _request(scope={"comparison_pairs": pairs}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response_one.status is JobStatus.SUCCEEDED
    assert response_one.metrics["created_count"] == 2

    response_two = handle_contextual_challenge_build(
        _request(scope={"comparison_pairs": pairs}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 2, tzinfo=UTC)),
    )
    assert response_two.metrics["unchanged_count"] == 2
    assert response_two.metrics["created_count"] == 0


# --- input validation -----------------------------------------------------


def test_handler_rejects_wrong_job_type(session: Session) -> None:
    response = handle_contextual_challenge_build(
        _request(job_type=JobType.HIRING_REFRESH),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_missing_comparison_pairs(session: Session) -> None:
    response = handle_contextual_challenge_build(
        _request(scope={"unrelated": "ok"}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_malformed_pair(session: Session) -> None:
    response = handle_contextual_challenge_build(
        _request(scope={"comparison_pairs": [["only_one"]]}),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_rejects_identical_regions_in_pair(session: Session) -> None:
    response = handle_contextual_challenge_build(
        _request(
            scope={
                "comparison_pairs": [["greater_boston", "greater_boston"]]
            }
        ),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INPUT_VALIDATION_ERROR


def test_handler_returns_integrity_failure_for_missing_region(
    session: Session,
) -> None:
    _seed_region(session, "greater_boston")
    response = handle_contextual_challenge_build(
        _request(
            scope={
                "comparison_pairs": [["greater_boston", "nope"]]
            }
        ),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INTEGRITY_CHECK_FAILED


# --- envelope correctness ------------------------------------------------


def test_handler_returns_valid_envelope(session: Session) -> None:
    _seed_region(session, "greater_boston")
    _seed_region(session, "greater_sf")
    _seed_score(session, region_id="greater_boston")
    _seed_score(session, region_id="greater_sf")
    response = handle_contextual_challenge_build(
        _request(
            scope={
                "comparison_pairs": [["greater_boston", "greater_sf"]]
            }
        ),
        _service(session),
        now=_ticking_clock(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    assert response.completed_at >= response.started_at
    assert response.error_code is None


# --- registry behavior ---------------------------------------------------


def test_contextual_challenge_handler_not_in_default_runtime() -> None:
    """Per the slice prompt, JobType.CONTEXTUAL_CHALLENGE_BUILD is
    intentionally not registered with Slice 14's default runtime. The
    handler is callable directly; auto-dispatch is deferred."""
    registry = default_registry()
    assert not registry.has(JobType.CONTEXTUAL_CHALLENGE_BUILD)
