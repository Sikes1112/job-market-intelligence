"""Public-safe read-only API routes for Layer 34 market intelligence."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import get_session
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.imports.operations import CuratedMarketRegistryUnavailable
from backend.market_intelligence.service import (
    InvalidCareerGoal,
    MarketIntelligenceService,
    UnknownMarketForIntelligence,
)

router = APIRouter(tags=["market-intelligence"])


@router.get("/market-intelligence")
def market_intelligence_platform(
    goal: str = Query(default="software_engineering", min_length=1),
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    service = MarketIntelligenceService(session)
    try:
        report = service.platform_summary(goal=goal, as_of=as_of)
    except InvalidCareerGoal:
        return _invalid_goal_response()
    except CuratedMarketRegistryUnavailable:
        return _registry_unavailable_response()
    return lightweight_success_envelope(data=report.as_dict())


@router.get("/market-intelligence/{market_key}")
def market_intelligence_profile(
    market_key: str,
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    service = MarketIntelligenceService(session)
    try:
        profile = service.profile(market_key, as_of=as_of)
    except UnknownMarketForIntelligence:
        return _unknown_market_response()
    except CuratedMarketRegistryUnavailable:
        return _registry_unavailable_response()
    return lightweight_success_envelope(data=profile.as_dict())


@router.get("/market-comparisons")
def market_comparisons_ranking(
    goal: str = Query(default="software_engineering", min_length=1),
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    service = MarketIntelligenceService(session)
    try:
        ranking = service.ranking(goal=goal, as_of=as_of)
    except InvalidCareerGoal:
        return _invalid_goal_response()
    except CuratedMarketRegistryUnavailable:
        return _registry_unavailable_response()
    return lightweight_success_envelope(data=ranking.as_dict())


@router.get("/market-comparisons/{market_a}/{market_b}")
def market_comparison_pair(
    market_a: str,
    market_b: str,
    goal: str = Query(default="software_engineering", min_length=1),
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    service = MarketIntelligenceService(session)
    try:
        comparison = service.comparison(
            market_a,
            market_b,
            goal=goal,
            as_of=as_of,
        )
    except InvalidCareerGoal:
        return _invalid_goal_response()
    except UnknownMarketForIntelligence:
        return _unknown_market_response()
    except CuratedMarketRegistryUnavailable:
        return _registry_unavailable_response()
    return lightweight_success_envelope(data=comparison.as_dict())


@router.get("/career-goal-comparisons")
def career_goal_comparisons(
    goal: str | None = Query(default=None, min_length=1),
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    service = MarketIntelligenceService(session)
    try:
        if goal is None:
            comparisons = service.all_career_goal_comparisons(as_of=as_of)
            return lightweight_success_envelope(
                data={"comparisons": [report.as_dict() for report in comparisons]}
            )
        report = service.career_goal_comparison(goal=goal, as_of=as_of)
    except InvalidCareerGoal:
        return _invalid_goal_response()
    except CuratedMarketRegistryUnavailable:
        return _registry_unavailable_response()
    return lightweight_success_envelope(data=report.as_dict())


@router.get("/career-goal-comparisons/{goal}")
def career_goal_comparison_detail(
    goal: str,
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    service = MarketIntelligenceService(session)
    try:
        report = service.career_goal_comparison(goal=goal, as_of=as_of)
    except InvalidCareerGoal:
        return _invalid_goal_response()
    except CuratedMarketRegistryUnavailable:
        return _registry_unavailable_response()
    return lightweight_success_envelope(data=report.as_dict())


def _unknown_market_response() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_envelope(
            code=NOT_FOUND,
            message="Market intelligence market not found.",
        ),
    )


def _invalid_goal_response() -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=error_envelope(
            code=VALIDATION_ERROR,
            message="Unsupported career goal.",
        ),
    )


def _registry_unavailable_response() -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=error_envelope(
            code=VALIDATION_ERROR,
            message="Curated market registry is not available.",
        ),
    )
