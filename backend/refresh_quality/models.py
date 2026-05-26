"""Read-only refresh-quality control plane models.

Layer 13 Batch 1 records diagnostic work: refresh candidates, reviewable
source-refresh queue items, and quality regressions. These models are not
canonical market truth, source observations, jobs, score inputs, or output
builders.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class QualitySeverity(_Vocabulary):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RefreshCandidateReason(_Vocabulary):
    STALE_HIRING_COUNT = "stale_hiring_count"
    EXPIRED_INTERNSHIP_DATA = "expired_internship_data"
    OLD_COMPANY_REGION_PRESENCE_DATA = "old_company_region_presence_data"
    LOW_CONFIDENCE_SOURCE_FACT = "low_confidence_source_fact"
    MISSING_SOURCE_FACT = "missing_source_fact"
    STALE_ENTRY_LEVEL_SIGNAL = "stale_entry_level_signal"
    COVERAGE_GAP = "coverage_gap"


class RefreshCandidateStatus(_Vocabulary):
    IDENTIFIED = "identified"
    QUEUED_FOR_REVIEW = "queued_for_review"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


class SourceRefreshTargetType(_Vocabulary):
    COMPANY_PAGE = "company_page"
    COMPANY_CAREERS_PAGE = "company_careers_page"
    PUBLIC_JOB_BOARD = "public_job_board"
    GOVERNMENT_OPEN_DATASET = "government_open_dataset"
    UNIVERSITY_COOP_PUBLIC_EMPLOYER_LIST = (
        "university_coop_public_employer_list"
    )
    COMPANY_INTERNSHIP_PAGE = "company_internship_page"
    MANUAL_RESEARCH_REQUIRED = "manual_research_required"


class LegalTermsPosture(_Vocabulary):
    MANUAL_ONLY = "MANUAL_ONLY"
    PUBLIC_DATASET_ALLOWED = "PUBLIC_DATASET_ALLOWED"
    TERMS_REVIEW_REQUIRED = "TERMS_REVIEW_REQUIRED"
    DISALLOWED = "DISALLOWED"
    UNKNOWN = "UNKNOWN"


class QueuePriority(_Vocabulary):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class SourceRefreshQueueStatus(_Vocabulary):
    PENDING_REVIEW = "pending_review"
    MANUAL_ONLY = "manual_only"
    TERMS_REVIEW_REQUIRED = "terms_review_required"
    DISALLOWED = "disallowed"
    DISMISSED = "dismissed"
    COMPLETED = "completed"


class QualityRegressionType(_Vocabulary):
    SOURCE_DISAPPEARED = "source_disappeared"
    SUSPICIOUS_HIRING_COUNT_DROP = "suspicious_hiring_count_drop"
    COMPANY_REGION_PRESENCE_CONTRADICTED = (
        "company_region_presence_contradicted"
    )
    ENTRY_LEVEL_SIGNAL_BECAME_STALE = "entry_level_signal_became_stale"
    SINGLE_SOURCE_DOMINATES_MARKET_SCORE = (
        "single_source_dominates_market_score"
    )
    MARKET_SCORE_LOW_CONFIDENCE_OVERRELIANCE = (
        "market_score_relies_too_heavily_on_low_confidence_facts"
    )
    COVERAGE_GAP_WORSENED = "coverage_gap_worsened"
    REPEATED_REFRESH_FAILURE = "repeated_refresh_failure"


class RefreshFactSnapshot(BaseModel):
    """Existing fact metadata inspected for possible refresh work.

    This is a read-side snapshot of metadata already present in the system. It
    is not a canonical fact and must not be persisted as one.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    fact_type: str = Field(min_length=1)
    fact_id: str | None = Field(default=None, min_length=1)
    current_value: Any = None
    last_updated_at: datetime | None = None
    freshness_expires_at: datetime | None = None
    confidence: str | None = Field(default=None, min_length=1)
    source_refs: tuple[str, ...] = Field(default_factory=tuple)
    evidence_context: dict[str, Any] = Field(default_factory=dict)
    coverage_score: float | None = Field(default=None, ge=0.0, le=100.0)
    required: bool = True
    recommended_source_type: SourceRefreshTargetType | None = None

    @property
    def logical_fact_id(self) -> str:
        return self.fact_id or f"{self.entity_type}:{self.entity_id}:{self.fact_type}"

    @field_validator(
        "entity_type",
        "entity_id",
        "fact_type",
        "fact_id",
        "confidence",
    )
    @classmethod
    def _strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("source_refs")
    @classmethod
    def _source_refs_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for ref in value:
            if not isinstance(ref, str) or not ref.strip():
                raise ValueError("source refs must be non-empty strings")
        return tuple(ref.strip() for ref in value)

    @field_validator("last_updated_at", "freshness_expires_at")
    @classmethod
    def _timestamps_must_be_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return value


