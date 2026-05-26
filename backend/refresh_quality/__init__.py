"""Layer 13 refresh-quality control plane.

This package identifies refresh candidates, converts them to reviewable source
queue items, and detects quality regressions. It is intentionally read-only and
does not scrape, fetch, mutate canonical truth, update scores, change rankings,
or rebuild outputs.
"""

from .approval import (
    ApprovedCanonicalUpdateHandoff,
    HandoffStatus,
    prepare_approved_canonical_update_handoff,
)
from .audit import (
    RefreshQualityAuditActionType,
    RefreshQualityAuditRecord,
    audit_record_for_handoff,
    audit_record_for_review,
    audit_record_for_validation,
)
from .candidate_detection import (
    detect_refresh_candidates,
    entry_level_signal_snapshot_from_record,
    hiring_count_snapshot_from_record,
    internship_snapshot_from_record,
    presence_snapshot_from_record,
    source_refs_from_payload,
)
from .dashboard import (
    RefreshDashboardItem,
    RefreshDashboardPayload,
    build_refresh_dashboard_payload,
)
from .models import (
    LegalTermsPosture,
    QualityRegressionRecord,
    QualityRegressionSnapshot,
    QualityRegressionType,
    QualitySeverity,
    QueuePriority,
    RefreshCandidate,
    RefreshCandidateReason,
    RefreshCandidateStatus,
    RefreshFactSnapshot,
    SourceRefreshQueueItem,
    SourceRefreshQueueStatus,
    SourceRefreshTargetType,
)
from .observations import (
    CandidateObservation,
    CandidateObservationStatus,
    make_candidate_observation,
    observation_from_candidate_and_queue,
)
from .regression_detection import detect_quality_regressions
from .review import (
    HumanReviewDecision,
    HumanReviewRecord,
    record_human_review_decision,
    review_decision_for_validation,
)
from .source_queue import queue_item_from_candidate, queue_items_from_candidates
from .validation import (
    ObservationValidationResult,
    ObservationValidationState,
    RecommendedReviewDecision,
    ValidationIssue,
    ValidationIssueCode,
    ValidationIssueSeverity,
    validate_candidate_observation,
)

__all__ = [
    "ApprovedCanonicalUpdateHandoff",
    "CandidateObservation",
    "CandidateObservationStatus",
    "HandoffStatus",
    "HumanReviewDecision",
    "HumanReviewRecord",
    "LegalTermsPosture",
    "ObservationValidationResult",
    "ObservationValidationState",
    "QualityRegressionRecord",
    "QualityRegressionSnapshot",
    "QualityRegressionType",
    "QualitySeverity",
    "QueuePriority",
    "RecommendedReviewDecision",
    "RefreshCandidate",
    "RefreshCandidateReason",
    "RefreshCandidateStatus",
    "RefreshDashboardItem",
    "RefreshDashboardPayload",
    "RefreshFactSnapshot",
    "RefreshQualityAuditActionType",
    "RefreshQualityAuditRecord",
    "SourceRefreshQueueItem",
    "SourceRefreshQueueStatus",
    "SourceRefreshTargetType",
    "ValidationIssue",
    "ValidationIssueCode",
    "ValidationIssueSeverity",
    "audit_record_for_handoff",
    "audit_record_for_review",
    "audit_record_for_validation",
    "build_refresh_dashboard_payload",
    "detect_quality_regressions",
    "detect_refresh_candidates",
    "entry_level_signal_snapshot_from_record",
    "hiring_count_snapshot_from_record",
    "internship_snapshot_from_record",
    "make_candidate_observation",
    "observation_from_candidate_and_queue",
    "prepare_approved_canonical_update_handoff",
    "presence_snapshot_from_record",
    "queue_item_from_candidate",
    "queue_items_from_candidates",
    "record_human_review_decision",
    "review_decision_for_validation",
    "source_refs_from_payload",
    "validate_candidate_observation",
]
