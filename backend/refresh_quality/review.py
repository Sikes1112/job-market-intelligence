"""Human review decision records for refresh-quality observations."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import stable_refresh_quality_key
from .observations import CandidateObservation
from .validation import (
    ObservationValidationResult,
    ObservationValidationState,
    RecommendedReviewDecision,
)


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class HumanReviewDecision(_Vocabulary):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    DUPLICATE = "DUPLICATE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    POLICY_BLOCKED = "POLICY_BLOCKED"


class HumanReviewRecord(BaseModel):
    """Auditable human decision over one candidate observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    review_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    validation_id: str | None = Field(default=None, min_length=1)
    reviewer_id: str | None = Field(default=None, min_length=1)
    decision: HumanReviewDecision
    reviewer_note: str = Field(min_length=1)
    reviewed_at: datetime | None = None

    @field_validator("review_id", "observation_id", "validation_id", "reviewer_id", "reviewer_note")
    @classmethod
    def _strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("reviewed_at")
    @classmethod
    def _reviewed_at_must_be_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")
        return value


def stable_review_id(
    *,
    observation_id: str,
    validation_id: str | None,
    decision: HumanReviewDecision,
    reviewer_id: str | None,
) -> str:
    return stable_refresh_quality_key(
        "human_review",
        observation_id,
        validation_id or "",
        decision.value,
        reviewer_id or "",
    )


def record_human_review_decision(
    *,
    observation: CandidateObservation,
    validation: ObservationValidationResult | None,
    decision: HumanReviewDecision,
    reviewer_note: str,
    reviewer_id: str | None = None,
    reviewed_at: datetime | None = None,
) -> HumanReviewRecord:
    """Create a human review record without mutating the observation."""

    if validation is not None and validation.observation_id != observation.observation_id:
        raise ValueError("validation result must link to the supplied observation")
    if decision is HumanReviewDecision.APPROVED:
        _ensure_approval_allowed(validation)
    if reviewed_at is not None and reviewed_at.tzinfo is None:
        raise ValueError("reviewed_at must be timezone-aware")
    reviewed_at = reviewed_at or datetime.now(UTC)
    return HumanReviewRecord(
        review_id=stable_review_id(
            observation_id=observation.observation_id,
            validation_id=validation.validation_id if validation else None,
            decision=decision,
            reviewer_id=reviewer_id,
        ),
        observation_id=observation.observation_id,
        validation_id=validation.validation_id if validation else None,
        reviewer_id=reviewer_id,
        decision=decision,
        reviewer_note=reviewer_note,
        reviewed_at=reviewed_at,
    )


def review_decision_for_validation(
    validation: ObservationValidationResult,
) -> HumanReviewDecision:
    """Map validation recommendation to the closest human-review decision."""

    if validation.recommended_review_decision is RecommendedReviewDecision.APPROVE:
        return HumanReviewDecision.APPROVED
    if validation.recommended_review_decision is RecommendedReviewDecision.REJECT:
        return HumanReviewDecision.REJECTED
    if validation.recommended_review_decision is RecommendedReviewDecision.POLICY_BLOCK:
        return HumanReviewDecision.POLICY_BLOCKED
    return HumanReviewDecision.NEEDS_MORE_EVIDENCE


def _ensure_approval_allowed(validation: ObservationValidationResult | None) -> None:
    if validation is None:
        raise ValueError("approved review requires a validation result")
    if validation.state is ObservationValidationState.FAILED:
        raise ValueError("failed validation cannot be approved for handoff")
    if validation.recommended_review_decision is RecommendedReviewDecision.POLICY_BLOCK:
        raise ValueError("policy-blocked validation cannot be approved")


__all__ = [
    "HumanReviewDecision",
    "HumanReviewRecord",
    "record_human_review_decision",
    "review_decision_for_validation",
    "stable_review_id",
]
