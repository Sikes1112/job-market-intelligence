"""Refresh-quality dashboard payload builders.

The dashboard is a read-only summary over supplied Layer 13 records. It does
not query databases, mutate review state, apply canonical updates, invalidate
caches, or rebuild outputs.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .approval import ApprovedCanonicalUpdateHandoff
from .audit import RefreshQualityAuditActionType, RefreshQualityAuditRecord
from .models import (
    QualityRegressionRecord,
    QualityRegressionType,
    RefreshCandidate,
    RefreshCandidateReason,
    SourceRefreshQueueItem,
)
from .observations import CandidateObservation, CandidateObservationStatus
from .review import HumanReviewDecision, HumanReviewRecord
from .validation import ObservationValidationResult, RecommendedReviewDecision


class RefreshDashboardItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    severity: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("item_id", "entity_type", "entity_id", "label", "severity", "status")
    @classmethod
    def _strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class RefreshDashboardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    generated_at: datetime
    summary_counts: dict[str, int]
    stale_regions: tuple[RefreshDashboardItem, ...] = Field(default_factory=tuple)
    stale_companies: tuple[RefreshDashboardItem, ...] = Field(default_factory=tuple)
    failed_refresh_jobs: tuple[RefreshDashboardItem, ...] = Field(default_factory=tuple)
    low_confidence_facts: tuple[RefreshDashboardItem, ...] = Field(default_factory=tuple)
    coverage_gaps: tuple[RefreshDashboardItem, ...] = Field(default_factory=tuple)
    audit_warnings: tuple[RefreshDashboardItem, ...] = Field(default_factory=tuple)
    refresh_queue_items: tuple[RefreshDashboardItem, ...] = Field(default_factory=tuple)
    pending_review_items: tuple[RefreshDashboardItem, ...] = Field(default_factory=tuple)
    approved_update_handoffs: tuple[RefreshDashboardItem, ...] = Field(default_factory=tuple)
    rejected_observations: tuple[RefreshDashboardItem, ...] = Field(default_factory=tuple)
    policy_blocked_observations: tuple[RefreshDashboardItem, ...] = Field(default_factory=tuple)
    quality_regressions: tuple[RefreshDashboardItem, ...] = Field(default_factory=tuple)

    @field_validator("generated_at")
    @classmethod
    def _generated_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return value


def build_refresh_dashboard_payload(
    *,
    candidates: Iterable[RefreshCandidate] = (),
    queue_items: Iterable[SourceRefreshQueueItem] = (),
    regressions: Iterable[QualityRegressionRecord] = (),
    observations: Iterable[CandidateObservation] = (),
    validations: Iterable[ObservationValidationResult] = (),
    reviews: Iterable[HumanReviewRecord] = (),
    handoffs: Iterable[ApprovedCanonicalUpdateHandoff] = (),
    audit_records: Iterable[RefreshQualityAuditRecord] = (),
    generated_at: datetime | None = None,
) -> RefreshDashboardPayload:
    """Build a read-only dashboard payload from supplied records."""

    generated_at = _checked_at(generated_at)
    candidate_list = tuple(candidates)
    queue_item_list = tuple(queue_items)
    regression_list = tuple(regressions)
    observation_list = tuple(observations)
    validation_list = tuple(validations)
    review_list = tuple(reviews)
    handoff_list = tuple(handoffs)
    audit_list = tuple(audit_records)

    stale_regions = _stale_items(candidate_list, entity_scope="region")
    stale_companies = _stale_items(candidate_list, entity_scope="company")
    failed_refresh_jobs = [
        _regression_item(regression, label="Repeated refresh failure")
        for regression in regression_list
        if regression.regression_type is QualityRegressionType.REPEATED_REFRESH_FAILURE
    ]
    low_confidence_facts = [
        _candidate_item(candidate, label="Low-confidence fact")
        for candidate in candidate_list
        if candidate.reason is RefreshCandidateReason.LOW_CONFIDENCE_SOURCE_FACT
    ]
    coverage_gaps = [
        _candidate_item(candidate, label="Coverage gap")
        for candidate in candidate_list
        if candidate.reason is RefreshCandidateReason.COVERAGE_GAP
    ] + [
        _regression_item(regression, label="Coverage gap worsened")
        for regression in regression_list
        if regression.regression_type is QualityRegressionType.COVERAGE_GAP_WORSENED
    ]
    validation_by_observation = {
        validation.observation_id: validation for validation in validation_list
    }
    reviews_by_observation = {review.observation_id: review for review in review_list}

    pending_review_items = [
        _observation_item(
            observation,
            label="Pending review",
            validation=validation_by_observation.get(observation.observation_id),
        )
        for observation in observation_list
        if observation.observation_id not in reviews_by_observation
        and observation.observation_status
        in {
            CandidateObservationStatus.PENDING_VALIDATION,
            CandidateObservationStatus.VALIDATED,
            CandidateObservationStatus.NEEDS_MORE_EVIDENCE,
        }
    ]
    approved_update_handoffs = [
        _handoff_item(handoff) for handoff in handoff_list
    ]
    rejected_observations = [
        _review_item(review, label="Rejected observation")
        for review in review_list
        if review.decision is HumanReviewDecision.REJECTED
    ] + [
        _observation_item(observation, label="Rejected observation")
        for observation in observation_list
        if observation.observation_status is CandidateObservationStatus.REJECTED
    ]
    policy_blocked_observations = [
        _review_item(review, label="Policy-blocked observation")
        for review in review_list
        if review.decision is HumanReviewDecision.POLICY_BLOCKED
    ] + [
        _validation_item(validation, label="Policy-blocked validation")
        for validation in validation_list
        if validation.recommended_review_decision
        is RecommendedReviewDecision.POLICY_BLOCK
    ]
    quality_regressions = [
        _regression_item(regression, label="Quality regression")
        for regression in regression_list
    ]
    audit_warnings = [
        _audit_item(record)
        for record in audit_list
        if _is_audit_warning(record)
    ]
    refresh_queue_items = [
        _queue_item(queue_item)
        for queue_item in queue_item_list
        if queue_item.status.value in {
            "pending_review",
            "manual_only",
            "terms_review_required",
        }
    ]
    pending_review_items = sorted(
        [*pending_review_items, *refresh_queue_items],
        key=lambda item: item.item_id,
    )

    sections = {
        "stale_regions": tuple(sorted(stale_regions, key=lambda item: item.item_id)),
        "stale_companies": tuple(sorted(stale_companies, key=lambda item: item.item_id)),
        "failed_refresh_jobs": tuple(sorted(failed_refresh_jobs, key=lambda item: item.item_id)),
        "low_confidence_facts": tuple(sorted(low_confidence_facts, key=lambda item: item.item_id)),
        "coverage_gaps": tuple(sorted(coverage_gaps, key=lambda item: item.item_id)),
        "audit_warnings": tuple(sorted(audit_warnings, key=lambda item: item.item_id)),
        "refresh_queue_items": tuple(
            sorted(refresh_queue_items, key=lambda item: item.item_id)
        ),
        "pending_review_items": tuple(pending_review_items),
        "approved_update_handoffs": tuple(
            sorted(approved_update_handoffs, key=lambda item: item.item_id)
        ),
        "rejected_observations": tuple(
            sorted(rejected_observations, key=lambda item: item.item_id)
        ),
        "policy_blocked_observations": tuple(
            sorted(policy_blocked_observations, key=lambda item: item.item_id)
        ),
        "quality_regressions": tuple(
            sorted(quality_regressions, key=lambda item: item.item_id)
        ),
    }
    return RefreshDashboardPayload(
        generated_at=generated_at,
        summary_counts={key: len(value) for key, value in sections.items()},
        **sections,
    )


def _stale_items(
    candidates: tuple[RefreshCandidate, ...],
    *,
    entity_scope: str,
) -> list[RefreshDashboardItem]:
    stale_reasons = {
        RefreshCandidateReason.STALE_HIRING_COUNT,
        RefreshCandidateReason.EXPIRED_INTERNSHIP_DATA,
        RefreshCandidateReason.OLD_COMPANY_REGION_PRESENCE_DATA,
        RefreshCandidateReason.STALE_ENTRY_LEVEL_SIGNAL,
    }
    return [
        _candidate_item(candidate, label=f"Stale {entity_scope}")
        for candidate in candidates
        if candidate.reason in stale_reasons
        and entity_scope in candidate.entity_type
    ]


def _candidate_item(candidate: RefreshCandidate, *, label: str) -> RefreshDashboardItem:
    return RefreshDashboardItem(
        item_id=candidate.candidate_key,
        entity_type=candidate.entity_type,
        entity_id=candidate.entity_id,
        label=label,
        severity=candidate.severity.value,
        status=candidate.status.value,
        details={
            "fact_type": candidate.fact_type,
            "reason": candidate.reason.value,
            "explanation": candidate.explanation,
        },
    )


def _queue_item(queue_item: SourceRefreshQueueItem) -> RefreshDashboardItem:
    return RefreshDashboardItem(
        item_id=queue_item.queue_item_id,
        entity_type=queue_item.entity_type,
        entity_id=queue_item.entity_id,
        label="Refresh queue review",
        severity=queue_item.priority.value,
        status=queue_item.status.value,
        details={
            "candidate_key": queue_item.candidate_key,
            "source_type": queue_item.source_type.value,
            "legal_terms_posture": queue_item.legal_terms_posture.value,
            "reason": queue_item.reason.value,
        },
    )


def _regression_item(
    regression: QualityRegressionRecord,
    *,
    label: str,
) -> RefreshDashboardItem:
    return RefreshDashboardItem(
        item_id=regression.regression_id,
        entity_type=regression.entity_type,
        entity_id=regression.entity_id,
        label=label,
        severity=regression.severity.value,
        status=regression.regression_type.value,
        details={
            "explanation": regression.explanation,
            "recommended_action": regression.recommended_action,
            "human_review_required": regression.human_review_required,
        },
    )


def _observation_item(
    observation: CandidateObservation,
    *,
    label: str,
    validation: ObservationValidationResult | None = None,
) -> RefreshDashboardItem:
    return RefreshDashboardItem(
        item_id=observation.observation_id,
        entity_type=observation.entity_type,
        entity_id=observation.entity_id,
        label=label,
        severity=None,
        status=observation.observation_status.value,
        details={
            "fact_type": observation.fact_type,
            "source_type": observation.source_type.value,
            "legal_terms_posture": observation.legal_terms_posture.value,
            "validation_state": validation.state.value if validation else None,
        },
    )


def _validation_item(
    validation: ObservationValidationResult,
    *,
    label: str,
) -> RefreshDashboardItem:
    return RefreshDashboardItem(
        item_id=validation.validation_id,
        entity_type="candidate_observation",
        entity_id=validation.observation_id,
        label=label,
        severity="high",
        status=validation.state.value,
        details={
            "recommended_review_decision": (
                validation.recommended_review_decision.value
            ),
            "blocking_issue_count": len(validation.blocking_issues),
            "warning_count": len(validation.warnings),
        },
    )


def _review_item(review: HumanReviewRecord, *, label: str) -> RefreshDashboardItem:
    return RefreshDashboardItem(
        item_id=review.review_id,
        entity_type="candidate_observation",
        entity_id=review.observation_id,
        label=label,
        severity=None,
        status=review.decision.value,
        details={
            "validation_id": review.validation_id,
            "reviewer_id": review.reviewer_id,
            "reviewer_note": review.reviewer_note,
        },
    )


def _handoff_item(handoff: ApprovedCanonicalUpdateHandoff) -> RefreshDashboardItem:
    return RefreshDashboardItem(
        item_id=handoff.handoff_id,
        entity_type=handoff.target_entity_type,
        entity_id=handoff.target_entity_id,
        label="Approved update handoff",
        severity=None,
        status=handoff.status.value,
        details={
            "approved_observation_id": handoff.approved_observation_id,
            "review_decision_id": handoff.review_decision_id,
            "target_fact_type": handoff.target_fact_type,
            "output_rebuild_needed": handoff.output_rebuild_needed,
        },
    )


def _audit_item(record: RefreshQualityAuditRecord) -> RefreshDashboardItem:
    return RefreshDashboardItem(
        item_id=record.audit_id,
        entity_type="refresh_quality_audit",
        entity_id=record.observation_id or record.audit_id,
        label="Audit warning",
        severity="medium",
        status=record.action_type.value,
        details={
            "review_id": record.review_id,
            "handoff_id": record.handoff_id,
            "validation_result_summary": record.validation_result_summary,
        },
    )


def _is_audit_warning(record: RefreshQualityAuditRecord) -> bool:
    summary = record.validation_result_summary
    return (
        int(summary.get("warning_count") or 0) > 0
        or record.action_type
        in {
            RefreshQualityAuditActionType.POLICY_BLOCKED,
            RefreshQualityAuditActionType.NEEDS_MORE_EVIDENCE,
            RefreshQualityAuditActionType.REVIEW_REJECTED,
        }
    )


def _checked_at(generated_at: datetime | None) -> datetime:
    if generated_at is None:
        return datetime.now(UTC)
    if generated_at.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    return generated_at


__all__ = [
    "RefreshDashboardItem",
    "RefreshDashboardPayload",
    "build_refresh_dashboard_payload",
]
