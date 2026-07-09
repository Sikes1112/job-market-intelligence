"""Read-only Layer 30C trust explanation API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import get_session
from backend.api.envelope import lightweight_success_envelope
from backend.data_standards.service import CandidateFactNotFound, DataStandardsService
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.service import OpportunityNotFound, OpportunityService
from backend.trust.exceptions import ExceptionWorkflowService
from backend.trust.explanations import TrustExplanationService
from backend.trust.reports import latest_report_recheck_status
from backend.trust.schemas import (
    PublicExceptionStatus,
    TrustAssessmentSubjectType,
    TrustExplanation,
)

router = APIRouter(tags=["trust"])


@router.get("/trust/explanation", response_model=None)
def trust_explanation(
    subject_type: TrustAssessmentSubjectType = Query(...),
    subject_id: str = Query(..., min_length=1, max_length=128),
    session: Session = Depends(get_session),
) -> dict:
    explanation = _resolve_explanation(
        session,
        subject_type=subject_type,
        subject_id=subject_id,
    )
    return lightweight_success_envelope(data=explanation.model_dump(mode="json"))


def _resolve_explanation(
    session: Session,
    *,
    subject_type: TrustAssessmentSubjectType,
    subject_id: str,
) -> TrustExplanation:
    report_status = latest_report_recheck_status(
        session,
        subject_type=subject_type,
        subject_id=subject_id,
    )
    exception_status = ExceptionWorkflowService(
        session
    ).get_exception_status_for_subject(
        subject_type=subject_type,
        subject_id=subject_id,
    )
    safe_exception_status = (
        None
        if exception_status.public_safe_status is PublicExceptionStatus.NO_EXCEPTION
        else exception_status
    )
    if subject_type is TrustAssessmentSubjectType.OPPORTUNITY:
        try:
            payload = OpportunityService(
                OpportunityRepository(session)
            ).get_opportunity(subject_id)
        except OpportunityNotFound:
            return TrustExplanationService().not_assessed(
                subject_type=subject_type,
                subject_id=subject_id,
                report_recheck_status=report_status,
                exception_status=safe_exception_status,
            )
        if payload.trust_explanation is not None:
            return payload.trust_explanation
    if subject_type is TrustAssessmentSubjectType.DATA_STANDARD_FACT:
        try:
            detail = DataStandardsService(session).candidate_detail(subject_id)
        except CandidateFactNotFound:
            return TrustExplanationService().not_assessed(
                subject_type=subject_type,
                subject_id=subject_id,
                report_recheck_status=report_status,
                exception_status=safe_exception_status,
            )
        explanation = detail.get("candidate", {}).get("trust_explanation")
        if isinstance(explanation, dict):
            return TrustExplanation.model_validate(explanation)
    return TrustExplanationService().not_assessed(
        subject_type=subject_type,
        subject_id=subject_id,
        report_recheck_status=report_status,
        exception_status=safe_exception_status,
    )
