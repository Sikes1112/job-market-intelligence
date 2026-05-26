"""Audit records for refresh-quality validation, review, and handoff actions."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .approval import ApprovedCanonicalUpdateHandoff
from .models import stable_refresh_quality_key
from .observations import CandidateObservation
from .review import HumanReviewDecision, HumanReviewRecord
from .validation import ObservationValidationResult


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class RefreshQualityAuditActionType(_Vocabulary):
    OBSERVATION_VALIDATED = "OBSERVATION_VALIDATED"
    REVIEW_DECISION_RECORDED = "REVIEW_DECISION_RECORDED"
    APPROVED_HANDOFF_PREPARED = "APPROVED_HANDOFF_PREPARED"
    REVIEW_REJECTED = "REVIEW_REJECTED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"


class RefreshQualityAuditRecord(BaseModel):
    """Structured audit record for Layer 13 review-control actions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    audit_id: str = Field(min_length=1)
    action_type: RefreshQualityAuditActionType
    observation_id: str | None = Field(default=None, min_length=1)
    review_id: str | None = Field(default=None, min_length=1)
    handoff_id: str | None = Field(default=None, min_length=1)
    original_fact: Any = None
    current_fact: Any = None
    proposed_fact: Any = None
    evidence_source_ref: str | None = Field(default=None, min_length=1)
    validation_result_summary: dict[str, Any] = Field(default_factory=dict)
    reviewer_decision: str | None = Field(default=None, min_length=1)
    affected_company_id: str | None = Field(default=None, min_length=1)
    affected_region_id: str | None = Field(default=None, min_length=1)
    affected_market_id: str | None = Field(default=None, min_length=1)
    timestamp: datetime | None = None
    output_rebuild_handoff_status: str | None = Field(default=None, min_length=1)

    @field_validator(
        "audit_id",
        "observation_id",
        "review_id",
        "handoff_id",
        "evidence_source_ref",
        "reviewer_decision",
        "affected_company_id",
        "affected_region_id",
        "affected_market_id",
        "output_rebuild_handoff_status",
    )
    @classmethod
    def _strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("timestamp")
    @classmethod
    def _timestamp_must_be_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


def audit_record_for_validation(
    *,
    observation: CandidateObservation,
    validation: ObservationValidationResult,
    timestamp: datetime | None = None,
) -> RefreshQualityAuditRecord:
    if validation.observation_id != observation.observation_id:
        raise ValueError("validation must link to the supplied observation")
    return _audit_record(
        action_type=RefreshQualityAuditActionType.OBSERVATION_VALIDATED,
        observation=observation,
        validation=validation,
        timestamp=timestamp,
    )


def audit_record_for_review(
    *,
    observation: CandidateObservation,
    review: HumanReviewRecord,
    validation: ObservationValidationResult | None = None,
    timestamp: datetime | None = None,
) -> RefreshQualityAuditRecord:
    if review.observation_id != observation.observation_id:
        raise ValueError("review must link to the supplied observation")
    if validation is not None and validation.observation_id != observation.observation_id:
        raise ValueError("validation must link to the supplied observation")
    return _audit_record(
        action_type=_action_for_review_decision(review.decision),
        observation=observation,
        validation=validation,
        review=review,
        timestamp=timestamp,
    )


def audit_record_for_handoff(
    *,
    observation: CandidateObservation,
    review: HumanReviewRecord,
    validation: ObservationValidationResult,
    handoff: ApprovedCanonicalUpdateHandoff,
    timestamp: datetime | None = None,
) -> RefreshQualityAuditRecord:
    if handoff.approved_observation_id != observation.observation_id:
        raise ValueError("handoff must link to the supplied observation")
    return _audit_record(
        action_type=RefreshQualityAuditActionType.APPROVED_HANDOFF_PREPARED,
        observation=observation,
        validation=validation,
        review=review,
        handoff=handoff,
        timestamp=timestamp,
    )


def _audit_record(
    *,
    action_type: RefreshQualityAuditActionType,
    observation: CandidateObservation,
    validation: ObservationValidationResult | None = None,
    review: HumanReviewRecord | None = None,
    handoff: ApprovedCanonicalUpdateHandoff | None = None,
    timestamp: datetime | None = None,
) -> RefreshQualityAuditRecord:
    timestamp = _checked_at(timestamp)
    company_id, region_id = _company_region_parts(observation.entity_id)
    validation_summary = (
        {
            "validation_id": validation.validation_id,
            "state": validation.state.value,
            "blocking_issue_count": len(validation.blocking_issues),
            "warning_count": len(validation.warnings),
            "recommended_review_decision": (
                validation.recommended_review_decision.value
            ),
        }
        if validation is not None
        else {}
    )
    return RefreshQualityAuditRecord(
        audit_id=stable_refresh_quality_key(
            "refresh_quality_audit",
            action_type.value,
            observation.observation_id,
            review.review_id if review else "",
            handoff.handoff_id if handoff else "",
        ),
        action_type=action_type,
        observation_id=observation.observation_id,
        review_id=review.review_id if review else None,
        handoff_id=handoff.handoff_id if handoff else None,
        original_fact=observation.previous_value,
        current_fact=observation.current_value,
        proposed_fact=observation.proposed_value,
        evidence_source_ref=observation.source_evidence_ref,
        validation_result_summary=validation_summary,
        reviewer_decision=review.decision.value if review else None,
        affected_company_id=company_id,
        affected_region_id=region_id,
        affected_market_id=region_id if observation.entity_type == "region" else None,
        timestamp=timestamp,
        output_rebuild_handoff_status=(
            handoff.status.value if handoff and handoff.output_rebuild_needed else None
        ),
    )


def _action_for_review_decision(
    decision: HumanReviewDecision,
) -> RefreshQualityAuditActionType:
    if decision is HumanReviewDecision.APPROVED:
        return RefreshQualityAuditActionType.REVIEW_DECISION_RECORDED
    if decision is HumanReviewDecision.REJECTED:
        return RefreshQualityAuditActionType.REVIEW_REJECTED
    if decision is HumanReviewDecision.POLICY_BLOCKED:
        return RefreshQualityAuditActionType.POLICY_BLOCKED
    if decision is HumanReviewDecision.NEEDS_MORE_EVIDENCE:
        return RefreshQualityAuditActionType.NEEDS_MORE_EVIDENCE
    return RefreshQualityAuditActionType.REVIEW_DECISION_RECORDED


def _company_region_parts(entity_id: str) -> tuple[str | None, str | None]:
    if "::" not in entity_id:
        return None, entity_id
    company_id, region_id = entity_id.split("::", 1)
    return company_id or None, region_id or None


def _checked_at(timestamp: datetime | None) -> datetime:
    if timestamp is None:
        return datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return timestamp


__all__ = [
    "RefreshQualityAuditActionType",
    "RefreshQualityAuditRecord",
    "audit_record_for_handoff",
    "audit_record_for_review",
    "audit_record_for_validation",
]
