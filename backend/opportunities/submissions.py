"""Employer submission and internal review workflow for Layer 23B."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.opportunities.models import (
    OpportunityReviewActionRecord,
    OpportunitySubmission,
)
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.schemas import (
    EmployerInfluenceMetadataCreate,
    OpportunityCreate,
    OpportunityReviewAction,
    OpportunityReviewRequest,
    OpportunityReviewStatus,
    OpportunitySubmissionListResponse,
    OpportunitySubmissionPayload,
    OpportunitySubmissionRequest,
    OpportunitySubmissionReviewSummary,
    OpportunitySubmissionStatus,
    OpportunityTrustLabel,
)
from backend.opportunities.service import OpportunityNotFound, OpportunityService
from backend.opportunities.verification import is_opportunity_expired


class OpportunitySubmissionNotFound(Exception):
    pass


class OpportunityReviewWorkflowError(ValueError):
    pass


class OpportunitySubmissionService:
    def __init__(self, repository: OpportunityRepository) -> None:
        self._repo = repository
        self._opportunity_service = OpportunityService(repository)

    def submit_opportunity(
        self,
        request: OpportunitySubmissionRequest,
    ) -> OpportunitySubmissionPayload:
        submitted_at = request.submitted_at or datetime.now(UTC)
        shared_url = request.application_url or request.source_url
        assert shared_url is not None
        source_url = request.source_url or shared_url
        application_url = request.application_url or shared_url

        opportunity = self._opportunity_service.create_opportunity(
            OpportunityCreate(
                opportunity_id=request.opportunity_id,
                employer_id=request.employer_id,
                employer_name=request.employer_name,
                program_name=request.program_name,
                program_type=request.program_type,
                location_mode=request.location_mode,
                seniority_level=request.seniority_level,
                eligibility_summary=request.eligibility_summary,
                application_url=application_url,
                source_url=source_url,
                source_type=request.source_type,
                application_open_date=request.application_open_date,
                application_deadline=request.application_deadline,
                expires_at=request.expires_at,
                compensation_min=request.compensation_min,
                compensation_max=request.compensation_max,
                compensation_disclosed=request.compensation_disclosed,
                trust_label=OpportunityTrustLabel.PARTNER_SUBMITTED,
                review_status=OpportunityReviewStatus.PENDING_REVIEW,
                employer_influence=EmployerInfluenceMetadataCreate(
                    partner_submitted=True,
                    paid_partner=request.paid_partner,
                    ranking_influence_allowed=False,
                    submitted_by_partner_id=request.partner_organization_id,
                    paid_partner_label=request.paid_partner_label,
                ),
                region_bindings=request.region_bindings,
                role_family_bindings=request.role_family_bindings,
                created_at=submitted_at,
            )
        )
        submission = OpportunitySubmission(
            opportunity_submission_id=request.submission_id or _new_id("opp_submission"),
            opportunity_id=opportunity.id,
            status=OpportunitySubmissionStatus.PENDING_REVIEW.value,
            submitter_contact=request.submitter_contact,
            submitted_by=request.submitted_by,
            submission_source=request.submission_source,
            partner_organization_id=request.partner_organization_id,
            partner_organization_name=request.partner_organization_name,
            paid_partner=request.paid_partner,
            paid_partner_label=request.paid_partner_label,
            raw_submission_json=request.model_dump(mode="json"),
            submitted_at=submitted_at,
            created_at=submitted_at,
        )
        self._repo.add_submission(submission)
        self._repo.flush()
        return self._submission_payload(submission)

    def get_submission(self, submission_id: str) -> OpportunitySubmissionPayload:
        submission = self._repo.get_submission(submission_id)
        if submission is None:
            raise OpportunitySubmissionNotFound(submission_id)
        return self._submission_payload(submission)

    def list_submissions(
        self,
        *,
        status: OpportunitySubmissionStatus | None = None,
        limit: int = 100,
    ) -> OpportunitySubmissionListResponse:
        submissions = []
        for row in self._repo.list_submissions(limit=limit):
            payload = self._submission_payload(row)
            if status is not None and payload.status != status:
                continue
            submissions.append(payload)
            if len(submissions) >= limit:
                break
        return OpportunitySubmissionListResponse(submissions=tuple(submissions))

    def review_submission(
        self,
        submission_id: str,
        request: OpportunityReviewRequest,
    ) -> OpportunitySubmissionPayload:
        submission = self._repo.get_submission(submission_id)
        if submission is None:
            raise OpportunitySubmissionNotFound(submission_id)
        opportunity = self._repo.get_opportunity(submission.opportunity_id)
        if opportunity is None:
            raise OpportunityNotFound(submission.opportunity_id)

        trust_label, review_status = _review_result(request.review_action)
        if request.review_action in {
            OpportunityReviewAction.APPROVE_AS_VERIFIED,
            OpportunityReviewAction.APPROVE_AS_SOURCE_CHECKED,
        } and is_opportunity_expired(opportunity, now=request.reviewed_at):
            raise OpportunityReviewWorkflowError(
                "expired opportunities cannot be approved as verified or source checked"
            )

        reviewed_at = request.reviewed_at or datetime.now(UTC)
        review = OpportunityReviewActionRecord(
            opportunity_review_action_id=_new_id("opp_review_action"),
            submission_id=submission.opportunity_submission_id,
            opportunity_id=submission.opportunity_id,
            review_action=request.review_action.value,
            resulting_trust_label=trust_label.value,
            resulting_review_status=review_status.value,
            ranking_influence_allowed=False,
            reviewer_id=request.reviewer_id,
            reviewer_name=request.reviewer_name,
            review_note=request.review_note,
            correction_reason=request.correction_reason,
            source_url_checked=request.source_url_checked,
            official_employer_url=request.official_employer_url,
            reviewed_at=reviewed_at,
            created_at=reviewed_at,
        )
        self._repo.add_review_action(review)
        self._repo.flush()
        return self._submission_payload(submission)

    def _submission_payload(
        self,
        submission: OpportunitySubmission,
    ) -> OpportunitySubmissionPayload:
        latest_review = self._repo.latest_review_action_for_submission(
            submission.opportunity_submission_id
        )
        return OpportunitySubmissionPayload(
            submission_id=submission.opportunity_submission_id,
            opportunity_id=submission.opportunity_id,
            status=_submission_status(latest_review),
            submitted_at=submission.submitted_at,
            submitter_contact=submission.submitter_contact,
            submitted_by=submission.submitted_by,
            submission_source=submission.submission_source,
            partner_organization_id=submission.partner_organization_id,
            partner_organization_name=submission.partner_organization_name,
            paid_partner=submission.paid_partner,
            paid_partner_label=submission.paid_partner_label,
            opportunity=self._opportunity_service.get_opportunity(submission.opportunity_id),
            latest_review=(
                _review_summary(latest_review) if latest_review is not None else None
            ),
        )


def _review_result(
    action: OpportunityReviewAction,
) -> tuple[OpportunityTrustLabel, OpportunityReviewStatus]:
    if action is OpportunityReviewAction.APPROVE_AS_VERIFIED:
        return OpportunityTrustLabel.VERIFIED, OpportunityReviewStatus.APPROVED
    if action is OpportunityReviewAction.APPROVE_AS_SOURCE_CHECKED:
        return OpportunityTrustLabel.SOURCE_CHECKED, OpportunityReviewStatus.SOURCE_CHECKED
    if action is OpportunityReviewAction.MARK_UNVERIFIED:
        return OpportunityTrustLabel.UNVERIFIED, OpportunityReviewStatus.PENDING_REVIEW
    if action is OpportunityReviewAction.MARK_EXPIRED:
        return OpportunityTrustLabel.EXPIRED, OpportunityReviewStatus.EXPIRED
    if action is OpportunityReviewAction.REJECT:
        return OpportunityTrustLabel.REJECTED, OpportunityReviewStatus.REJECTED
    if action is OpportunityReviewAction.REQUEST_CORRECTION:
        return OpportunityTrustLabel.UNVERIFIED, OpportunityReviewStatus.NEEDS_CORRECTION
    raise OpportunityReviewWorkflowError(f"unsupported review action: {action!r}")


def _submission_status(
    latest_review: OpportunityReviewActionRecord | None,
) -> OpportunitySubmissionStatus:
    if latest_review is None:
        return OpportunitySubmissionStatus.PENDING_REVIEW
    if latest_review.review_action == OpportunityReviewAction.REJECT.value:
        return OpportunitySubmissionStatus.REJECTED
    if latest_review.review_action == OpportunityReviewAction.MARK_EXPIRED.value:
        return OpportunitySubmissionStatus.EXPIRED
    if latest_review.review_action == OpportunityReviewAction.REQUEST_CORRECTION.value:
        return OpportunitySubmissionStatus.NEEDS_CORRECTION
    return OpportunitySubmissionStatus.REVIEWED


def _review_summary(
    row: OpportunityReviewActionRecord,
) -> OpportunitySubmissionReviewSummary:
    return OpportunitySubmissionReviewSummary(
        review_action=row.review_action,
        resulting_trust_label=row.resulting_trust_label,
        resulting_review_status=row.resulting_review_status,
        reviewed_at=row.reviewed_at,
        correction_reason=row.correction_reason,
        source_url_checked=row.source_url_checked,
        official_employer_url=row.official_employer_url,
    )


def _new_id(prefix: str) -> str:
    suffix_length = max(8, 63 - len(prefix))
    return f"{prefix}_{uuid4().hex[:suffix_length]}"
