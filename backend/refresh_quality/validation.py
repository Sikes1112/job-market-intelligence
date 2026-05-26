"""Validation helpers for candidate observations.

Validation classifies review risk. It does not approve, reject, or apply
canonical updates by itself.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from numbers import Number
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import LegalTermsPosture, SourceRefreshTargetType, stable_refresh_quality_key
from .observations import CandidateObservation


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class ObservationValidationState(_Vocabulary):
    PASSED = "PASSED"
    PASSED_WITH_WARNINGS = "PASSED_WITH_WARNINGS"
    FAILED = "FAILED"


class RecommendedReviewDecision(_Vocabulary):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    POLICY_BLOCK = "POLICY_BLOCK"


class ValidationIssueSeverity(_Vocabulary):
    BLOCKING = "BLOCKING"
    WARNING = "WARNING"


class ValidationIssueCode(_Vocabulary):
    REQUIRED_FIELD_MISSING = "REQUIRED_FIELD_MISSING"
    SOURCE_EVIDENCE_MISSING = "SOURCE_EVIDENCE_MISSING"
    LEGAL_POSTURE_DISALLOWED = "LEGAL_POSTURE_DISALLOWED"
    PUBLIC_JOB_BOARD_REQUIRES_REVIEW = "PUBLIC_JOB_BOARD_REQUIRES_REVIEW"
    CONFIDENCE_BELOW_THRESHOLD = "CONFIDENCE_BELOW_THRESHOLD"
    SUSPICIOUS_NUMERIC_CHANGE = "SUSPICIOUS_NUMERIC_CHANGE"
    PRIOR_VALUE_MISSING = "PRIOR_VALUE_MISSING"
    STALE_SOURCE_EVIDENCE = "STALE_SOURCE_EVIDENCE"
    CONTRADICTS_EXISTING_VALUE = "CONTRADICTS_EXISTING_VALUE"
    SOURCE_POSTURE_LOW_CONFIDENCE = "SOURCE_POSTURE_LOW_CONFIDENCE"
    SOURCE_DOMINANCE_RISK = "SOURCE_DOMINANCE_RISK"


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ValidationIssueCode
    severity: ValidationIssueSeverity
    message: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped


class ObservationValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    validation_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    state: ObservationValidationState
    blocking_issues: tuple[ValidationIssue, ...] = Field(default_factory=tuple)
    warnings: tuple[ValidationIssue, ...] = Field(default_factory=tuple)
    explanation: str = Field(min_length=1)
    recommended_review_decision: RecommendedReviewDecision

    @field_validator("validation_id", "observation_id", "explanation")
    @classmethod
    def _strings_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


def stable_validation_id(observation_id: str) -> str:
    return stable_refresh_quality_key("observation_validation", observation_id)


def validate_candidate_observation(
    observation: CandidateObservation,
    *,
    now: datetime | None = None,
    minimum_confidence: str = "medium",
    stale_source_max_age_days: int = 120,
    suspicious_numeric_change_ratio: float = 0.50,
    source_dominance_warning_ratio: float = 0.80,
) -> ObservationValidationResult:
    """Validate one observation for human review."""

    checked_at = _checked_at(now)
    blocking: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    for field_name in ("entity_type", "entity_id", "fact_type", "explanation"):
        if not getattr(observation, field_name):
            blocking.append(
                _issue(
                    ValidationIssueCode.REQUIRED_FIELD_MISSING,
                    ValidationIssueSeverity.BLOCKING,
                    f"{field_name} is required.",
                    field=field_name,
                )
            )
    if observation.proposed_value is None:
        blocking.append(
            _issue(
                ValidationIssueCode.REQUIRED_FIELD_MISSING,
                ValidationIssueSeverity.BLOCKING,
                "proposed_value is required.",
                field="proposed_value",
            )
        )

    if not observation.source_evidence_ref:
        blocking.append(
            _issue(
                ValidationIssueCode.SOURCE_EVIDENCE_MISSING,
                ValidationIssueSeverity.BLOCKING,
                "source_evidence_ref is required before review approval.",
            )
        )

    if observation.legal_terms_posture is LegalTermsPosture.DISALLOWED:
        blocking.append(
            _issue(
                ValidationIssueCode.LEGAL_POSTURE_DISALLOWED,
                ValidationIssueSeverity.BLOCKING,
                "Source legal/terms posture is disallowed.",
                legal_terms_posture=observation.legal_terms_posture.value,
            )
        )
    elif observation.legal_terms_posture in {
        LegalTermsPosture.UNKNOWN,
        LegalTermsPosture.TERMS_REVIEW_REQUIRED,
    }:
        warnings.append(
            _issue(
                ValidationIssueCode.SOURCE_POSTURE_LOW_CONFIDENCE,
                ValidationIssueSeverity.WARNING,
                "Source legal/terms posture requires human policy attention.",
                legal_terms_posture=observation.legal_terms_posture.value,
            )
        )

    if observation.source_type is SourceRefreshTargetType.PUBLIC_JOB_BOARD:
        warnings.append(
            _issue(
                ValidationIssueCode.PUBLIC_JOB_BOARD_REQUIRES_REVIEW,
                ValidationIssueSeverity.WARNING,
                "Public job board observations cannot be automatically approved.",
                source_type=observation.source_type.value,
            )
        )

    if _confidence_rank(observation.confidence) < _confidence_rank(minimum_confidence):
        blocking.append(
            _issue(
                ValidationIssueCode.CONFIDENCE_BELOW_THRESHOLD,
                ValidationIssueSeverity.BLOCKING,
                "Observation confidence is below the minimum review threshold.",
                confidence=observation.confidence,
                minimum_confidence=minimum_confidence,
            )
        )

    prior_value = (
        observation.current_value
        if observation.current_value is not None
        else observation.previous_value
    )
    if prior_value is None:
        warnings.append(
            _issue(
                ValidationIssueCode.PRIOR_VALUE_MISSING,
                ValidationIssueSeverity.WARNING,
                "Prior/current value is missing; reviewer should treat this as new evidence.",
            )
        )
    else:
        numeric_ratio = _numeric_change_ratio(prior_value, observation.proposed_value)
        if (
            numeric_ratio is not None
            and numeric_ratio >= suspicious_numeric_change_ratio
        ):
            warnings.append(
                _issue(
                    ValidationIssueCode.SUSPICIOUS_NUMERIC_CHANGE,
                    ValidationIssueSeverity.WARNING,
                    "Proposed numeric value changed sharply from the current value.",
                    prior_value=prior_value,
                    proposed_value=observation.proposed_value,
                    change_ratio=numeric_ratio,
                )
            )
        if _contradicts_existing_value(prior_value, observation.proposed_value):
            warnings.append(
                _issue(
                    ValidationIssueCode.CONTRADICTS_EXISTING_VALUE,
                    ValidationIssueSeverity.WARNING,
                    "Proposed value contradicts the current value.",
                    current_value=prior_value,
                    proposed_value=observation.proposed_value,
                )
            )

    if observation.observed_at is not None:
        age = checked_at - observation.observed_at
        if age > timedelta(days=stale_source_max_age_days):
            warnings.append(
                _issue(
                    ValidationIssueCode.STALE_SOURCE_EVIDENCE,
                    ValidationIssueSeverity.WARNING,
                    "Source/evidence timestamp is stale for validation.",
                    observed_at=observation.observed_at.isoformat(),
                    max_age_days=stale_source_max_age_days,
                )
            )

    if (
        observation.source_dominance_ratio is not None
        and observation.source_dominance_ratio >= source_dominance_warning_ratio
    ):
        warnings.append(
            _issue(
                ValidationIssueCode.SOURCE_DOMINANCE_RISK,
                ValidationIssueSeverity.WARNING,
                "Observation carries source dominance risk.",
                source_dominance_ratio=observation.source_dominance_ratio,
                threshold=source_dominance_warning_ratio,
            )
        )

    state = _state_for(blocking, warnings)
    recommendation = _recommendation_for(
        observation,
        state=state,
        blocking_issues=blocking,
        warnings=warnings,
    )
    return ObservationValidationResult(
        validation_id=stable_validation_id(observation.observation_id),
        observation_id=observation.observation_id,
        state=state,
        blocking_issues=tuple(blocking),
        warnings=tuple(warnings),
        explanation=_explanation_for(state, blocking, warnings),
        recommended_review_decision=recommendation,
    )


def _issue(
    code: ValidationIssueCode,
    severity: ValidationIssueSeverity,
    message: str,
    **context: Any,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity=severity,
        message=message,
        context=context,
    )


def _state_for(
    blocking: list[ValidationIssue],
    warnings: list[ValidationIssue],
) -> ObservationValidationState:
    if blocking:
        return ObservationValidationState.FAILED
    if warnings:
        return ObservationValidationState.PASSED_WITH_WARNINGS
    return ObservationValidationState.PASSED


def _recommendation_for(
    observation: CandidateObservation,
    *,
    state: ObservationValidationState,
    blocking_issues: list[ValidationIssue],
    warnings: list[ValidationIssue],
) -> RecommendedReviewDecision:
    if any(
        issue.code is ValidationIssueCode.LEGAL_POSTURE_DISALLOWED
        for issue in blocking_issues
    ):
        return RecommendedReviewDecision.POLICY_BLOCK
    if state is ObservationValidationState.FAILED:
        return RecommendedReviewDecision.NEEDS_MORE_EVIDENCE
    if observation.source_type is SourceRefreshTargetType.PUBLIC_JOB_BOARD:
        return RecommendedReviewDecision.NEEDS_MORE_EVIDENCE
    if any(
        issue.code
        in {
            ValidationIssueCode.SOURCE_POSTURE_LOW_CONFIDENCE,
            ValidationIssueCode.SOURCE_DOMINANCE_RISK,
        }
        for issue in warnings
    ):
        return RecommendedReviewDecision.NEEDS_MORE_EVIDENCE
    return RecommendedReviewDecision.APPROVE


def _explanation_for(
    state: ObservationValidationState,
    blocking: list[ValidationIssue],
    warnings: list[ValidationIssue],
) -> str:
    if state is ObservationValidationState.FAILED:
        return (
            f"Validation failed with {len(blocking)} blocking issue(s) and "
            f"{len(warnings)} warning(s)."
        )
    if state is ObservationValidationState.PASSED_WITH_WARNINGS:
        return f"Validation passed with {len(warnings)} warning(s)."
    return "Validation passed with no blocking issues or warnings."


def _confidence_rank(confidence: str | None) -> int:
    value = (confidence or "unknown").strip().lower()
    ranks = {
        "high": 3,
        "high_confidence": 3,
        "medium": 2,
        "moderate": 2,
        "moderate_confidence": 2,
        "low": 1,
        "low_confidence": 1,
        "unknown": 0,
        "unknown_confidence": 0,
    }
    return ranks.get(value, 0)


def _numeric_change_ratio(current_value: Any, proposed_value: Any) -> float | None:
    if not isinstance(current_value, Number) or not isinstance(proposed_value, Number):
        return None
    if isinstance(current_value, bool) or isinstance(proposed_value, bool):
        return None
    if current_value == 0:
        return None if proposed_value == 0 else 1.0
    return abs(float(proposed_value) - float(current_value)) / abs(float(current_value))


def _contradicts_existing_value(current_value: Any, proposed_value: Any) -> bool:
    if current_value is None or proposed_value is None:
        return False
    if isinstance(current_value, bool) and isinstance(proposed_value, bool):
        return current_value != proposed_value
    if isinstance(current_value, str) and isinstance(proposed_value, str):
        pairs = {
            ("present", "not_present"),
            ("not_present", "present"),
            ("active", "inactive"),
            ("inactive", "active"),
            ("fresh", "stale"),
            ("stale", "fresh"),
        }
        return (current_value.strip().lower(), proposed_value.strip().lower()) in pairs
    return False


def _checked_at(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now


__all__ = [
    "ObservationValidationResult",
    "ObservationValidationState",
    "RecommendedReviewDecision",
    "ValidationIssue",
    "ValidationIssueCode",
    "ValidationIssueSeverity",
    "stable_validation_id",
    "validate_candidate_observation",
]
