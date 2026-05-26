"""Candidate observations for Layer 13 human review.

Candidate observations are proposed evidence from refresh-quality work. They
are not canonical truth and they do not update canonical facts.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import (
    LegalTermsPosture,
    RefreshCandidate,
    SourceRefreshQueueItem,
    SourceRefreshTargetType,
    stable_refresh_quality_key,
)


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class CandidateObservationStatus(_Vocabulary):
    PENDING_VALIDATION = "PENDING_VALIDATION"
    VALIDATED = "VALIDATED"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    REJECTED = "REJECTED"
    APPROVED_FOR_HANDOFF = "APPROVED_FOR_HANDOFF"


class CandidateObservation(BaseModel):
    """Proposed refresh evidence awaiting validation and human review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(min_length=1)
    refresh_candidate_key: str | None = Field(default=None, min_length=1)
    queue_item_id: str | None = Field(default=None, min_length=1)
    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    fact_type: str = Field(min_length=1)
    previous_value: Any = None
    current_value: Any = None
    proposed_value: Any = None
    source_evidence_ref: str | None = Field(default=None, min_length=1)
    source_type: SourceRefreshTargetType
    legal_terms_posture: LegalTermsPosture
    confidence: str | None = Field(default=None, min_length=1)
    observation_status: CandidateObservationStatus = (
        CandidateObservationStatus.PENDING_VALIDATION
    )
    explanation: str = Field(min_length=1)
    observed_at: datetime | None = None
    source_dominance_ratio: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator(
        "observation_id",
        "refresh_candidate_key",
        "queue_item_id",
        "entity_type",
        "entity_id",
        "fact_type",
        "source_evidence_ref",
        "confidence",
        "explanation",
    )
    @classmethod
    def _strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("observed_at")
    @classmethod
    def _observed_at_must_be_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        return value


def stable_candidate_observation_id(
    *,
    refresh_candidate_key: str | None,
    queue_item_id: str | None,
    entity_type: str,
    entity_id: str,
    fact_type: str,
    source_evidence_ref: str | None,
) -> str:
    return stable_refresh_quality_key(
        "candidate_observation",
        refresh_candidate_key or "",
        queue_item_id or "",
        entity_type,
        entity_id,
        fact_type,
        source_evidence_ref or "",
    )


def make_candidate_observation(
    *,
    entity_type: str,
    entity_id: str,
    fact_type: str,
    proposed_value: Any,
    source_evidence_ref: str | None,
    source_type: SourceRefreshTargetType,
    legal_terms_posture: LegalTermsPosture,
    explanation: str,
    refresh_candidate_key: str | None = None,
    queue_item_id: str | None = None,
    previous_value: Any = None,
    current_value: Any = None,
    confidence: str | None = None,
    observed_at: datetime | None = None,
    source_dominance_ratio: float | None = None,
    observation_status: CandidateObservationStatus = (
        CandidateObservationStatus.PENDING_VALIDATION
    ),
) -> CandidateObservation:
    """Build a deterministic candidate observation record."""

    return CandidateObservation(
        observation_id=stable_candidate_observation_id(
            refresh_candidate_key=refresh_candidate_key,
            queue_item_id=queue_item_id,
            entity_type=entity_type,
            entity_id=entity_id,
            fact_type=fact_type,
            source_evidence_ref=source_evidence_ref,
        ),
        refresh_candidate_key=refresh_candidate_key,
        queue_item_id=queue_item_id,
        entity_type=entity_type,
        entity_id=entity_id,
        fact_type=fact_type,
        previous_value=previous_value,
        current_value=current_value,
        proposed_value=proposed_value,
        source_evidence_ref=source_evidence_ref,
        source_type=source_type,
        legal_terms_posture=legal_terms_posture,
        confidence=confidence,
        observation_status=observation_status,
        explanation=explanation,
        observed_at=observed_at,
        source_dominance_ratio=source_dominance_ratio,
    )


def observation_from_candidate_and_queue(
    *,
    candidate: RefreshCandidate,
    queue_item: SourceRefreshQueueItem,
    proposed_value: Any,
    source_evidence_ref: str | None,
    explanation: str,
    observed_at: datetime | None = None,
    confidence: str | None = None,
    source_dominance_ratio: float | None = None,
) -> CandidateObservation:
    """Create an observation from Batch 1 candidate and queue metadata."""

    if queue_item.candidate_key != candidate.candidate_key:
        raise ValueError("queue item must link to the supplied refresh candidate")
    return make_candidate_observation(
        refresh_candidate_key=candidate.candidate_key,
        queue_item_id=queue_item.queue_item_id,
        entity_type=candidate.entity_type,
        entity_id=candidate.entity_id,
        fact_type=candidate.fact_type,
        previous_value=candidate.current_value,
        current_value=candidate.current_value,
        proposed_value=proposed_value,
        source_evidence_ref=source_evidence_ref,
        source_type=queue_item.source_type,
        legal_terms_posture=queue_item.legal_terms_posture,
        confidence=confidence or candidate.confidence,
        explanation=explanation,
        observed_at=observed_at,
        source_dominance_ratio=source_dominance_ratio,
    )


__all__ = [
    "CandidateObservation",
    "CandidateObservationStatus",
    "make_candidate_observation",
    "observation_from_candidate_and_queue",
    "stable_candidate_observation_id",
]
