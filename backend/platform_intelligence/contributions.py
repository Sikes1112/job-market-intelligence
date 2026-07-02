"""Governed contribution intake for Layer 18D."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.institutions.repository import InstitutionRepository
from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.models import (
    ContributionEvidence,
    ContributionReview,
    DataContribution,
)
from backend.platform_intelligence.permissions import can_submit_contribution
from backend.platform_intelligence.schemas import (
    ContributionEvidenceSummary,
    ContributionReviewDecision,
    ContributionReviewQueueItem,
    ContributionReviewQueueResponse,
    ContributionReviewRequest,
    ContributionReviewSummary,
    ContributionStatus,
    ContributionSubmissionRequest,
    ContributionSubmissionSummary,
    ContributionType,
    ContributorType,
)


class ContributionPermissionError(Exception):
    pass


class ContributionNotFound(Exception):
    pass


class ContributionWorkflowError(Exception):
    pass


class ContributionService:
    def __init__(
        self,
        repository: HistoryRepository,
        institution_repository: InstitutionRepository,
    ) -> None:
        self._repo = repository
        self._institution_repo = institution_repository

    def submit_contribution(
        self,
        request: ContributionSubmissionRequest,
        *,
        current_user_id: str,
    ) -> ContributionSubmissionSummary:
        if not can_submit_contribution(
            self._institution_repo,
            user_id=current_user_id,
            contribution_type=request.contribution_type,
            institution_id=request.institution_id,
        ):
            raise ContributionPermissionError(
                "contribution type is not allowed for this user or institution"
            )

        created_at = request.created_at or datetime.now(UTC)
        row = DataContribution(
            data_contribution_id=request.contribution_id or _new_id("data_contribution"),
            contributor_type=(
                ContributorType.INSTITUTION.value
                if request.institution_id is not None
                else ContributorType.USER.value
            ),
            contributor_id=current_user_id,
            institution_id=request.institution_id,
            target_type=request.target_type.value,
            target_id=request.target_id,
            region_id=request.region_id,
            contribution_type=request.contribution_type.value,
            structured_payload=request.structured_payload,
            summary=request.summary,
            claimed_confidence=request.claimed_confidence,
            status=ContributionStatus.SUBMITTED.value,
            created_at=created_at,
        )
        self._repo.add_data_contribution(row)
        self._repo.flush()
        for evidence in request.evidence:
            self._repo.add_contribution_evidence(
                ContributionEvidence(
                    contribution_evidence_id=_new_id("contribution_evidence"),
                    contribution_id=row.data_contribution_id,
                    evidence_type=evidence.evidence_type.value,
                    url=evidence.url,
                    reference=evidence.reference,
                    description=evidence.description,
                    uploaded_reference_id=evidence.uploaded_reference_id,
                    created_at=created_at,
                )
            )
        self._repo.flush()
        return _submission_summary(row)

    def list_review_queue(
        self,
        *,
        limit: int = 100,
    ) -> ContributionReviewQueueResponse:
        return ContributionReviewQueueResponse(
            contributions=tuple(
                _review_queue_item(
                    row,
                    evidence=self._repo.list_contribution_evidence(
                        row.data_contribution_id
                    ),
                )
                for row in self._repo.list_data_contributions_for_review(limit=limit)
            )
        )

    def review_contribution(
        self,
        contribution_id: str,
        request: ContributionReviewRequest,
        *,
        reviewer_id: str,
    ) -> ContributionReviewSummary:
        contribution = self._repo.get_data_contribution(contribution_id)
        if contribution is None:
            raise ContributionNotFound(contribution_id)
        if contribution.status == ContributionStatus.SUPERSEDED.value:
            raise ContributionWorkflowError("superseded contributions cannot be reviewed")

        if request.review_decision not in {
            ContributionReviewDecision.VERIFIED,
            ContributionReviewDecision.MERGED,
        } and (
            request.canonical_update_candidate_created
            or request.canonical_update_candidate_ref
            or request.refresh_task_created
            or request.refresh_task_ref
        ):
            raise ContributionWorkflowError(
                "follow-up candidates are allowed only for verified or merged reviews"
            )

        created_at = request.created_at or datetime.now(UTC)
        candidate_created = request.canonical_update_candidate_created
        candidate_ref = request.canonical_update_candidate_ref
        refresh_created = request.refresh_task_created
        refresh_ref = request.refresh_task_ref
        if candidate_created and candidate_ref is None:
            candidate_ref = f"governed_candidate:{contribution_id}"
        if refresh_created and refresh_ref is None:
            refresh_ref = f"refresh_review:{contribution_id}"

        review = ContributionReview(
            contribution_review_id=_new_id("contribution_review"),
            contribution_id=contribution_id,
            reviewer_id=reviewer_id,
            review_decision=request.review_decision.value,
            review_notes=request.review_notes,
            canonical_update_candidate_created=candidate_created,
            canonical_update_candidate_ref=candidate_ref,
            refresh_task_created=refresh_created,
            refresh_task_ref=refresh_ref,
            created_at=created_at,
        )
        self._repo.add_contribution_review(review)
        contribution.status = _status_for_decision(request.review_decision).value
        contribution.reviewed_at = created_at
        self._repo.flush()
        return ContributionReviewSummary(
            contribution_id=contribution_id,
            review_decision=request.review_decision,
            resulting_status=ContributionStatus(contribution.status),
            canonical_update_candidate_created=candidate_created,
            refresh_task_created=refresh_created,
            created_at=created_at,
        )


def _submission_summary(row: DataContribution) -> ContributionSubmissionSummary:
    return ContributionSubmissionSummary(
        contribution_id=row.data_contribution_id,
        status=ContributionStatus(row.status),
        contribution_type=ContributionType(row.contribution_type),
        summary=row.summary,
        created_at=row.created_at,
        next_step_message=(
            "Contribution received for governed review; it will not change "
            "published intelligence until reviewed through internal workflows."
        ),
    )


def _review_queue_item(
    row: DataContribution,
    *,
    evidence: list[ContributionEvidence],
) -> ContributionReviewQueueItem:
    return ContributionReviewQueueItem(
        contribution_id=row.data_contribution_id,
        contributor_type=ContributorType(row.contributor_type),
        contributor_id=row.contributor_id,
        institution_id=row.institution_id,
        target_type=row.target_type,
        target_id=row.target_id,
        region_id=row.region_id,
        contribution_type=row.contribution_type,
        structured_payload=row.structured_payload,
        summary=row.summary,
        claimed_confidence=row.claimed_confidence,
        status=row.status,
        evidence=tuple(_evidence_summary(item) for item in evidence),
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
    )


def _evidence_summary(row: ContributionEvidence) -> ContributionEvidenceSummary:
    return ContributionEvidenceSummary(
        evidence_type=row.evidence_type,
        url=row.url,
        reference=row.reference,
        description=row.description,
        uploaded_reference_id=row.uploaded_reference_id,
        created_at=row.created_at,
    )


def _status_for_decision(decision: ContributionReviewDecision) -> ContributionStatus:
    return ContributionStatus(decision.value)


def _new_id(prefix: str) -> str:
    suffix_length = max(8, 63 - len(prefix))
    return f"{prefix}_{uuid4().hex[:suffix_length]}"
