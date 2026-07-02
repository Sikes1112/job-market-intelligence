"""Controlled external API routes for Layer 17C."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import get_output_service, get_session
from backend.institutions.exceptions import OrganizationNotFound
from backend.institutions.repository import InstitutionRepository
from backend.integrations.repository import IntegrationRepository
from backend.integrations.service import (
    ApiAuthenticationError,
    ApiRateLimitExceeded,
    ApiScopeDenied,
    IntegrationService,
)
from backend.integrations.types import ApiRateLimitDecision, ApiScope, json_safe
from backend.outputs.exceptions import MissingCompanyForOutput, MissingRegionForOutput
from backend.outputs.service import OutputAssemblyService

router = APIRouter(prefix="/api/external/v1", tags=["external-api"])


def _service(
    session: Session,
    output_service: OutputAssemblyService,
) -> IntegrationService:
    return IntegrationService(
        IntegrationRepository(session),
        institution_repo=InstitutionRepository(session),
        output_service=output_service,
    )


def _raw_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str | None:
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    return None


@router.get("/regions", response_model=None)
def external_regions(
    request: Request,
    raw_api_key: str | None = Depends(_raw_api_key),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    service = _service(session, output_service)
    try:
        context = service.authenticate_external_api_key(
            raw_key=raw_api_key,
            required_scope=ApiScope.REGION_READ,
            route=request.url.path,
            method=request.method,
        )
        envelope = service.external_regions(context=context)
    except (ApiAuthenticationError, ApiScopeDenied, ApiRateLimitExceeded) as exc:
        return _external_access_error(exc)
    return envelope.model_dump(mode="json")


@router.get("/regions/{region_id}/intelligence", response_model=None)
def external_region_intelligence(
    region_id: str,
    request: Request,
    raw_api_key: str | None = Depends(_raw_api_key),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    service = _service(session, output_service)
    try:
        context = service.authenticate_external_api_key(
            raw_key=raw_api_key,
            required_scope=ApiScope.REGION_READ,
            route=request.url.path,
            method=request.method,
        )
        envelope = service.external_region_intelligence(
            region_id=region_id,
            context=context,
        )
    except (ApiAuthenticationError, ApiScopeDenied, ApiRateLimitExceeded) as exc:
        return _external_access_error(exc)
    except MissingRegionForOutput:
        return _external_error(404, "NOT_FOUND", "Region not found.")
    return envelope.model_dump(mode="json")


@router.get("/companies/{company_id}/geography", response_model=None)
def external_company_geography(
    company_id: str,
    request: Request,
    raw_api_key: str | None = Depends(_raw_api_key),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    service = _service(session, output_service)
    try:
        context = service.authenticate_external_api_key(
            raw_key=raw_api_key,
            required_scope=ApiScope.COMPANY_GEOGRAPHY_READ,
            route=request.url.path,
            method=request.method,
        )
        envelope = service.external_company_geography(
            company_id=company_id,
            context=context,
        )
    except (ApiAuthenticationError, ApiScopeDenied, ApiRateLimitExceeded) as exc:
        return _external_access_error(exc)
    except MissingCompanyForOutput:
        return _external_error(404, "NOT_FOUND", "Company not found.")
    return envelope.model_dump(mode="json")


@router.get("/market-signals", response_model=None)
def external_market_signals(
    request: Request,
    raw_api_key: str | None = Depends(_raw_api_key),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    service = _service(session, output_service)
    try:
        context = service.authenticate_external_api_key(
            raw_key=raw_api_key,
            required_scope=ApiScope.MARKET_SIGNAL_READ,
            route=request.url.path,
            method=request.method,
        )
        envelope = service.external_market_signals(context=context)
    except (ApiAuthenticationError, ApiScopeDenied, ApiRateLimitExceeded) as exc:
        return _external_access_error(exc)
    return envelope.model_dump(mode="json")


@router.get("/institutions/{organization_id}/dashboard", response_model=None)
def external_institution_dashboard(
    organization_id: str,
    request: Request,
    raw_api_key: str | None = Depends(_raw_api_key),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    service = _service(session, output_service)
    try:
        context = service.authenticate_external_api_key(
            raw_key=raw_api_key,
            required_scope=ApiScope.INSTITUTION_DASHBOARD_READ,
            route=request.url.path,
            method=request.method,
            requested_organization_id=organization_id,
        )
        envelope = service.external_institution_dashboard(
            organization_id=organization_id,
            context=context,
        )
    except (ApiAuthenticationError, ApiScopeDenied, ApiRateLimitExceeded) as exc:
        return _external_access_error(exc)
    except OrganizationNotFound:
        return _external_error(404, "NOT_FOUND", "Organization not found.")
    return envelope.model_dump(mode="json")


def _external_access_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, ApiRateLimitExceeded):
        return _external_error(
            429,
            "RATE_LIMIT_EXCEEDED",
            "External API rate limit exhausted.",
            rate_limit=exc.decision,
        )
    if isinstance(exc, ApiScopeDenied):
        return _external_error(403, "MISSING_SCOPE", str(exc))
    return _external_error(401, "INVALID_API_KEY", str(exc))


def _external_error(
    status_code: int,
    code: str,
    message: str,
    *,
    rate_limit: ApiRateLimitDecision | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "data": None,
            "meta": {
                "generated_at": datetime.now(UTC).isoformat(),
                "rate_limit": json_safe(rate_limit) if rate_limit else None,
                "governance_warnings": [
                    "External API access failed safely without exposing internal-only fields."
                ],
            },
            "error": {"code": code, "message": message},
        },
    )
