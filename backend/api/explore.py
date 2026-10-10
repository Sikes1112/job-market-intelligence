"""Authenticated Layer 41B Explore Context and Explore Fit facade."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import CurrentUser, get_current_user, get_session, require_beta_access
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.explore.comparison_service import (
    ExploreComparisonNotFound,
    ExploreComparisonService,
    ExploreComparisonValidationError,
)
from backend.explore.schemas import (
    ExploreComparisonRequest,
    ExploreMarketsRequest,
    PrioritizeExploreComparisonRequest,
    SaveExploreComparisonRequest,
)
from backend.explore.service import ExploreFitService
from backend.imports.operations import CuratedMarketRegistryUnavailable
from backend.market_intelligence.service import InvalidCareerGoal

router = APIRouter(
    prefix="/me/explore", tags=["explore"], dependencies=[Depends(require_beta_access)]
)


@router.get("/context", response_model=None)
def get_explore_context(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    context = ExploreFitService(session).context(current.user.user_id)
    return lightweight_success_envelope(data=context.model_dump(mode="json"))


@router.post("/markets", response_model=None)
def evaluate_explore_markets(
    request: ExploreMarketsRequest,
    as_of: date | None = Query(default=None),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        result = ExploreFitService(session).evaluate(
            current.user.user_id,
            request.session_overrides,
            as_of=as_of,
        )
    except (CuratedMarketRegistryUnavailable, InvalidCareerGoal) as exc:
        return _validation(str(exc))
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.post("/markets/{market_ref}", response_model=None)
def get_explore_market_detail(
    market_ref: str,
    request: ExploreMarketsRequest,
    as_of: date | None = Query(default=None),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        response, market = ExploreFitService(session).market_detail(
            current.user.user_id,
            market_ref,
            request.session_overrides,
            as_of=as_of,
        )
    except (CuratedMarketRegistryUnavailable, InvalidCareerGoal) as exc:
        return _validation(str(exc))
    if market is None:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message="Explore market not found in the evaluated universe.",
            ),
        )
    return lightweight_success_envelope(
        data={
            "context": response.context.model_dump(mode="json"),
            "ranking_universe": response.ranking_universe.model_dump(mode="json"),
            "market": market.model_dump(mode="json"),
            "evaluated_at": response.evaluated_at.isoformat(),
            "authority": response.authority,
            "authority_version": response.authority_version,
            "contradiction_status": response.contradiction_status,
            "contradiction_findings": list(response.contradiction_findings),
            "contradiction_blocking": response.contradiction_blocking,
            "contradiction_summary": response.contradiction_summary,
            "limitations": list(response.limitations),
        }
    )


@router.post("/compare", response_model=None)
def compare_explore_markets(
    request: ExploreComparisonRequest,
    as_of: date | None = Query(default=None),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        result = ExploreComparisonService(session).compare(
            current.user.user_id,
            request,
            as_of=as_of,
        )
    except (
        ExploreComparisonValidationError,
        CuratedMarketRegistryUnavailable,
        InvalidCareerGoal,
    ) as exc:
        return _validation(str(exc), status_code=422)
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.post("/comparisons", status_code=status.HTTP_201_CREATED, response_model=None)
def save_explore_comparison(
    request: SaveExploreComparisonRequest,
    as_of: date | None = Query(default=None),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        result = ExploreComparisonService(session).save(
            current.user.user_id,
            request,
            as_of=as_of,
        )
    except (
        ExploreComparisonValidationError,
        CuratedMarketRegistryUnavailable,
        InvalidCareerGoal,
    ) as exc:
        return _validation(str(exc), status_code=409)
    return lightweight_success_envelope(data={"comparison": result.model_dump(mode="json")})


@router.get("/comparisons", response_model=None)
def list_explore_comparisons(
    limit: int = Query(default=100, ge=1, le=500),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    results = ExploreComparisonService(session).list_saved(current.user.user_id, limit=limit)
    return lightweight_success_envelope(
        data={"comparisons": [result.model_dump(mode="json") for result in results]}
    )


@router.get("/comparisons/{comparison_id}", response_model=None)
def get_explore_comparison(
    comparison_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        result = ExploreComparisonService(session).get_saved(
            current.user.user_id,
            comparison_id,
        )
    except ExploreComparisonNotFound:
        return JSONResponse(
            status_code=404,
            content=error_envelope(code=NOT_FOUND, message="Saved comparison not found."),
        )
    return lightweight_success_envelope(data={"comparison": result.model_dump(mode="json")})


@router.post("/prioritize", response_model=None)
def prioritize_explore_comparison(
    request: PrioritizeExploreComparisonRequest,
    as_of: date | None = Query(default=None),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        result = ExploreComparisonService(session).prioritize(
            current.user.user_id,
            request,
            as_of=as_of,
        )
    except ExploreComparisonNotFound:
        return JSONResponse(
            status_code=404,
            content=error_envelope(code=NOT_FOUND, message="Comparison not found."),
        )
    except (
        ExploreComparisonValidationError,
        CuratedMarketRegistryUnavailable,
        InvalidCareerGoal,
    ) as exc:
        return _validation(str(exc), status_code=422)
    return lightweight_success_envelope(data={"prioritization": result.model_dump(mode="json")})


def _validation(message: str, *, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_envelope(code=VALIDATION_ERROR, message=message),
    )
