"""Authenticated Layer 38A current opportunity APIs."""

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
from backend.api.envelope import NOT_FOUND, error_envelope, lightweight_success_envelope
from backend.current_opportunities.repository import CurrentOpportunityRepository
from backend.current_opportunities.schemas import (
    OpportunityGeographyCorrectionInput,
    WorkArrangement,
)
from backend.current_opportunities.service import (
    CurrentOpportunityError,
    CurrentOpportunityNotFound,
    CurrentOpportunityService,
)

router = APIRouter(tags=["current-opportunities"])


@router.get("/current-opportunities")
def list_current_opportunities(
    market: str | None = Query(default=None, min_length=1),
    role_family: str | None = Query(default=None, min_length=1),
    opportunity_type: str | None = Query(default=None, min_length=1),
    work_arrangement: WorkArrangement | None = Query(default=None),
    include_ineligible: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    service = CurrentOpportunityService(CurrentOpportunityRepository(session))
    payload = service.list_opportunities(
        market=market,
        role_family=role_family,
        opportunity_type=opportunity_type,
        work_arrangement=work_arrangement.value if work_arrangement else None,
        include_ineligible=include_ineligible,
        limit=limit,
        offset=offset,
    )
    return lightweight_success_envelope(
        data={"opportunities": [item.model_dump(mode="json") for item in payload]}
    )


@router.get("/current-opportunities/matches")
def list_current_opportunity_matches(
    decision_id: str | None = Query(default=None, min_length=1),
    include_ineligible: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    service = CurrentOpportunityService(CurrentOpportunityRepository(session))
    payload = service.strategic_matches(
        current.user.user_id,
        decision_id=decision_id,
        include_ineligible=include_ineligible,
        limit=limit,
    )
    return lightweight_success_envelope(
        data={"matches": [item.model_dump(mode="json") for item in payload]}
    )


@router.get("/current-opportunities/coverage")
def get_current_opportunity_coverage(
    market_key: str = Query(default="*", min_length=1),
    role_family: str = Query(default="*", min_length=1),
    opportunity_type: str = Query(default="*", min_length=1),
    _current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    service = CurrentOpportunityService(CurrentOpportunityRepository(session))
    payload = service.coverage(
        market_key=market_key,
        role_family=role_family,
        opportunity_type=opportunity_type,
    )
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/current-opportunities/diagnostics")
def list_current_opportunity_diagnostics(
    _admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
):
    service = CurrentOpportunityService(CurrentOpportunityRepository(session))
    payload = service.diagnostics()
    return lightweight_success_envelope(
        data={"diagnostics": [item.model_dump(mode="json") for item in payload]}
    )


@router.get("/current-opportunities/refresh-runs")
def list_current_opportunity_refresh_runs(
    source_id: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=100, ge=1, le=500),
    _admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
):
    service = CurrentOpportunityService(CurrentOpportunityRepository(session))
    return lightweight_success_envelope(
        data={
            "runs": [
                item.model_dump(mode="json")
                for item in service.list_refresh_runs(source_id=source_id, limit=limit)
            ]
        }
    )


@router.post(
    "/current-opportunities/geography-conflicts/{identity_evidence_id}/approve"
)
def approve_current_opportunity_geography_conflict(
    identity_evidence_id: str,
    payload: OpportunityGeographyCorrectionInput,
    admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
):
    service = CurrentOpportunityService(CurrentOpportunityRepository(session))
    try:
        row = service.authorize_geography_correction(
            identity_evidence_id,
            corrected_region=payload.corrected_region,
            reason=payload.reason,
            operator_id=admin.current.user.user_id,
        )
    except CurrentOpportunityNotFound as exc:
        raise HTTPException(status_code=404, detail="Geography conflict not found") from exc
    except CurrentOpportunityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return lightweight_success_envelope(
        data={
            "identity_evidence_id": identity_evidence_id,
            "opportunity_id": row.current_opportunity_id,
            "canonical_region_id": row.market_id,
            "location_resolution_source": row.location_resolution_source,
        }
    )


@router.get("/current-opportunities/geography-conflicts")
def list_current_opportunity_geography_conflicts(
    limit: int = Query(default=100, ge=1, le=500),
    _admin: CurrentAdmin = Depends(require_data_review_access),
    session: Session = Depends(get_session),
):
    service = CurrentOpportunityService(CurrentOpportunityRepository(session))
    return lightweight_success_envelope(
        data={"conflicts": list(service.pending_geography_conflicts(limit=limit))}
    )


@router.get("/current-opportunities/{opportunity_id}")
def get_current_opportunity(
    opportunity_id: str,
    _current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    service = CurrentOpportunityService(CurrentOpportunityRepository(session))
    try:
        payload = service.get_opportunity(opportunity_id, require_display=True)
    except CurrentOpportunityNotFound:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Current opportunity not found: {opportunity_id!r}",
            ),
        )
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))
