"""Read-only API routes for Slice 12.

Routes are thin: they call :class:`OutputAssemblyService` (Slice 11) for
the per-subject output endpoints and the region repository for the
lightweight ``GET /regions`` listing. Domain exceptions raised by Slice 11
are mapped to HTTP responses here; nothing in this module recomputes,
mutates, or personalizes anything.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
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
    region_a: str = Query(..., min_length=1),
    region_b: str = Query(..., min_length=1),
    service: OutputAssemblyService = Depends(get_output_service),
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
    return success_envelope(
        data=payload.comparison.model_dump(mode="json"),
        output_metadata_row=result.metadata,
        payload_metadata=payload.metadata,
    )
