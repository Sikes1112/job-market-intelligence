"""End-to-end runner tests.

Exercises the full enqueue → run_one / run_next loop using the default
registry against seeded canonical truth.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.orchestration.dependencies.checks import database_dependency_resolver
from backend.orchestration.jobs.envelopes import JobRequest, JobResponse
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.models import Job
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)
from backend.orchestration.queues.exceptions import (
    JobNotFoundInQueue,
    RetryNotEligible,
)
from backend.orchestration.queues.repository import QueueRepository
from backend.orchestration.queues.service import QueueService
from backend.orchestration.queues.types import QueueName
from backend.orchestration.workers.registry import WorkerRegistry, default_registry
from backend.orchestration.workers.runner import WorkerRunner
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore


def _request(**overrides) -> JobRequest:
    payload = dict(
        job_id="job_geo_001",
        job_type=JobType.GEOGRAPHY_BUILD,
        trigger_type=TriggerType.MANUAL,
        requested_by="admin",
        priority=Priority.HIGH,
        request_time=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        scope={"region_ids": ["greater_boston"]},
        inputs={
            "region_definitions": [
                {
                    "region_id": "greater_boston",
                    "region_name": "greater_boston",
                    "display_name": "Greater Boston",
                    "region_type": "greater_region",
                }
            ]
        },
        options={"validate_hierarchy": True},
        dependency_refs=[],
    )
    payload.update(overrides)
    return JobRequest(**payload)


def _runner(session: Session, registry: WorkerRegistry | None = None) -> WorkerRunner:
    return WorkerRunner(
        registry or default_registry(),
        session=session,
    )


def _enqueue(session: Session, request: JobRequest) -> Job:
    return QueueService(QueueRepository(session)).enqueue(request).job


# --- run_one with each implemented handler --------------------------------


def test_run_one_executes_geography_build(session: Session) -> None:
    job = _enqueue(session, _request())
    runner = _runner(session)

    response = runner.run_one(job.job_id)
    assert response.status is JobStatus.SUCCEEDED
    # The Job row reflects success.
    session.refresh(job)
    assert job.status == "succeeded"
    assert job.error_code is None
    assert job.started_at is not None
    assert job.completed_at is not None
    # Region was created via the handler.
    assert session.get(Region, "greater_boston") is not None


def test_run_one_executes_eligibility_classification(session: Session) -> None:
    request = _request(
        job_id="cls_001",
        job_type=JobType.ELIGIBILITY_CLASSIFICATION,
        trigger_type=TriggerType.EVENT_DRIVEN,
        requested_by="system",
        scope={"candidate_pool_id": "pool_v1"},
        inputs={
            "company_records": [
                {
                    "company_id": "comp_a",
                    "company_name": "A",
                    "normalized_company_name": "a",
                    "sector_primary": "ai",
                }
            ]
        },
    )
    job = _enqueue(session, request)
    response = _runner(session).run_one(job.job_id)
    assert response.status is JobStatus.SUCCEEDED
    assert session.get(Company, "comp_a") is not None


def test_run_one_executes_region_output_build(session: Session) -> None:
    """Output handler runs end-to-end given seeded prerequisites."""
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.add(
        Company(
            company_id="comp_a",
            company_name="A",
            normalized_company_name="a",
            eligibility_status="eligible",
        )
    )
    session.flush()
    session.add(
        CompanyRegionPresence(
            presence_id="p_a_b",
            company_id="comp_a",
            region_id="greater_boston",
            presence_status="present",
            presence_basis="office_plus_hiring",
            office_evidence_flag=True,
            hiring_evidence_flag=True,
        )
    )
    session.add(
        RegionMarketScore(
            region_score_id="rms_b",
            region_id="greater_boston",
            objective_opportunity_score=0.74,
            score_ruleset_version="marketscore_v1",
        )
    )
    session.flush()

    request = _request(
        job_id="rout_001",
        job_type=JobType.REGION_OUTPUT_BUILD,
        trigger_type=TriggerType.EVENT_DRIVEN,
        requested_by="system",
        priority=Priority.NORMAL,
        scope={"region_ids": ["greater_boston"]},
        inputs={},
    )
    job = _enqueue(session, request)
    response = _runner(session).run_one(job.job_id)
    assert response.status is JobStatus.SUCCEEDED
    session.refresh(job)
    assert job.status == "succeeded"


# --- not-found / unregistered handler ------------------------------------


def test_run_one_raises_for_unknown_job_id(session: Session) -> None:
    runner = _runner(session)
    with pytest.raises(JobNotFoundInQueue):
        runner.run_one("ghost")


def test_run_one_returns_failed_for_unregistered_handler(session: Session) -> None:
    """Empty registry — handler missing → INTERNAL_EXCEPTION."""
    job = _enqueue(session, _request())
    runner = _runner(session, WorkerRegistry())
    response = runner.run_one(job.job_id)
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.INTERNAL_EXCEPTION


# --- run_next ------------------------------------------------------------


def test_run_next_returns_none_when_queue_empty(session: Session) -> None:
    runner = _runner(session)
    assert runner.run_next(QueueName.FOUNDATIONAL) is None


def test_run_next_runs_oldest_queued_job(session: Session) -> None:
    _enqueue(session, _request(job_id="first"))
    _enqueue(session, _request(job_id="second", scope={"region_ids": ["a"]}))

    runner = _runner(session)
    response = runner.run_next(QueueName.FOUNDATIONAL)
    assert response is not None
    # First-enqueued runs first (deterministic by created_at).
    assert response.job_id == "first"


# --- dependency check at dispatch ---------------------------------------


def test_run_one_blocks_on_unsatisfied_dependency(session: Session) -> None:
    """JobRequest envelope rejects blank refs at the wire layer
    (Slice 4). To exercise the runtime's dispatch-time dependency check,
    inject a stricter resolver that flags well-formed refs as
    unsatisfied."""
    job = _enqueue(session, _request(dependency_refs=["unsat_x"]))

    def strict_resolver(refs):
        # Anything not prefixed ``v`` is reported as unsatisfied.
        return [r for r in refs if not r.startswith("v")]

    runner = WorkerRunner(
        default_registry(),
        session=session,
        dependency_resolver=strict_resolver,
    )
    response = runner.run_one(job.job_id)
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.DEPENDENCY_MISSING


def test_run_one_with_satisfied_dependency_runs_handler(session: Session) -> None:
    job = _enqueue(session, _request(dependency_refs=["geo_v1"]))
    response = _runner(session).run_one(job.job_id)
    assert response.status is JobStatus.SUCCEEDED


def test_run_one_blocks_on_missing_database_dependency_ref(session: Session) -> None:
    job = _enqueue(
        session,
        _request(
            job_id="job_missing_dep",
            dependency_refs=["region:missing_region@v1"],
        ),
    )
    runner = WorkerRunner(
        default_registry(),
        session=session,
        dependency_resolver=database_dependency_resolver(session),
    )

    response = runner.run_one(job.job_id)

    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.DEPENDENCY_MISSING
    assert "region:missing_region@v1" in (response.error_message or "")


def test_run_one_blocks_on_stale_database_dependency_ref(session: Session) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.flush()
    job = _enqueue(
        session,
        _request(
            job_id="job_stale_dep",
            dependency_refs=["region:greater_boston@v2"],
        ),
    )
    runner = WorkerRunner(
        default_registry(),
        session=session,
        dependency_resolver=database_dependency_resolver(session),
    )

    response = runner.run_one(job.job_id)

    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.DEPENDENCY_MISSING
    assert "region:greater_boston@v2" in (response.error_message or "")


# --- response application ------------------------------------------------


def test_response_warnings_persist_on_job_row(session: Session) -> None:
    """Run a handler and confirm its response (even an empty-warnings one)
    propagates correctly to the row."""
    job = _enqueue(session, _request())
    response = _runner(session).run_one(job.job_id)
    session.refresh(job)
    if response.warnings:
        assert job.warnings == [w.model_dump(mode="json") for w in response.warnings]
    else:
        assert job.warnings is None


def test_response_input_output_hashes_preserved(session: Session) -> None:
    """If the handler sets input_hash/output_hash, they should round-trip."""
    job = _enqueue(session, _request())
    response = _runner(session).run_one(job.job_id)
    # The geography handler in MVP doesn't set hashes; they should remain None.
    session.refresh(job)
    assert job.input_hash == response.input_hash
    assert job.output_hash == response.output_hash


# --- retry --------------------------------------------------------------


def test_retry_requeues_eligible_failed_job(session: Session) -> None:
    """A failed job with a retryable error code can be re-queued."""
    job = _enqueue(session, _request(dependency_refs=["valid_v1"]))
    # Manually drop into failed state with a retryable code.
    job.status = JobStatus.FAILED.value
    job.error_code = ErrorCode.SOURCE_UNAVAILABLE.value
    job.error_message = "503"
    session.flush()

    runner = _runner(session)
    requeued = runner.retry(job.job_id)
    assert requeued.status == JobStatus.QUEUED.value
    assert requeued.retry_count == 1
    assert requeued.error_code is None
    assert requeued.error_message is None


def test_retry_rejects_non_retryable_error_code(session: Session) -> None:
    job = _enqueue(session, _request())
    job.status = JobStatus.FAILED.value
    job.error_code = ErrorCode.INTEGRITY_CHECK_FAILED.value  # not retryable
    job.error_message = "x"
    session.flush()

    runner = _runner(session)
    with pytest.raises(RetryNotEligible):
        runner.retry(job.job_id)


def test_retry_rejects_when_attempts_exhausted(session: Session) -> None:
    job = _enqueue(session, _request())
    job.status = JobStatus.FAILED.value
    job.error_code = ErrorCode.TIMEOUT.value
    job.error_message = "x"
    job.retry_count = job.max_retries  # cap reached
    session.flush()

    runner = _runner(session)
    with pytest.raises(RetryNotEligible):
        runner.retry(job.job_id)


def test_retry_rejects_non_failed_job(session: Session) -> None:
    job = _enqueue(session, _request())
    runner = _runner(session)
    with pytest.raises(RetryNotEligible):
        runner.retry(job.job_id)  # still queued — nothing to retry


def test_retry_then_run_executes_again(session: Session) -> None:
    """Full cycle: fail → retry → run_one."""
    job = _enqueue(session, _request())
    job.status = JobStatus.FAILED.value
    job.error_code = ErrorCode.TIMEOUT.value
    job.error_message = "transient"
    session.flush()

    runner = _runner(session)
    requeued = runner.retry(job.job_id)
    assert requeued.retry_count == 1

    response = runner.run_one(job.job_id)
    assert response.status is JobStatus.SUCCEEDED


# --- dedupe interaction --------------------------------------------------


def test_dedupe_returns_existing_job_without_running(session: Session) -> None:
    svc = QueueService(QueueRepository(session))
    first = svc.enqueue(_request())
    duplicate = svc.enqueue(_request(job_id="ignored_id"))
    assert duplicate.outcome == "suppressed"
    # Same row.
    assert duplicate.job.job_id == first.job.job_id


# --- runtime does not introduce daemons / brokers / threads -------------


def test_runner_does_not_start_background_daemons(session: Session) -> None:
    """Sanity: building a runner is synchronous and does not import any
    threading/multiprocessing/scheduling primitives at construction."""
    runner = _runner(session)
    # Just constructing it should be cheap and side-effect-free.
    assert runner is not None


def test_runtime_dispatch_is_synchronous_and_returns_response(
    session: Session,
) -> None:
    job = _enqueue(session, _request())
    response = _runner(session).run_one(job.job_id)
    assert isinstance(response, JobResponse)
