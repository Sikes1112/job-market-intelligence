"""Read-only API routes for Slice 12.

Routes are thin: they call :class:`OutputAssemblyService` (Slice 11) for
the per-subject output endpoints and the region repository for the
lightweight ``GET /regions`` listing. Domain exceptions raised by Slice 11
are mapped to HTTP responses here; nothing in this module recomputes,
mutates, or personalizes anything.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
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
    success_envelope,
)
from backend.api.metadata import ApiFreshnessStatus
from backend.api.monetization_access import (
    blocked_entitlement_response,
    optional_current_user,
)
from backend.api.search import (
    company_geography,
    explain_company_sources,
    explain_region_sources,
    region_coverage_lookup,
    search_companies,
    search_regions,
)
from backend.geography.market_coverage import priority_market_by_id
from backend.geography.repository import RegionRepository
from backend.imports.coverage import build_all_market_coverage_summaries
from backend.imports.diagnostics import (
    build_refresh_readiness_reports,
    coverage_gaps_from_snapshot,
    dataset_health_from_snapshot,
    fact_health_from_snapshot,
    platform_summary_from_health_reports,
    ranking_exclusions_from_snapshot,
    refresh_readiness_from_snapshot,
    source_aging_from_snapshot,
)
from backend.imports.diff import build_import_diff_preview
from backend.imports.operations import (
    CuratedMarketRegistryUnavailable,
    UnknownCuratedMarket,
    build_all_market_operational_snapshots,
    build_market_operational_snapshot,
)
from backend.monetization.enforcement import (
    evaluate_account_access,
    increment_feature_usage,
)
from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.repository import MonetizationRepository
from backend.outputs.exceptions import (
    InvalidComparisonInput,
    MissingCompanyForOutput,
    MissingRegionForOutput,
)
from backend.outputs.service import OutputAssemblyService

router = APIRouter()


# ---------------------------------------------------------------------------
# /regions — lightweight identity list
# ---------------------------------------------------------------------------


@router.get("/regions")
def list_regions(
    region_repo: RegionRepository = Depends(get_region_repository),
    session: Session = Depends(get_session),
) -> dict:
    rows = region_repo.list()
    coverage_by_region = region_coverage_lookup(session)
    regions = [
        {
            "region_id": r.region_id,
            "display_name": r.display_name,
            "region_type": r.region_type,
            "parent_region_id": r.parent_region_id,
            "labor_market_group": r.labor_market_group,
            "priority_market": (
                priority_market.model_dump(mode="json")
                if (priority_market := priority_market_by_id(r.region_id)) is not None
                else None
            ),
            "state": r.state,
            "version": r.version,
            "coverage": coverage_by_region[r.region_id].model_dump(mode="json"),
            "sector_coverage": {},
        }
        for r in rows
    ]
    return lightweight_success_envelope(data={"regions": regions})


@router.get("/metadata/coverage")
def coverage_metadata() -> dict:
    from backend.api.metadata import build_coverage_metadata_vocabulary

    return lightweight_success_envelope(data=build_coverage_metadata_vocabulary())


@router.get("/markets/imported")
def imported_markets(session: Session = Depends(get_session)) -> dict:
    summaries = build_all_market_coverage_summaries(session)
    markets = [summary.as_dict() for summary in summaries.values()]
    return lightweight_success_envelope(
        data={"markets": markets, "market_count": len(markets)}
    )


@router.get("/markets/imported/health")
def imported_market_health(
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    try:
        snapshots = build_all_market_operational_snapshots(session, as_of=as_of)
    except CuratedMarketRegistryUnavailable:
        return _registry_unavailable_response()
    health_reports = tuple(dataset_health_from_snapshot(snapshot) for snapshot in snapshots)
    readiness_reports = build_refresh_readiness_reports(session, as_of=as_of)
    summary = platform_summary_from_health_reports(health_reports, readiness_reports)
    return lightweight_success_envelope(
        data={
            "summary": summary.as_dict(),
            "markets": [report.as_dict() for report in health_reports],
        }
    )


@router.get("/markets/imported/{market_key}/health")
def imported_market_health_detail(
    market_key: str,
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    snapshot = _market_snapshot_or_response(session, market_key, as_of=as_of)
    if isinstance(snapshot, JSONResponse):
        return snapshot
    return lightweight_success_envelope(data=dataset_health_from_snapshot(snapshot).as_dict())


@router.get("/markets/imported/{market_key}/sources")
def imported_market_sources(
    market_key: str,
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    snapshot = _market_snapshot_or_response(session, market_key, as_of=as_of)
    if isinstance(snapshot, JSONResponse):
        return snapshot
    return lightweight_success_envelope(data=source_aging_from_snapshot(snapshot).as_dict())


@router.get("/markets/imported/{market_key}/facts")
def imported_market_facts(
    market_key: str,
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    snapshot = _market_snapshot_or_response(session, market_key, as_of=as_of)
    if isinstance(snapshot, JSONResponse):
        return snapshot
    return lightweight_success_envelope(data=fact_health_from_snapshot(snapshot).as_dict())


@router.get("/markets/imported/{market_key}/gaps")
def imported_market_gaps(
    market_key: str,
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    snapshot = _market_snapshot_or_response(session, market_key, as_of=as_of)
    if isinstance(snapshot, JSONResponse):
        return snapshot
    return lightweight_success_envelope(data=coverage_gaps_from_snapshot(snapshot).as_dict())


@router.get("/markets/imported/{market_key}/ranking-diagnostics")
def imported_market_ranking_diagnostics(
    market_key: str,
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    snapshot = _market_snapshot_or_response(session, market_key, as_of=as_of)
    if isinstance(snapshot, JSONResponse):
        return snapshot
    return lightweight_success_envelope(data=ranking_exclusions_from_snapshot(snapshot).as_dict())


@router.get("/markets/imported/{market_key}/refresh-readiness")
def imported_market_refresh_readiness(
    market_key: str,
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    snapshot = _market_snapshot_or_response(session, market_key, as_of=as_of)
    if isinstance(snapshot, JSONResponse):
        return snapshot
    return lightweight_success_envelope(data=refresh_readiness_from_snapshot(snapshot).as_dict())


@router.get("/markets/imported/{market_key}/diff-preview")
def imported_market_diff_preview(
    market_key: str,
    as_of: date | None = Query(default=None),
    session: Session = Depends(get_session),
):
    try:
        preview = build_import_diff_preview(session, market_key, as_of=as_of)
    except UnknownCuratedMarket:
        return _unknown_market_response()
    except CuratedMarketRegistryUnavailable:
        return _registry_unavailable_response()
    return lightweight_success_envelope(data=preview.as_dict())


@router.get("/regions/search")
def search_regions_route(
    query: str | None = Query(default=None, min_length=1),
    region_type: str | None = Query(default=None, min_length=1),
    has_real_data: bool | None = Query(default=None),
    freshness_status: ApiFreshnessStatus | None = Query(default=None),
    min_opportunity_score: float | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    result = search_regions(
        session,
        query=query,
        region_type=region_type,
        has_real_data=has_real_data,
        freshness_status=freshness_status,
        min_opportunity_score=min_opportunity_score,
    )
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


def _market_snapshot_or_response(
    session: Session,
    market_key: str,
    *,
    as_of: date | None,
):
    try:
        return build_market_operational_snapshot(session, market_key, as_of=as_of)
    except UnknownCuratedMarket:
        return _unknown_market_response()
    except CuratedMarketRegistryUnavailable:
        return _registry_unavailable_response()


def _unknown_market_response() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_envelope(
            code=NOT_FOUND,
            message="Imported market not found.",
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


# ---------------------------------------------------------------------------
# /regions/{region_id} — full region output via Slice 11
# ---------------------------------------------------------------------------


@router.get("/regions/{region_id}")
def get_region(
    region_id: str,
    service: OutputAssemblyService = Depends(get_output_service),
):
    try:
        result = service.read_region(region_id)
    except MissingRegionForOutput:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND, message=f"Region not found: {region_id!r}"
            ),
        )
    payload = result.payload
    return success_envelope(
        data=payload.region.model_dump(mode="json"),
        output_metadata_row=result.metadata,
        payload_metadata=payload.metadata,
    )


@router.get("/regions/{region_id}/sources")
def explain_region_sources_route(
    region_id: str,
    session: Session = Depends(get_session),
):
    result = explain_region_sources(session, region_id=region_id)
    if result is None:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND, message=f"Region not found: {region_id!r}"
            ),
        )
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# /companies/{company_id} — full company output via Slice 11
# ---------------------------------------------------------------------------


@router.get("/companies/search")
def search_companies_route(
    query: str | None = Query(default=None, min_length=1),
    sector: str | None = Query(default=None, min_length=1),
    industry: str | None = Query(default=None, min_length=1),
    role_family: str | None = Query(default=None, min_length=1),
    region_id: str | None = Query(default=None, min_length=1),
    current_hiring: bool | None = Query(default=None),
    has_entry_level_access: bool | None = Query(default=None),
    presence_status: str | None = Query(default=None, min_length=1),
    session: Session = Depends(get_session),
) -> dict:
    result = search_companies(
        session,
        query=query,
        sector=sector,
        industry=industry,
        role_family=role_family,
        region_id=region_id,
        current_hiring=current_hiring,
        has_entry_level_access=has_entry_level_access,
        presence_status=presence_status,
    )
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.get("/companies/{company_id}")
def get_company(
    company_id: str,
    service: OutputAssemblyService = Depends(get_output_service),
):
    try:
        result = service.read_company(company_id)
    except MissingCompanyForOutput:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND, message=f"Company not found: {company_id!r}"
            ),
        )
    payload = result.payload
    return success_envelope(
        data=payload.company.model_dump(mode="json"),
        output_metadata_row=result.metadata,
        payload_metadata=payload.metadata,
    )


@router.get("/companies/{company_id}/regions")
def company_geography_route(
    company_id: str,
    session: Session = Depends(get_session),
):
    result = company_geography(session, company_id=company_id)
    if result is None:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND, message=f"Company not found: {company_id!r}"
            ),
        )
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


@router.get("/companies/{company_id}/sources")
def explain_company_sources_route(
    company_id: str,
    session: Session = Depends(get_session),
):
    result = explain_company_sources(session, company_id=company_id)
    if result is None:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND, message=f"Company not found: {company_id!r}"
            ),
        )
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# /compare — comparison output via Slice 11
# ---------------------------------------------------------------------------


@router.get("/compare")
def get_comparison(
    request: Request,
    region_a: str = Query(..., min_length=1),
    region_b: str = Query(..., min_length=1),
    service: OutputAssemblyService = Depends(get_output_service),
    session: Session = Depends(get_session),
):
    if region_a == region_b:
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                code=VALIDATION_ERROR,
                message=(
                    f"region_a and region_b must be distinct; got {region_a!r} twice"
                ),
            ),
        )

    current = optional_current_user(request, session)
    repo = MonetizationRepository(session)
    if current is not None:
        repo.ensure_account_for_user(user_id=current.user.user_id)
        access = evaluate_account_access(
            repo,
            user_id=current.user.user_id,
            feature_key=MonetizationFeatureKey.LIMITED_COMPARISONS,
            create_usage_counter=True,
        )
        if not access.allowed:
            return blocked_entitlement_response(access)

    try:
        result = service.read_comparison(region_a, region_b)
    except InvalidComparisonInput as e:
        return JSONResponse(
            status_code=400,
            content=error_envelope(code=VALIDATION_ERROR, message=str(e)),
        )
    except MissingRegionForOutput as e:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND, message=f"Region not found: {e!s}"
            ),
        )
    payload = result.payload
    envelope = success_envelope(
        data=payload.comparison.model_dump(mode="json"),
        output_metadata_row=result.metadata,
        payload_metadata=payload.metadata,
    )
    if current is not None:
        usage_decision = increment_feature_usage(
            repo,
            user_id=current.user.user_id,
            feature_key=MonetizationFeatureKey.LIMITED_COMPARISONS,
        )
        envelope["metadata"]["monetization_access"] = usage_decision.model_dump(
            mode="json"
        )
    return envelope
