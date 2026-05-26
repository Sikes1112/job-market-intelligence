"""Policy-aware source refresh queue item helpers.

The queue produced here is a review list, not an execution queue. Creating an
item must never fetch external data or authorize scraping.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from .models import (
    LegalTermsPosture,
    QualitySeverity,
    QueuePriority,
    RefreshCandidate,
    RefreshCandidateReason,
    SourceRefreshQueueItem,
    SourceRefreshQueueStatus,
    SourceRefreshTargetType,
    stable_source_queue_item_id,
)

_DEFAULT_SOURCE_BY_REASON: dict[RefreshCandidateReason, SourceRefreshTargetType] = {
    RefreshCandidateReason.STALE_HIRING_COUNT: (
        SourceRefreshTargetType.COMPANY_CAREERS_PAGE
    ),
    RefreshCandidateReason.EXPIRED_INTERNSHIP_DATA: (
        SourceRefreshTargetType.COMPANY_INTERNSHIP_PAGE
    ),
    RefreshCandidateReason.OLD_COMPANY_REGION_PRESENCE_DATA: (
        SourceRefreshTargetType.COMPANY_PAGE
    ),
    RefreshCandidateReason.LOW_CONFIDENCE_SOURCE_FACT: (
        SourceRefreshTargetType.MANUAL_RESEARCH_REQUIRED
    ),
    RefreshCandidateReason.MISSING_SOURCE_FACT: (
        SourceRefreshTargetType.MANUAL_RESEARCH_REQUIRED
    ),
    RefreshCandidateReason.STALE_ENTRY_LEVEL_SIGNAL: (
        SourceRefreshTargetType.COMPANY_INTERNSHIP_PAGE
    ),
    RefreshCandidateReason.COVERAGE_GAP: (
        SourceRefreshTargetType.MANUAL_RESEARCH_REQUIRED
    ),
}


def queue_items_from_candidates(
    candidates: Iterable[RefreshCandidate],
    *,
    created_at: datetime | None = None,
) -> list[SourceRefreshQueueItem]:
    """Convert refresh candidates into deterministic reviewable queue items."""

    items = [
        queue_item_from_candidate(candidate, created_at=created_at)
        for candidate in candidates
    ]
    return sorted(items, key=lambda item: item.queue_item_id)


def queue_item_from_candidate(
    candidate: RefreshCandidate,
    *,
    source_type: SourceRefreshTargetType | None = None,
    legal_terms_posture: LegalTermsPosture | None = None,
    created_at: datetime | None = None,
) -> SourceRefreshQueueItem:
    """Create one source-refresh queue item from a refresh candidate."""

    target = (
        source_type
        or candidate.recommended_source_type
        or _DEFAULT_SOURCE_BY_REASON[candidate.reason]
    )
    posture = legal_terms_posture or default_legal_terms_posture(target)
    _validate_source_posture(target, posture)
    status = queue_status_for_posture(posture)

    return SourceRefreshQueueItem(
        queue_item_id=stable_source_queue_item_id(
            candidate_key=candidate.candidate_key,
            source_type=target,
        ),
        candidate_key=candidate.candidate_key,
        entity_type=candidate.entity_type,
        entity_id=candidate.entity_id,
        source_type=target,
        priority=priority_for_candidate(candidate),
        legal_terms_posture=posture,
        reason=candidate.reason,
        status=status,
        explanation=_queue_explanation(candidate, target, posture),
        created_at=created_at,
    )


def default_legal_terms_posture(
    source_type: SourceRefreshTargetType,
) -> LegalTermsPosture:
    """Return conservative default legal posture for a source target type."""

    if source_type is SourceRefreshTargetType.MANUAL_RESEARCH_REQUIRED:
        return LegalTermsPosture.MANUAL_ONLY
    if source_type in {
        SourceRefreshTargetType.GOVERNMENT_OPEN_DATASET,
        SourceRefreshTargetType.UNIVERSITY_COOP_PUBLIC_EMPLOYER_LIST,
    }:
        return LegalTermsPosture.PUBLIC_DATASET_ALLOWED
    if source_type is SourceRefreshTargetType.PUBLIC_JOB_BOARD:
        return LegalTermsPosture.TERMS_REVIEW_REQUIRED
    return LegalTermsPosture.UNKNOWN


def queue_status_for_posture(
    posture: LegalTermsPosture,
) -> SourceRefreshQueueStatus:
    if posture is LegalTermsPosture.DISALLOWED:
        return SourceRefreshQueueStatus.DISALLOWED
    if posture is LegalTermsPosture.TERMS_REVIEW_REQUIRED:
        return SourceRefreshQueueStatus.TERMS_REVIEW_REQUIRED
    if posture is LegalTermsPosture.MANUAL_ONLY:
        return SourceRefreshQueueStatus.MANUAL_ONLY
    return SourceRefreshQueueStatus.PENDING_REVIEW


def priority_for_candidate(candidate: RefreshCandidate) -> QueuePriority:
    if candidate.severity is QualitySeverity.CRITICAL:
        return QueuePriority.URGENT
    if candidate.severity is QualitySeverity.HIGH:
        return QueuePriority.HIGH
    if candidate.severity is QualitySeverity.MEDIUM:
        return QueuePriority.MEDIUM
    return QueuePriority.LOW


def _validate_source_posture(
    source_type: SourceRefreshTargetType,
    posture: LegalTermsPosture,
) -> None:
    if (
        source_type is SourceRefreshTargetType.PUBLIC_JOB_BOARD
        and posture is LegalTermsPosture.PUBLIC_DATASET_ALLOWED
    ):
        raise ValueError(
            "public job board queue items require terms review or a disallowed "
            "posture; they cannot be treated as public datasets"
        )


def _queue_explanation(
    candidate: RefreshCandidate,
    source_type: SourceRefreshTargetType,
    posture: LegalTermsPosture,
) -> str:
    return (
        f"Review {source_type.value} for candidate {candidate.candidate_key}; "
        f"legal posture is {posture.value}. This item is not executable scraping."
    )


__all__ = [
    "default_legal_terms_posture",
    "priority_for_candidate",
    "queue_item_from_candidate",
    "queue_items_from_candidates",
    "queue_status_for_posture",
]
