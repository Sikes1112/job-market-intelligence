"""Layer 27 data standards and partner submission API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.api.dependencies import (
    CurrentAdmin,
    get_session,
    require_admin_mutation_access,
    require_data_review_access,
)
from backend.api.envelope import NOT_FOUND, VALIDATION_ERROR, lightweight_success_envelope
from backend.data_standards.schemas import (
    CandidateReviewRequest,
    CanonicalMergeRequest,
)
from backend.data_standards.service import (
    CandidateFactNotFound,
    CandidateReviewWorkflowError,
    CanonicalMergeBlocked,
    DataStandardsService,
    PartnerSubmissionNotFound,
    PartnerSubmissionReviewLifecycleError,
    PartnerSubmissionValidationFailed,
)

router = APIRouter(tags=["data-standards"])


@router.get("/data-standards/definitions", response_model=None)
def data_standard_definitions() -> dict:
    payload = DataStandardsService().standard_definitions()
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/data-standards/partner-schema", response_model=None)
def data_standard_partner_schema() -> dict:
    payload = DataStandardsService().partner_schema()
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/data-standards/partners", response_model=None)
def data_standard_partners() -> dict:
    payload = DataStandardsService().partner_registry()
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/data-standards/partners/{partner_id}", response_model=None)
def data_standard_partner_detail(partner_id: str) -> Any:
    partner = DataStandardsService().partner_by_id(partner_id)
    if partner is None:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "data": None,
                "metadata": {"state": "failed", "warnings": []},
                "error": {
                    "code": NOT_FOUND,
                    "message": "Partner registry record not found.",
                },
            },
        )
    return lightweight_success_envelope(data=partner.model_dump(mode="json"))


@router.get("/data-standards/quality-labels", response_model=None)
def data_standard_quality_labels() -> dict:
    payload = DataStandardsService().quality_labels()
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/data-standards/governance-framework", response_model=None)
def data_standard_governance_framework() -> dict:
    payload = DataStandardsService().governance_framework()
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.post("/data-standards/quality-labels/evaluate", response_model=None)
def evaluate_data_quality_label(
    payload: dict[str, Any] = Body(...),
) -> Any:
    try:
        result = DataStandardsService().evaluate_quality_label(payload)
    except (KeyError, ValidationError, ValueError):
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "data": None,
                "metadata": {"state": "failed", "warnings": []},
                "error": {
                    "code": VALIDATION_ERROR,
                    "message": "Data quality label evaluation request is invalid.",
                },
            },
        )
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.post("/data-standards/partner-submissions/validate", response_model=None)
def validate_partner_submission(
    payload: dict[str, Any] = Body(...),
    _admin: CurrentAdmin = Depends(require_data_review_access),
) -> dict:
    result = DataStandardsService().validate_submission(payload)
    return lightweight_success_envelope(
        data=result.model_dump(mode="json"),
        state="partial" if result.errors else "fresh",
    )


@router.post("/data-standards/partner-submissions", response_model=None)
def create_partner_submission(
    payload: dict[str, Any] = Body(...),
    _admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
) -> Any:
    service = DataStandardsService(session)
    try:
        submission = service.create_submission(payload)
    except PartnerSubmissionValidationFailed as exc:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "data": exc.result.model_dump(mode="json"),
                "metadata": {
                    "state": "failed",
                    "warnings": [
                        warning.model_dump(mode="json")
                        for warning in exc.result.warnings
                    ],
                },
                "error": {
                    "code": VALIDATION_ERROR,
                    "message": "Partner submission failed Layer 27 validation.",
                },
            },
        )
    return lightweight_success_envelope(data=submission.model_dump(mode="json"))


@router.post(
    "/data-standards/partner-submissions/{submission_id}/candidates",
    response_model=None,
)
def create_partner_submission_candidates(
    submission_id: str,
    _admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
) -> Any:
    service = DataStandardsService(session)
    try:
        payload = service.create_candidates_from_submission(submission_id)
    except PartnerSubmissionNotFound:
        return _not_found("Partner submission not found.")
    except PartnerSubmissionReviewLifecycleError as exc:
        return _validation_error(str(exc))
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get(
    "/data-standards/partner-submissions/{submission_id}/candidates",
    response_model=None,
)
def list_partner_submission_candidates(
    submission_id: str,
    _admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
) -> Any:
    service = DataStandardsService(session)
    try:
        payload = service.list_candidates_for_submission(submission_id)
    except PartnerSubmissionNotFound:
        return _not_found("Partner submission not found.")
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/data-standards/review/candidates", response_model=None)
def list_data_standard_review_candidates(
    limit: int = 100,
    _admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
) -> Any:
    bounded_limit = max(1, min(limit, 500))
    payload = DataStandardsService(session).list_review_candidates(limit=bounded_limit)
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/data-standards/candidates/{candidate_fact_id}", response_model=None)
def get_candidate_fact_detail(
    candidate_fact_id: str,
    _admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
) -> Any:
    service = DataStandardsService(session)
    try:
        payload = service.candidate_detail(candidate_fact_id)
    except CandidateFactNotFound:
        return _not_found("Candidate fact not found.")
    return lightweight_success_envelope(data=payload)


@router.post("/data-standards/candidates/{candidate_fact_id}/review", response_model=None)
def review_candidate_fact(
    candidate_fact_id: str,
    request: CandidateReviewRequest,
    _admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
) -> Any:
    service = DataStandardsService(session)
    try:
        payload = service.review_candidate_fact(candidate_fact_id, request)
    except CandidateFactNotFound:
        return _not_found("Candidate fact not found.")
    except CandidateReviewWorkflowError as exc:
        return _validation_error(str(exc))
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.post(
    "/data-standards/candidates/{candidate_fact_id}/merge-preview",
    response_model=None,
)
def preview_candidate_merge(
    candidate_fact_id: str,
    _admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
) -> Any:
    service = DataStandardsService(session)
    try:
        payload = service.preview_canonical_merge(candidate_fact_id)
    except CandidateFactNotFound:
        return _not_found("Candidate fact not found.")
    return lightweight_success_envelope(
        data=payload.model_dump(mode="json"),
        state="fresh" if payload.can_merge else "blocked",
    )


@router.post("/data-standards/candidates/{candidate_fact_id}/merge", response_model=None)
def merge_candidate_fact(
    candidate_fact_id: str,
    request: CanonicalMergeRequest,
    _admin: CurrentAdmin = Depends(require_admin_mutation_access),
    session: Session = Depends(get_session),
) -> Any:
    service = DataStandardsService(session)
    try:
        payload = service.merge_candidate_fact(candidate_fact_id, request)
    except CandidateFactNotFound:
        return _not_found("Candidate fact not found.")
    except CanonicalMergeBlocked as exc:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "data": exc.preview.model_dump(mode="json"),
                "metadata": {"state": "blocked", "warnings": []},
                "error": {
                    "code": VALIDATION_ERROR,
                    "message": "Candidate fact is not eligible for canonical merge.",
                },
            },
        )
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "status": "error",
            "data": None,
            "metadata": {"state": "failed", "warnings": []},
            "error": {
                "code": NOT_FOUND,
                "message": message,
            },
        },
    )


def _validation_error(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "status": "error",
            "data": None,
            "metadata": {"state": "failed", "warnings": []},
            "error": {
                "code": VALIDATION_ERROR,
                "message": message,
            },
        },
    )
