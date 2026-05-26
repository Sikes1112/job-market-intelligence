from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.refresh_quality.approval import (
    HandoffStatus,
    prepare_approved_canonical_update_handoff,
)
from backend.refresh_quality.audit import (
    RefreshQualityAuditActionType,
    audit_record_for_handoff,
    audit_record_for_review,
    audit_record_for_validation,
)
from backend.refresh_quality.models import LegalTermsPosture, SourceRefreshTargetType
from backend.refresh_quality.observations import make_candidate_observation
from backend.refresh_quality.review import (
    HumanReviewDecision,
    record_human_review_decision,
)
from backend.refresh_quality.validation import validate_candidate_observation

NOW = datetime(2026, 5, 26, 12, tzinfo=UTC)


def _approved_bundle():
    observation = make_candidate_observation(
        entity_type="company_region",
        entity_id="company_a::boston",
        fact_type="hiring_count",
        previous_value=10,
        current_value=10,
        proposed_value=12,
        source_evidence_ref="source_obs_a",
        source_type=SourceRefreshTargetType.COMPANY_CAREERS_PAGE,
        legal_terms_posture=LegalTermsPosture.PUBLIC_DATASET_ALLOWED,
        confidence="high_confidence",
        explanation="reviewed source evidence",
        observed_at=NOW,
    )
    validation = validate_candidate_observation(observation, now=NOW)
    review = record_human_review_decision(
        observation=observation,
        validation=validation,
        decision=HumanReviewDecision.APPROVED,
        reviewer_id="admin_1",
        reviewer_note="approve for handoff",
        reviewed_at=NOW,
    )
    return observation, validation, review


def test_handoff_status_values_are_documented() -> None:
    assert HandoffStatus.values() == {
        "PREPARED",
        "WAITING_CANONICAL_APPLY",
        "APPLIED_EXTERNALLY",
        "REJECTED_BEFORE_APPLY",
        "SUPERSEDED",
    }


def test_approved_review_prepares_handoff_without_canonical_write() -> None:
    observation, validation, review = _approved_bundle()

    handoff = prepare_approved_canonical_update_handoff(
        observation=observation,
        validation=validation,
        review=review,
        output_rebuild_needed=True,
        audit_metadata={"request_id": "req_1"},
    )

    assert handoff.handoff_id.startswith("approved_canonical_update_handoff:")
    assert handoff.approved_observation_id == observation.observation_id
    assert handoff.review_decision_id == review.review_id
    assert handoff.target_entity_type == "company_region"
    assert handoff.target_entity_id == "company_a::boston"
    assert handoff.target_fact_type == "hiring_count"
    assert handoff.current_value == 10
    assert handoff.proposed_value == 12
    assert handoff.status is HandoffStatus.PREPARED
    assert handoff.output_rebuild_needed is True


def test_non_approved_review_cannot_prepare_handoff() -> None:
    observation, validation, _review = _approved_bundle()
    rejected = record_human_review_decision(
        observation=observation,
        validation=validation,
        decision=HumanReviewDecision.REJECTED,
        reviewer_id="admin_1",
        reviewer_note="reject",
        reviewed_at=NOW,
    )

    with pytest.raises(ValueError, match="only APPROVED reviews"):
        prepare_approved_canonical_update_handoff(
            observation=observation,
            validation=validation,
            review=rejected,
        )


def test_audit_records_cover_validation_review_and_handoff() -> None:
    observation, validation, review = _approved_bundle()
    handoff = prepare_approved_canonical_update_handoff(
        observation=observation,
        validation=validation,
        review=review,
        output_rebuild_needed=True,
    )

    validation_audit = audit_record_for_validation(
        observation=observation,
        validation=validation,
        timestamp=NOW,
    )
    review_audit = audit_record_for_review(
        observation=observation,
        validation=validation,
        review=review,
        timestamp=NOW,
    )
    handoff_audit = audit_record_for_handoff(
        observation=observation,
        validation=validation,
        review=review,
        handoff=handoff,
        timestamp=NOW,
    )

    assert validation_audit.action_type is RefreshQualityAuditActionType.OBSERVATION_VALIDATED
    assert review_audit.action_type is RefreshQualityAuditActionType.REVIEW_DECISION_RECORDED
    assert handoff_audit.action_type is RefreshQualityAuditActionType.APPROVED_HANDOFF_PREPARED
    assert handoff_audit.affected_company_id == "company_a"
    assert handoff_audit.affected_region_id == "boston"
    assert handoff_audit.output_rebuild_handoff_status == "PREPARED"
