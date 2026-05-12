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

from backend.api.dependencies import (
    get_output_service,
    get_region_repository,
)
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
    success_envelope,
)
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
) -> dict:
    rows = region_repo.list()
    regions = [
        {
            "region_id": r.region_id,
            "display_name": r.display_name,
            "region_type": r.region_type,
            "parent_region_id": r.parent_region_id,
            "labor_market_group": r.labor_market_group,
            "state": r.state,
            "version": r.version,
        }
        for r in rows
    ]
    return lightweight_success_envelope(data={"regions": regions})


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


# ---------------------------------------------------------------------------
# /companies/{company_id} — full company output via Slice 11
# ---------------------------------------------------------------------------


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

