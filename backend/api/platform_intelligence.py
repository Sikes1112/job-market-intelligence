"""Read-only Layer 18 platform intelligence API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import (
    CurrentAdmin,
    CurrentUser,
    get_current_user,
    get_session,
    require_data_review_access,
)
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.api.geographic_identity import require_canonical_region_id
from backend.geography.exceptions import GeographicResolutionError
from backend.institutions.repository import InstitutionRepository
from backend.platform_intelligence.contributions import (
    ContributionNotFound,
    ContributionPermissionError,
    ContributionService,
    ContributionWorkflowError,
)
from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.indices import MarketIndexService
from backend.platform_intelligence.predictive_exports import (
    export_predictive_observations,
)
from backend.platform_intelligence.predictive_signals import PredictiveSignalService
from backend.platform_intelligence.reports import BenchmarkReportService
from backend.platform_intelligence.schemas import (
    ContributionReviewRequest,
    ContributionSubmissionRequest,
)
from backend.platform_intelligence.snapshots import HistoricalSnapshotService
from backend.predictive.reports import PredictiveReportBuilder

router = APIRouter(tags=["platform-intelligence"])


@router.get("/platform/history/regions/{region_id}")
def region_history(
    region_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict:
    try:
        region_id = require_canonical_region_id(session, region_id)
    except GeographicResolutionError:
        return JSONResponse(
            status_code=404,
            content=error_envelope(code=NOT_FOUND, message="Region not found."),
        )
    service = HistoricalSnapshotService(HistoryRepository(session))
    payload = service.region_history(region_id, limit=limit)
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/platform/history/companies/{company_id}")
def company_history(
    company_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict:
    service = HistoricalSnapshotService(HistoryRepository(session))
    payload = service.company_history(company_id, limit=limit)
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/platform/signals/regions/{region_id}")
def region_signals(
    region_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict:
    try:
        region_id = require_canonical_region_id(session, region_id)
    except GeographicResolutionError:
        return JSONResponse(
            status_code=404,
            content=error_envelope(code=NOT_FOUND, message="Region not found."),
        )
    service = PredictiveSignalService(HistoryRepository(session))
    payload = service.active_region_signals(region_id, limit=limit)
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/platform/indices")
def list_market_indices(
    session: Session = Depends(get_session),
) -> dict:
    service = MarketIndexService(HistoryRepository(session))
    return lightweight_success_envelope(
        data={"indices": [row.model_dump(mode="json") for row in service.list_indices()]}
    )


@router.get("/platform/indices/{index_key}/scores")
def list_market_index_scores(
    index_key: str,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict:
    service = MarketIndexService(HistoryRepository(session))
    payload = service.list_index_scores(index_key, limit=limit)
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/platform/reports")
def list_benchmark_reports(
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict:
    service = BenchmarkReportService(HistoryRepository(session))
    payload = service.list_public_reports(limit=limit)
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/platform/reports/{report_key}")
def get_benchmark_report(
    report_key: str,
    session: Session = Depends(get_session),
):
    service = BenchmarkReportService(HistoryRepository(session))
    payload = service.public_report_detail(report_key)
    if payload is None:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Published benchmark report not found: {report_key!r}",
            ),
        )
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/platform/predictive/reports")
def predictive_reports(
    region_id: tuple[str, ...] = Query(default=()),
    company_id: tuple[str, ...] = Query(default=()),
    limit_per_subject: int = Query(default=500, ge=1, le=1_000),
    session: Session = Depends(get_session),
) -> dict:
    canonical_region_ids: list[str] = []
    try:
        canonical_region_ids = [require_canonical_region_id(session, value) for value in region_id]
    except GeographicResolutionError:
        return JSONResponse(
            status_code=404,
            content=error_envelope(code=NOT_FOUND, message="Region not found."),
        )
    repository = HistoryRepository(session)
    observations = export_predictive_observations(
        repository,
        region_ids=tuple(dict.fromkeys(canonical_region_ids)),
        company_ids=company_id,
        limit_per_subject=limit_per_subject,
    )
    payload = PredictiveReportBuilder().build_report(observations)
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.post("/platform/contributions")
def submit_data_contribution(
    request: ContributionSubmissionRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    service = ContributionService(
        HistoryRepository(session),
        InstitutionRepository(session),
    )
    try:
        payload = service.submit_contribution(
            request,
            current_user_id=current.user.user_id,
        )
    except ContributionPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/platform/contributions/review")
def list_data_contributions_for_review(
    limit: int = Query(default=100, ge=1, le=500),
    _admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
) -> dict:
    service = ContributionService(
        HistoryRepository(session),
        InstitutionRepository(session),
    )
    payload = service.list_review_queue(limit=limit)
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.post("/platform/contributions/{contribution_id}/review")
def review_data_contribution(
    contribution_id: str,
    request: ContributionReviewRequest,
    admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
):
    service = ContributionService(
        HistoryRepository(session),
        InstitutionRepository(session),
    )
    try:
        payload = service.review_contribution(
            contribution_id,
            request,
            reviewer_id=admin.current.user.user_id,
        )
    except ContributionNotFound:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Contribution not found: {contribution_id!r}",
            ),
        )
    except ContributionWorkflowError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(code=VALIDATION_ERROR, message=str(exc)),
        )
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))
