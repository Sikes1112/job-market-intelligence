from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.refresh_quality.models import LegalTermsPosture, SourceRefreshTargetType
from backend.refresh_quality.observations import make_candidate_observation
from backend.refresh_quality.validation import (
    ObservationValidationState,
    RecommendedReviewDecision,
    ValidationIssueCode,
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


def test_clean_observation_validation_passes_and_recommends_approve() -> None:
    result = validate_candidate_observation(_observation(), now=NOW)

    assert result.validation_id.startswith("observation_validation:")
    assert result.state is ObservationValidationState.PASSED
    assert result.blocking_issues == ()
    assert result.warnings == ()
    assert result.recommended_review_decision is RecommendedReviewDecision.APPROVE


def test_missing_evidence_and_low_confidence_fail_validation() -> None:
    result = validate_candidate_observation(
        _observation(source_evidence_ref=None, confidence="low_confidence"),
        now=NOW,
    )
    codes = {issue.code for issue in result.blocking_issues}

    assert result.state is ObservationValidationState.FAILED
    assert ValidationIssueCode.SOURCE_EVIDENCE_MISSING in codes
    assert ValidationIssueCode.CONFIDENCE_BELOW_THRESHOLD in codes
    assert result.recommended_review_decision is RecommendedReviewDecision.NEEDS_MORE_EVIDENCE


def test_disallowed_legal_posture_policy_blocks() -> None:
    result = validate_candidate_observation(
        _observation(legal_terms_posture=LegalTermsPosture.DISALLOWED),
        now=NOW,
    )

    assert result.state is ObservationValidationState.FAILED
    assert result.recommended_review_decision is RecommendedReviewDecision.POLICY_BLOCK
    assert any(
        issue.code is ValidationIssueCode.LEGAL_POSTURE_DISALLOWED
        for issue in result.blocking_issues
    )


def test_public_job_board_is_warning_not_auto_approval() -> None:
    result = validate_candidate_observation(
        _observation(
            source_type=SourceRefreshTargetType.PUBLIC_JOB_BOARD,
            legal_terms_posture=LegalTermsPosture.TERMS_REVIEW_REQUIRED,
        ),
        now=NOW,
    )
    warning_codes = {issue.code for issue in result.warnings}

    assert result.state is ObservationValidationState.PASSED_WITH_WARNINGS
    assert ValidationIssueCode.PUBLIC_JOB_BOARD_REQUIRES_REVIEW in warning_codes
    assert result.recommended_review_decision is RecommendedReviewDecision.NEEDS_MORE_EVIDENCE


def test_numeric_change_missing_prior_stale_source_contradiction_and_dominance_warn() -> None:
    numeric = validate_candidate_observation(
        _observation(current_value=10, proposed_value=30),
        now=NOW,
    )
    assert any(
        issue.code is ValidationIssueCode.SUSPICIOUS_NUMERIC_CHANGE
        for issue in numeric.warnings
    )

    missing_prior = validate_candidate_observation(
        _observation(current_value=None, previous_value=None),
        now=NOW,
    )
    assert any(
        issue.code is ValidationIssueCode.PRIOR_VALUE_MISSING
        for issue in missing_prior.warnings
    )

    stale = validate_candidate_observation(
        _observation(observed_at=NOW - timedelta(days=121)),
        now=NOW,
    )
    assert any(
        issue.code is ValidationIssueCode.STALE_SOURCE_EVIDENCE
        for issue in stale.warnings
    )

    contradiction = validate_candidate_observation(
        _observation(
            fact_type="company_region_presence",
            current_value="present",
            proposed_value="not_present",
        ),
        now=NOW,
    )
    assert any(
        issue.code is ValidationIssueCode.CONTRADICTS_EXISTING_VALUE
        for issue in contradiction.warnings
    )

    dominance = validate_candidate_observation(
        _observation(source_dominance_ratio=0.9),
        now=NOW,
    )
    assert any(
        issue.code is ValidationIssueCode.SOURCE_DOMINANCE_RISK
        for issue in dominance.warnings
    )
