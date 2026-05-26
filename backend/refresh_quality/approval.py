"""Approved canonical update handoff records.

Handoffs are intent records for an external canonical apply boundary. They do
not write canonical truth, mutate scores, invalidate caches, or rebuild output.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import stable_refresh_quality_key
from .observations import CandidateObservation
from .review import HumanReviewDecision, HumanReviewRecord
from .validation import ObservationValidationResult


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class HandoffStatus(_Vocabulary):
    PREPARED = "PREPARED"
    WAITING_CANONICAL_APPLY = "WAITING_CANONICAL_APPLY"
    APPLIED_EXTERNALLY = "APPLIED_EXTERNALLY"
    REJECTED_BEFORE_APPLY = "REJECTED_BEFORE_APPLY"
    SUPERSEDED = "SUPERSEDED"


class ApprovedCanonicalUpdateHandoff(BaseModel):
    """Approved intent for a separate canonical apply process."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    handoff_id: str = Field(min_length=1)
    approved_observation_id: str = Field(min_length=1)
    review_decision_id: str = Field(min_length=1)
    target_entity_type: str = Field(min_length=1)
    target_entity_id: str = Field(min_length=1)
    target_fact_type: str = Field(min_length=1)
    old_value: Any = None
    current_value: Any = None
    proposed_value: Any = None
    source_evidence_ref: str | None = Field(default=None, min_length=1)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    reviewer_id: str | None = Field(default=None, min_length=1)
    audit_metadata: dict[str, Any] = Field(default_factory=dict)
    output_rebuild_needed: bool = False
    status: HandoffStatus = HandoffStatus.PREPARED

    @field_validator(
        "handoff_id",
        "approved_observation_id",
        "review_decision_id",
        "target_entity_type",
        "target_entity_id",
        "target_fact_type",
        "source_evidence_ref",
        "reviewer_id",
    )
    @classmethod
    def _strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


def stable_handoff_id(*, observation_id: str, review_id: str) -> str:
    return stable_refresh_quality_key(
        "approved_canonical_update_handoff",
        observation_id,
        review_id,
    )


def prepare_approved_canonical_update_handoff(
    *,
    observation: CandidateObservation,
    review: HumanReviewRecord,
    validation: ObservationValidationResult,
    output_rebuild_needed: bool = False,
    audit_metadata: dict[str, Any] | None = None,
) -> ApprovedCanonicalUpdateHandoff:
    """Prepare an approved handoff without applying it."""

    if review.observation_id != observation.observation_id:
        raise ValueError("review must link to the supplied observation")
    if validation.observation_id != observation.observation_id:
        raise ValueError("validation must link to the supplied observation")
    if review.validation_id is not None and review.validation_id != validation.validation_id:
        raise ValueError("review validation_id must match the supplied validation")
    if review.decision is not HumanReviewDecision.APPROVED:
        raise ValueError("only APPROVED reviews can produce canonical handoff records")

    return ApprovedCanonicalUpdateHandoff(
        handoff_id=stable_handoff_id(
            observation_id=observation.observation_id,
            review_id=review.review_id,
        ),
        approved_observation_id=observation.observation_id,
        review_decision_id=review.review_id,
        target_entity_type=observation.entity_type,
        target_entity_id=observation.entity_id,
        target_fact_type=observation.fact_type,
        old_value=observation.previous_value,
        current_value=observation.current_value,
        proposed_value=observation.proposed_value,
        source_evidence_ref=observation.source_evidence_ref,
        validation_summary={
            "validation_id": validation.validation_id,
            "state": validation.state.value,
            "blocking_issue_count": len(validation.blocking_issues),
            "warning_count": len(validation.warnings),
            "recommended_review_decision": (
                validation.recommended_review_decision.value
            ),
        },
        reviewer_id=review.reviewer_id,
        audit_metadata=dict(audit_metadata or {}),
        output_rebuild_needed=output_rebuild_needed,
        status=HandoffStatus.PREPARED,
    )


__all__ = [
    "ApprovedCanonicalUpdateHandoff",
    "HandoffStatus",
    "prepare_approved_canonical_update_handoff",
    "stable_handoff_id",
]
