from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.refresh_quality.models import LegalTermsPosture, SourceRefreshTargetType
from backend.refresh_quality.observations import make_candidate_observation
from backend.refresh_quality.review import (
    HumanReviewDecision,
    record_human_review_decision,
    review_decision_for_validation,
)
from backend.refresh_quality.validation import (
    RecommendedReviewDecision,
    validate_candidate_observation,
)

NOW = datetime(2026, 5, 26, 12, tzinfo=UTC)


def _observation(**overrides):
    base = {
        "entity_type": "company_region",
        "entity_id": "company_a::boston",
        "fact_type": "hiring_count",
        "current_value": 10,
        "proposed_value": 11,
        "source_evidence_ref": "source_obs_a",
        "source_type": SourceRefreshTargetType.COMPANY_CAREERS_PAGE,
        "legal_terms_posture": LegalTermsPosture.PUBLIC_DATASET_ALLOWED,
        "confidence": "high_confidence",
        "explanation": "reviewed evidence",
        "observed_at": NOW,
    }
    base.update(overrides)
    return make_candidate_observation(**base)


def test_review_decision_values_are_documented() -> None:
    assert HumanReviewDecision.values() == {
        "APPROVED",
        "REJECTED",
        "NEEDS_MORE_EVIDENCE",
        "DUPLICATE",
        "OUT_OF_SCOPE",
        "POLICY_BLOCKED",
    }


def test_review_record_preserves_validation_and_reviewer_context() -> None:
    observation = _observation()
    validation = validate_candidate_observation(observation, now=NOW)

    review = record_human_review_decision(
        observation=observation,
        validation=validation,
        decision=HumanReviewDecision.APPROVED,
        reviewer_id="admin_1",
        reviewer_note="approved after source review",
        reviewed_at=NOW,
    )

    assert review.review_id.startswith("human_review:")
    assert review.observation_id == observation.observation_id
    assert review.validation_id == validation.validation_id
    assert review.reviewer_id == "admin_1"
    assert review.decision is HumanReviewDecision.APPROVED
    assert review.reviewed_at == NOW


def test_failed_or_policy_blocked_validation_cannot_be_approved() -> None:
    failed_observation = _observation(confidence="low_confidence")
    failed_validation = validate_candidate_observation(failed_observation, now=NOW)

    with pytest.raises(ValueError, match="failed validation cannot be approved"):
        record_human_review_decision(
            observation=failed_observation,
            validation=failed_validation,
            decision=HumanReviewDecision.APPROVED,
            reviewer_note="unsafe approval",
        )


def test_review_decision_for_validation_maps_recommendation() -> None:
    observation = _observation(
        source_type=SourceRefreshTargetType.PUBLIC_JOB_BOARD,
        legal_terms_posture=LegalTermsPosture.TERMS_REVIEW_REQUIRED,
    )
    validation = validate_candidate_observation(observation, now=NOW)

    assert validation.recommended_review_decision is RecommendedReviewDecision.NEEDS_MORE_EVIDENCE
    assert review_decision_for_validation(validation) is HumanReviewDecision.NEEDS_MORE_EVIDENCE


def test_review_record_rejects_validation_for_other_observation() -> None:
    observation = _observation()
    other = _observation(entity_id="company_b::boston")
    validation = validate_candidate_observation(other, now=NOW)

    with pytest.raises(ValueError, match="validation result must link"):
        record_human_review_decision(
            observation=observation,
            validation=validation,
            decision=HumanReviewDecision.REJECTED,
            reviewer_note="wrong validation",
        )
