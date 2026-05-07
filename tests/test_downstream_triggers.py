import pytest
from pydantic import ValidationError

from backend.orchestration.events.recommendations import (
    DownstreamTriggerRecommendation,
)
from backend.orchestration.jobs.types import JobType, Priority


def test_recommendation_round_trip() -> None:
    rec = DownstreamTriggerRecommendation(
        job_type=JobType.ENTRY_LEVEL_REFRESH,
        reason="Hiring records changed for 4 company-region pairs",
        scope={"company_region_pairs": [{"company_id": "comp_101", "region_id": "greater_boston"}]},
        priority=Priority.HIGH,
    )
    dumped = rec.model_dump()
    assert dumped == {
        "job_type": "entry_level_refresh",
        "reason": "Hiring records changed for 4 company-region pairs",
        "scope": {
            "company_region_pairs": [
                {"company_id": "comp_101", "region_id": "greater_boston"}
            ]
        },
        "priority": "high",
    }
    again = DownstreamTriggerRecommendation.model_validate(dumped)
    assert again == rec


def test_recommendation_default_priority_is_normal() -> None:
    rec = DownstreamTriggerRecommendation(
        job_type=JobType.AUDIT,
        reason="post-build integrity check",
    )
    assert rec.priority is Priority.NORMAL
    assert rec.scope == {}


def test_recommendation_requires_reason() -> None:
    with pytest.raises(ValidationError):
        DownstreamTriggerRecommendation(job_type=JobType.AUDIT, reason="")


def test_recommendation_rejects_unknown_job_type() -> None:
    with pytest.raises(ValidationError):
        DownstreamTriggerRecommendation.model_validate(
            {"job_type": "build_something_else", "reason": "x"}
        )


def test_recommendation_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        DownstreamTriggerRecommendation.model_validate(
            {
                "job_type": "audit",
                "reason": "x",
                "force_run_now": True,
            }
        )


def test_recommendation_is_frozen() -> None:
    """Recommendations are advisory; immutability prevents stealth mutation downstream."""
    rec = DownstreamTriggerRecommendation(job_type=JobType.AUDIT, reason="x")
    with pytest.raises(ValidationError):
        rec.priority = Priority.URGENT  # type: ignore[misc]
