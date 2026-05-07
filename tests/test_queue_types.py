import pytest

from backend.orchestration.jobs.types import JobType
from backend.orchestration.queues.types import (
    DEFAULT_QUEUE_FOR_JOB_TYPE,
    QueueName,
    coerce_queue_name,
    default_queue_for,
)


def test_four_mvp_queue_names() -> None:
    assert QueueName.values() == {
        "foundational",
        "refresh",
        "output",
        "interactive",
    }


def test_default_queue_for_each_implemented_job_type() -> None:
    """Every JobType that has a handler in Slice 14's default registry must
    have a default queue."""
    expected = {
        JobType.GEOGRAPHY_BUILD: QueueName.FOUNDATIONAL,
        JobType.ELIGIBILITY_CLASSIFICATION: QueueName.FOUNDATIONAL,
        JobType.PRESENCE_MAPPING: QueueName.FOUNDATIONAL,
        JobType.HIRING_REFRESH: QueueName.REFRESH,
        JobType.ENTRY_LEVEL_REFRESH: QueueName.REFRESH,
        JobType.REGION_SCORE_RECOMPUTE: QueueName.REFRESH,
        JobType.REGION_OUTPUT_BUILD: QueueName.OUTPUT,
        JobType.COMPANY_OUTPUT_BUILD: QueueName.OUTPUT,
        JobType.COMPARISON_CACHE_BUILD: QueueName.OUTPUT,
    }
    for jt, expected_queue in expected.items():
        assert default_queue_for(jt) is expected_queue


def test_default_queue_raises_for_unmapped() -> None:
    """AUDIT has no handler in Slice 14 and no default queue mapping."""
    with pytest.raises(ValueError):
        default_queue_for(JobType.AUDIT)


def test_coerce_accepts_queue_name_or_string() -> None:
    assert coerce_queue_name(QueueName.OUTPUT) is QueueName.OUTPUT
    assert coerce_queue_name("foundational") is QueueName.FOUNDATIONAL


def test_coerce_rejects_unknown_string() -> None:
    with pytest.raises(ValueError):
        coerce_queue_name("not_a_queue")


def test_personalization_and_audit_queues_documented() -> None:
    """PERSONAL_OVERLAY_QUERY and CONTEXTUAL_CHALLENGE_BUILD are documented
    as interactive but Slice 14 doesn't register handlers for them. The
    default queue mapping still describes their home."""
    assert (
        DEFAULT_QUEUE_FOR_JOB_TYPE[JobType.PERSONAL_OVERLAY_QUERY]
        is QueueName.INTERACTIVE
    )
    assert (
        DEFAULT_QUEUE_FOR_JOB_TYPE[JobType.CONTEXTUAL_CHALLENGE_BUILD]
        is QueueName.INTERACTIVE
    )
