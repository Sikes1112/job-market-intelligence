"""Layer 14 recommendation API routes.

These routes expose deterministic recommendation ranking and strategy planning
over existing app-owned outputs. They do not scrape live data, call AI systems,
persist recommendation state, or mutate canonical market facts.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import (
    get_output_service,
    get_region_repository,
    get_session,
)
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.api.search import (
    explain_company_sources,
    explain_region_sources,
    search_companies,
)
from backend.geography.repository import RegionRepository
from backend.outputs.exceptions import MissingCompanyForOutput, MissingRegionForOutput
from backend.outputs.service import OutputAssemblyService
from backend.recommendations.payloads import (
    RecommendationStrategyPayload,
    RecommendationStrategyRequest,
    recommendation_goal_modes_payload,
    recommendation_strategy_payload,
)
from backend.recommendations.ranking import (
    RecommendationRankingResult,
    rank_company_recommendations,
    rank_region_recommendations,
)
from backend.recommendations.strategy import generate_market_strategy_plan

router = APIRouter()


@router.get("/recommendations/goal-modes")
def recommendation_goal_modes_route() -> dict:
    payload = recommendation_goal_modes_payload()
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.post("/recommendations/strategy", response_model=None)
def recommendation_strategy_route(
    request: RecommendationStrategyRequest,
    service: OutputAssemblyService = Depends(get_output_service),
    region_repo: RegionRepository = Depends(get_region_repository),
    session: Session = Depends(get_session),
) -> Any:
    region_payloads, data_warnings = _region_payloads(
        service=service,
        region_repo=region_repo,
    )
    if not region_payloads:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message="No region outputs are available for recommendation strategy.",
            ),
        )

    source_warnings: list[str] = []
    try:
        region_rankings = rank_region_recommendations(
            region_payloads,
            goal_mode=request.goal_mode,
            source_summaries=_region_source_summaries(
                session,
                region_payloads,
                warnings=source_warnings,
            ),
        )
        region_rankings = _limit_ranking_result(region_rankings, request.region_limit)

        company_rankings = _company_rankings(
            request,
            service=service,
            session=session,
            warnings=data_warnings,
        )
        if company_rankings is not None:
            company_rankings = _limit_ranking_result(
                company_rankings,
                request.company_limit,
            )

        strategy_plan = generate_market_strategy_plan(
            region_rankings,
            company_rankings=company_rankings,
            goal_mode=request.goal_mode,
            max_primary_regions=request.max_primary_regions,
            max_secondary_regions=request.max_secondary_regions,
            max_fallback_regions=request.max_fallback_regions,
            max_watchlist_items=request.max_watchlist_items,
            max_company_targets=request.max_company_targets,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(code=VALIDATION_ERROR, message=str(exc)),
        )

    payload = recommendation_strategy_payload(
        region_rankings=region_rankings,
        company_rankings=company_rankings,
        strategy_plan=strategy_plan,
        warnings=tuple((*data_warnings, *source_warnings)),
    )
    envelope = lightweight_success_envelope(
        data=payload.model_dump(mode="json"),
        state=_response_state(payload),
    )
    envelope["metadata"]["warnings"] = list(payload.warnings)
    return envelope


def _region_payloads(
    *,
    service: OutputAssemblyService,
    region_repo: RegionRepository,
) -> tuple[tuple[Any, ...], list[str]]:
    payloads: list[Any] = []
    warnings: list[str] = []
    for region in region_repo.list():
        try:
            payloads.append(service.read_region(region.region_id).payload)
        except MissingRegionForOutput:
            warnings.append(
                f"Region output skipped because region was unavailable: {region.region_id}"
            )
    return tuple(payloads), warnings


def _company_rankings(
    request: RecommendationStrategyRequest,
    *,
    service: OutputAssemblyService,
    session: Session,
    warnings: list[str],
) -> RecommendationRankingResult | None:
    if not request.include_company_recommendations:
        warnings.append("Company recommendations were not requested.")
        return None
    if request.company_limit == 0:
        warnings.append("Company recommendation limit is zero.")
        return None

    company_ids = tuple(company.company_id for company in search_companies(session).companies)
    if not company_ids:
        warnings.append("Company rankings unavailable: no company outputs were available.")
        return None

    payloads: list[Any] = []
    for company_id in company_ids:
        try:
            payloads.append(service.read_company(company_id).payload)
        except MissingCompanyForOutput:
            warnings.append(
                f"Company output skipped because company was unavailable: {company_id}"
            )
    if not payloads:
        warnings.append("Company rankings unavailable: no readable company outputs.")
        return None

    source_warnings: list[str] = []
    result = rank_company_recommendations(
        payloads,
        goal_mode=request.goal_mode,
        source_summaries=_company_source_summaries(
            session,
            company_ids,
            warnings=source_warnings,
        ),
    )
    warnings.extend(source_warnings)
    return result


def _region_source_summaries(
    session: Session,
    region_payloads: Iterable[Any],
    *,
    warnings: list[str],
) -> Mapping[str, Any]:
    summaries: dict[str, Any] = {}
    for payload in region_payloads:
        region_id = _target_id(payload, outer_field="region", id_field="region_id")
        if region_id is None:
            warnings.append("Region source summary skipped for payload without region_id.")
            continue
        summary = explain_region_sources(session, region_id=region_id)
        if summary is not None:
            summaries[region_id] = summary
    return summaries


def _company_source_summaries(
    session: Session,
    company_ids: Iterable[str],
    *,
    warnings: list[str],
) -> Mapping[str, Any]:
    summaries: dict[str, Any] = {}
    for company_id in company_ids:
        summary = explain_company_sources(session, company_id=company_id)
        if summary is not None:
            summaries[company_id] = summary
    return summaries


def _limit_ranking_result(
    result: RecommendationRankingResult,
    limit: int,
) -> RecommendationRankingResult:
    limited_items = result.ranked_recommendations[:limit]
    return RecommendationRankingResult(
        goal_mode=result.goal_mode,
        profile=result.profile,
        profile_version=result.profile_version,
        tie_breaker=result.tie_breaker,
        ranked_recommendations=limited_items,
    )


def _response_state(payload: RecommendationStrategyPayload) -> str:
    if not payload.warnings:
        has_partial_evidence = bool(payload.market_strategy_plan.evidence_warnings) or any(
            item.score_components_missing
            for item in (
                *payload.ranked_region_recommendations,
                *payload.ranked_company_recommendations,
            )
        )
        return "partial" if has_partial_evidence else "fresh"
    warning_text = " ".join(payload.warnings).casefold()
    if "unavailable" in warning_text or "missing" in warning_text:
        return "partial"
    return "fresh"


def _target_id(payload: Any, *, outer_field: str, id_field: str) -> str | None:
    outer = _field(payload, outer_field) or payload
    value = _field(outer, id_field)
    return value if isinstance(value, str) and value.strip() else None


def _field(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
