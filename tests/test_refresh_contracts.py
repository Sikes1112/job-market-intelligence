from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from backend.refresh.contracts import (
    REFRESH_JOB_CONTRACTS,
    RefreshOperationKind,
    contracts_requiring_source_preservation,
)
from backend.refresh.job_types import REQUIRED_REFRESH_JOB_TYPES, RefreshJobType
from backend.refresh.queue_decision import SELECTED_QUEUE_DECISION, QueueBackend
from backend.refresh.status import (
    RefreshJobStatus,
    RefreshJobStatusRecord,
    summarize_refresh_observability,
)


def test_refresh_job_type_vocabulary_is_explicit_and_stable() -> None:
    assert RefreshJobType.values() == {
        "company_universe_refresh",
        "presence_refresh",
        "hiring_refresh",
        "entry_level_refresh",
        "score_recompute",
        "output_rebuild",
        "audit_run",
    }
    assert REQUIRED_REFRESH_JOB_TYPES == frozenset(RefreshJobType)
    assert frozenset(REFRESH_JOB_CONTRACTS) == REQUIRED_REFRESH_JOB_TYPES


def test_queue_decision_selects_external_redis_worker_posture() -> None:
    decision = SELECTED_QUEUE_DECISION

    assert decision.selected_backend is QueueBackend.RQ_REDIS
    assert decision.broker == "redis"
    assert decision.external_process_compatible is True
    assert decision.production_queue_is_in_process is False
    assert decision.imports_runtime_client is False


def test_queue_decision_rejects_kafka_as_overbuilt() -> None:
    decision = SELECTED_QUEUE_DECISION

    kafka = [
        option for option in decision.rejected_options if option.backend is QueueBackend.KAFKA
    ]
    assert kafka
    assert "streaming platform" in kafka[0].reason
    assert decision.rejects_kafka is True


def test_refresh_contracts_do_not_take_over_authoritative_domain_policy() -> None:
    for contract in REFRESH_JOB_CONTRACTS.values():
        assert contract.boundary.queue_owns_scoring_policy is False
        assert contract.boundary.queue_owns_ingestion_truth is False
        assert contract.boundary.queue_owns_source_freshness_rules is False
        assert contract.boundary.queue_owns_output_semantics is False


def test_source_version_preservation_required_for_data_score_and_output_writers() -> None:
    writer_contracts = {
        contract.job_type
        for contract in REFRESH_JOB_CONTRACTS.values()
        if contract.operation_kind
        in {
            RefreshOperationKind.SOURCE_DATA_REFRESH,
            RefreshOperationKind.DERIVED_DATA_RECOMPUTE,
            RefreshOperationKind.OUTPUT_REBUILD,
        }
    }

    assert writer_contracts == REQUIRED_REFRESH_JOB_TYPES - {RefreshJobType.AUDIT_RUN}
    assert {
        contract.job_type for contract in contracts_requiring_source_preservation()
    } == writer_contracts
    for job_type in writer_contracts:
        contract = REFRESH_JOB_CONTRACTS[job_type]
        assert contract.source_preservation.source_version_refs_required is True
        assert contract.source_preservation.source_bundle_ref_required is True


def test_audit_contract_is_observational_not_a_refresh_writer() -> None:
    contract = REFRESH_JOB_CONTRACTS[RefreshJobType.AUDIT_RUN]

    assert contract.operation_kind is RefreshOperationKind.AUDIT
    assert contract.requires_source_preservation is False


def test_status_record_supports_failure_retry_duration_and_source_refs() -> None:
    enqueued = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    started = enqueued + timedelta(seconds=5)
    finished = started + timedelta(seconds=42)

    record = RefreshJobStatusRecord(
        stable_job_key="hiring_refresh:greater_boston",
        job_id="rq-job-123",
        job_type=RefreshJobType.HIRING_REFRESH,
        target_scope={"region_id": "greater_boston"},
        target_id="greater_boston",
        status=RefreshJobStatus.FAILED,
        enqueued_at=enqueued,
        started_at=started,
        finished_at=finished,
        failure_reason="source timeout",
        retry_count=2,
        source_version_refs=("hiring:greater_boston@v7",),
        source_version_bundle_ref="source_version_bundle:hiring:greater_boston:v7",
        stale_output_count=3,
    )

    assert record.duration_seconds == 42
    assert record.failure_reason == "source timeout"
    assert record.retry_count == 2
    assert record.source_version_refs == ("hiring:greater_boston@v7",)
    assert (
        record.source_version_bundle_ref
        == "source_version_bundle:hiring:greater_boston:v7"
    )
    assert record.stale_output_count == 3


def test_failed_status_requires_failure_reason() -> None:
    with pytest.raises(ValidationError, match="failure_reason"):
        RefreshJobStatusRecord(
            stable_job_key="presence_refresh:company_a",
            job_type=RefreshJobType.PRESENCE_REFRESH,
            status=RefreshJobStatus.FAILED,
            enqueued_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
        )


def test_observability_summary_supports_last_successful_run_and_stale_outputs() -> None:
    base = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    older = RefreshJobStatusRecord(
        stable_job_key="score_recompute:older",
        job_type=RefreshJobType.SCORE_RECOMPUTE,
        status=RefreshJobStatus.SUCCEEDED,
        enqueued_at=base,
        started_at=base + timedelta(minutes=1),
        finished_at=base + timedelta(minutes=2),
    )
    newer = RefreshJobStatusRecord(
        stable_job_key="score_recompute:newer",
        job_type=RefreshJobType.SCORE_RECOMPUTE,
        status=RefreshJobStatus.SUCCEEDED_WITH_WARNINGS,
        enqueued_at=base + timedelta(hours=1),
        started_at=base + timedelta(hours=1, minutes=1),
        finished_at=base + timedelta(hours=1, minutes=3),
    )
    failed = RefreshJobStatusRecord(
        stable_job_key="score_recompute:failed",
        job_type=RefreshJobType.SCORE_RECOMPUTE,
        status=RefreshJobStatus.FAILED,
        enqueued_at=base + timedelta(hours=2),
        failure_reason="dependency missing",
        retry_count=1,
    )

    summary = summarize_refresh_observability(
        [older, newer, failed],
        stale_output_count=5,
        job_type=RefreshJobType.SCORE_RECOMPUTE,
        target_scope={"region_id": "greater_boston"},
        target_id="greater_boston",
    )

    assert summary.last_successful_run_at == newer.finished_at
    assert summary.last_successful_job_key == "score_recompute:newer"
    assert summary.stale_output_count == 5
    assert summary.target_scope == {"region_id": "greater_boston"}