class RefreshCandidate(BaseModel):
    """Diagnostic record saying an existing fact may need refresh."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_key: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    fact_type: str = Field(min_length=1)
    fact_id: str | None = Field(default=None, min_length=1)
    reason: RefreshCandidateReason
    severity: QualitySeverity
    status: RefreshCandidateStatus = RefreshCandidateStatus.IDENTIFIED
    explanation: str = Field(min_length=1)
    evidence_context: dict[str, Any] = Field(default_factory=dict)
    current_value: Any = None
    last_updated_at: datetime | None = None
    confidence: str | None = Field(default=None, min_length=1)
    recommended_source_type: SourceRefreshTargetType | None = None

    @field_validator(
        "candidate_key",
        "entity_type",
        "entity_id",
        "fact_type",
        "fact_id",
        "explanation",
        "confidence",
    )
    @classmethod
    def _strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("last_updated_at")
    @classmethod
    def _last_updated_must_be_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("last_updated_at must be timezone-aware")
        return value


class SourceRefreshQueueItem(BaseModel):
    """Reviewable source-refresh work item.

    Queue items describe research work for humans or a future approved
    workflow. They are not executable scraping jobs.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    queue_item_id: str = Field(min_length=1)
    candidate_key: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    source_type: SourceRefreshTargetType
    priority: QueuePriority
    legal_terms_posture: LegalTermsPosture
    reason: RefreshCandidateReason
    status: SourceRefreshQueueStatus
    explanation: str = Field(min_length=1)
    created_at: datetime | None = None

    @field_validator("queue_item_id", "candidate_key", "entity_type", "entity_id")
    @classmethod
    def _strings_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("created_at")
    @classmethod
    def _created_at_must_be_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class QualityRegressionSnapshot(BaseModel):
    """Current-vs-prior quality metadata for regression detection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    previous_source_refs: tuple[str, ...] = Field(default_factory=tuple)
    current_source_refs: tuple[str, ...] = Field(default_factory=tuple)
    previous_hiring_count: int | None = Field(default=None, ge=0)
    current_hiring_count: int | None = Field(default=None, ge=0)
    previous_presence_status: str | None = Field(default=None, min_length=1)
    current_presence_status: str | None = Field(default=None, min_length=1)
    entry_level_freshness_expires_at: datetime | None = None
    market_score_source_weights: dict[str, float] = Field(default_factory=dict)
    market_score_low_confidence_weight: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    previous_coverage_gap_count: int | None = Field(default=None, ge=0)
    current_coverage_gap_count: int | None = Field(default=None, ge=0)
    refresh_failure_count: int = Field(default=0, ge=0)
    old_value: Any = None
    current_value: Any = None
    evidence_values: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "entity_type",
        "entity_id",
        "previous_presence_status",
        "current_presence_status",
    )
    @classmethod
    def _strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("previous_source_refs", "current_source_refs")
    @classmethod
    def _source_refs_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for ref in value:
            if not isinstance(ref, str) or not ref.strip():
                raise ValueError("source refs must be non-empty strings")
        return tuple(ref.strip() for ref in value)

    @field_validator("entry_level_freshness_expires_at")
    @classmethod
    def _freshness_must_be_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("entry_level_freshness_expires_at must be timezone-aware")
        return value

    @field_validator("market_score_source_weights")
    @classmethod
    def _source_weights_are_ratios(
        cls, value: dict[str, float]
    ) -> dict[str, float]:
        for source_ref, weight in value.items():
            if not isinstance(source_ref, str) or not source_ref.strip():
                raise ValueError("source weight keys must be non-empty strings")
            if weight < 0.0 or weight > 1.0:
                raise ValueError("source weights must be ratios between 0 and 1")
        return {source_ref.strip(): weight for source_ref, weight in value.items()}


class QualityRegressionRecord(BaseModel):
    """Diagnostic record that data quality became worse."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    regression_id: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    regression_type: QualityRegressionType
    severity: QualitySeverity
    explanation: str = Field(min_length=1)
    evidence_values: dict[str, Any] = Field(default_factory=dict)
    old_value: Any = None
    current_value: Any = None
    recommended_action: str = Field(min_length=1)
    human_review_required: bool = True

    @field_validator(
        "regression_id",
        "entity_type",
        "entity_id",
        "explanation",
        "recommended_action",
    )
    @classmethod
    def _strings_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


def stable_refresh_candidate_key(
    *,
    entity_type: str,
    entity_id: str,
    fact_type: str,
    fact_id: str | None,
    reason: RefreshCandidateReason,
) -> str:
    digest = _stable_digest(
        "refresh_candidate",
        entity_type,
        entity_id,
        fact_type,
        fact_id or "",
        reason.value,
    )
    return f"refresh_candidate:{reason.value}:{digest}"


def stable_source_queue_item_id(
    *,
    candidate_key: str,
    source_type: SourceRefreshTargetType,
) -> str:
    digest = _stable_digest("source_refresh_queue", candidate_key, source_type.value)
    return f"source_refresh_queue:{digest}"


def stable_quality_regression_id(
    *,
    entity_type: str,
    entity_id: str,
    regression_type: QualityRegressionType,
) -> str:
    digest = _stable_digest(
        "quality_regression",
        entity_type,
        entity_id,
        regression_type.value,
    )
    return f"quality_regression:{regression_type.value}:{digest}"


def stable_refresh_quality_key(prefix: str, *parts: object) -> str:
    """Build a deterministic ID for refresh-quality control-plane records."""

    digest = _stable_digest(prefix, *parts)
    return f"{prefix}:{digest}"


def _stable_digest(*parts: object) -> str:
    canonical = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


__all__ = [
    "LegalTermsPosture",
    "QualityRegressionRecord",
    "QualityRegressionSnapshot",
    "QualityRegressionType",
    "QualitySeverity",
    "QueuePriority",
    "RefreshCandidate",
    "RefreshCandidateReason",
    "RefreshCandidateStatus",
    "RefreshFactSnapshot",
    "SourceRefreshQueueItem",
    "SourceRefreshQueueStatus",
    "SourceRefreshTargetType",
    "stable_quality_regression_id",
    "stable_refresh_candidate_key",
    "stable_refresh_quality_key",
    "stable_source_queue_item_id",
]
