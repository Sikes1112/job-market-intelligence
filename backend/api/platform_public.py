"""Versioned public Platform API routes for Layer 20."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import get_output_service, get_session
from backend.api.envelope import error_envelope, lightweight_success_envelope
from backend.outputs.exceptions import (
    InvalidComparisonInput,
    MissingCompanyForOutput,
    MissingRegionForOutput,
)
from backend.outputs.service import OutputAssemblyService
from backend.platform.api_keys import (
    PlatformApiKeyValidationReason,
    mark_platform_api_key_used,
    validate_platform_api_key,
)
from backend.platform.audit_logs import (
    PlatformApiAuditDecision,
    PlatformApiAuditEventType,
    record_platform_api_audit_event,
)
from backend.platform.docs_exports import (
    build_platform_openapi_spec,
    build_platform_postman_collection,
)
from backend.platform.embeds import (
    build_platform_embed_access_payload,
    decide_platform_embed_request,
    platform_embed_product_id_from_route,
    record_platform_embed_usage_event,
)
from backend.platform.entitlements import (
    PlatformApiEntitlementReason,
    PlatformApiTier,
    decide_platform_api_entitlement,
)
from backend.platform.models import PlatformApiKey
from backend.platform.product_catalog import PlatformApiProductId
from backend.platform.public_api_payloads import build_public_api_error_envelope
from backend.platform.public_api_service import PlatformPublicApiService
from backend.platform.rate_limits import (
    PlatformApiMonthlyUsageDecision,
    PlatformApiRateLimitDecision,
    check_platform_api_monthly_usage_limit,
    check_platform_api_rate_limit,
)
from backend.platform.usage import (
    PlatformApiUsageOutcome,
    record_platform_api_usage,
)

router = APIRouter(prefix="/api/v1/platform", tags=["platform-public-api"])


@dataclass(slots=True)
class _PlatformAccessContext:
    api_key: PlatformApiKey
    product_id: PlatformApiProductId
    endpoint: str
    method: str
    rate_limit: PlatformApiRateLimitDecision
    monthly_limit: PlatformApiMonthlyUsageDecision


def _service(
    session: Session,
    output_service: OutputAssemblyService,
) -> PlatformPublicApiService:
    return PlatformPublicApiService(
        session=session,
        output_service=output_service,
    )


def _platform_api_key_header(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str | None:
    return x_api_key


@router.get("/docs/openapi.json", response_model=None)
def platform_openapi_export() -> dict:
    return build_platform_openapi_spec()


@router.get("/docs/postman.json", response_model=None)
def platform_postman_export() -> dict:
    return build_platform_postman_collection()


@router.get("/embeds/{embed_product_slug}", response_model=None)
def platform_embed_payload(
    embed_product_slug: str,
    request: Request,
    origin: str | None = None,
) -> JSONResponse | dict:
    try:
        product_id = platform_embed_product_id_from_route(embed_product_slug)
    except ValueError:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code="EMBED_POLICY_DENIED",
                message="Unknown platform embed.",
            ),
        )

    decision = decide_platform_embed_request(
        embed_product_id=product_id,
        origin_header=request.headers.get("origin"),
        referer_header=request.headers.get("referer"),
        declared_origin=origin,
    )
    record_platform_embed_usage_event(embed_product_id=product_id, decision=decision)
    if not decision.allowed:
        return JSONResponse(
            status_code=403,
            content=error_envelope(
                code="EMBED_DOMAIN_NOT_ALLOWED",
                message="This embed is not approved for the requesting domain.",
            ),
        )

    payload = build_platform_embed_access_payload(product_id)
    return lightweight_success_envelope(
        data=payload.model_dump(mode="json"),
        state="public_safe",
    )


@router.get("/regions/{region_id}/scores", response_model=None)
def public_region_scores(
    region_id: str,
    request: Request,
    raw_api_key: str | None = Depends(_platform_api_key_header),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    access = _authorize_platform_request(
        session=session,
        request=request,
        product_id=PlatformApiProductId.REGION_SCORES,
        raw_api_key=raw_api_key,
    )
    if isinstance(access, JSONResponse):
        return access

    unsupported = _unsupported_query_parameters(request, allowed=())
    if unsupported:
        return _deny_authorized_platform_request(
            session=session,
            access=access,
            status_code=400,
            code="UNSUPPORTED_QUERY",
            message=_unsupported_query_message(unsupported),
            decision_reason="unsupported_query",
            metadata={"unsupported_query_parameters": unsupported},
        )

    try:
        envelope = _service(session, output_service).region_scores(region_id)
    except MissingRegionForOutput:
        return _deny_authorized_platform_request(
            session=session,
            access=access,
            status_code=404,
            code="NOT_FOUND",
            message="Region not found.",
            decision_reason="not_found",
        )

    _record_platform_success(session=session, access=access)
    return envelope.model_dump(mode="json")


@router.get("/companies/{company_id}/geography", response_model=None)
def public_company_geography(
    company_id: str,
    request: Request,
    raw_api_key: str | None = Depends(_platform_api_key_header),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    access = _authorize_platform_request(
        session=session,
        request=request,
        product_id=PlatformApiProductId.COMPANY_GEOGRAPHY,
        raw_api_key=raw_api_key,
    )
    if isinstance(access, JSONResponse):
        return access

    unsupported = _unsupported_query_parameters(request, allowed=())
    if unsupported:
        return _deny_authorized_platform_request(
            session=session,
            access=access,
            status_code=400,
            code="UNSUPPORTED_QUERY",
            message=_unsupported_query_message(unsupported),
            decision_reason="unsupported_query",
            metadata={"unsupported_query_parameters": unsupported},
        )

    try:
        envelope = _service(session, output_service).company_geography(company_id)
    except MissingCompanyForOutput:
        return _deny_authorized_platform_request(
            session=session,
            access=access,
            status_code=404,
            code="NOT_FOUND",
            message="Company not found.",
            decision_reason="not_found",
        )

    _record_platform_success(session=session, access=access)
    return envelope.model_dump(mode="json")


@router.get("/regions/{region_id}/early-career-access", response_model=None)
def public_early_career_access(
    region_id: str,
    request: Request,
    raw_api_key: str | None = Depends(_platform_api_key_header),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    access = _authorize_platform_request(
        session=session,
        request=request,
        product_id=PlatformApiProductId.EARLY_CAREER_ACCESS,
        raw_api_key=raw_api_key,
    )
    if isinstance(access, JSONResponse):
        return access

    unsupported = _unsupported_query_parameters(request, allowed=())
    if unsupported:
        return _deny_authorized_platform_request(
            session=session,
            access=access,
            status_code=400,
            code="UNSUPPORTED_QUERY",
            message=_unsupported_query_message(unsupported),
            decision_reason="unsupported_query",
            metadata={"unsupported_query_parameters": unsupported},
        )

    try:
        envelope = _service(session, output_service).early_career_access(region_id)
    except MissingRegionForOutput:
        return _deny_authorized_platform_request(
            session=session,
            access=access,
            status_code=404,
            code="NOT_FOUND",
            message="Region not found.",
            decision_reason="not_found",
        )

    _record_platform_success(session=session, access=access)
    return envelope.model_dump(mode="json")


@router.get("/markets/hiring-concentration", response_model=None)
def public_hiring_concentration(
    request: Request,
    raw_api_key: str | None = Depends(_platform_api_key_header),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    access = _authorize_platform_request(
        session=session,
        request=request,
        product_id=PlatformApiProductId.HIRING_CONCENTRATION,
        raw_api_key=raw_api_key,
    )
    if isinstance(access, JSONResponse):
        return access

    unsupported = _unsupported_query_parameters(request, allowed=("limit",))
    if unsupported:
        return _deny_authorized_platform_request(
            session=session,
            access=access,
            status_code=400,
            code="UNSUPPORTED_QUERY",
            message=_unsupported_query_message(unsupported),
            decision_reason="unsupported_query",
            metadata={"unsupported_query_parameters": unsupported},
        )

    limit, error = _parse_limit_query(request)
    if error is not None:
        return _deny_authorized_platform_request(
            session=session,
            access=access,
            status_code=400,
            code="VALIDATION_ERROR",
            message=error,
            decision_reason="validation_error",
        )

    envelope = _service(session, output_service).hiring_concentration(limit=limit)
    _record_platform_success(session=session, access=access)
    return envelope.model_dump(mode="json")


@router.get("/markets/compare", response_model=None)
def public_market_compare(
    request: Request,
    raw_api_key: str | None = Depends(_platform_api_key_header),
    session: Session = Depends(get_session),
    output_service: OutputAssemblyService = Depends(get_output_service),
) -> JSONResponse | dict:
    access = _authorize_platform_request(
        session=session,
        request=request,
        product_id=PlatformApiProductId.MARKET_COMPARISONS,
        raw_api_key=raw_api_key,
    )
    if isinstance(access, JSONResponse):
        return access

    unsupported = _unsupported_query_parameters(request, allowed=("region_a", "region_b"))
    if unsupported:
        return _deny_authorized_platform_request(
            session=session,
            access=access,
            status_code=400,
            code="UNSUPPORTED_QUERY",
            message=_unsupported_query_message(unsupported),
            decision_reason="unsupported_query",
            metadata={"unsupported_query_parameters": unsupported},
        )

    region_a = _required_query_value(request, "region_a")
    region_b = _required_query_value(request, "region_b")
    if region_a is None or region_b is None:
        return _deny_authorized_platform_request(
            session=session,
            access=access,
            status_code=400,
            code="VALIDATION_ERROR",
            message="region_a and region_b query parameters are required.",
            decision_reason="validation_error",
        )

    try:
        envelope = _service(session, output_service).market_comparison(region_a, region_b)
    except InvalidComparisonInput as exc:
        return _deny_authorized_platform_request(
            session=session,
            access=access,
            status_code=400,
            code="VALIDATION_ERROR",
            message=str(exc),
            decision_reason="validation_error",
        )
    except MissingRegionForOutput:
        return _deny_authorized_platform_request(
            session=session,
            access=access,
            status_code=404,
            code="NOT_FOUND",
            message="Region not found.",
            decision_reason="not_found",
        )

    _record_platform_success(session=session, access=access)
    return envelope.model_dump(mode="json")


def _authorize_platform_request(
    *,
    session: Session,
    request: Request,
    product_id: PlatformApiProductId,
    raw_api_key: str | None,
) -> _PlatformAccessContext | JSONResponse:
    endpoint = request.url.path
    method = request.method.upper()
    validation = validate_platform_api_key(session, raw_api_key)
    if not validation.valid:
        event_type = _validation_event_type(validation.reason)
        code = _validation_error_code(validation.reason)
        return _record_denial_and_error(
            session=session,
            api_key=validation.api_key,
            product_id=product_id,
            endpoint=endpoint,
            method=method,
            status_code=validation.status_code,
            code=code,
            message=validation.message,
            event_type=event_type,
            decision_reason=validation.reason.value,
            metadata={"reason": validation.reason.value},
        )

    api_key = validation.api_key
    if api_key is None:
        return _record_denial_and_error(
            session=session,
            api_key=None,
            product_id=product_id,
            endpoint=endpoint,
            method=method,
            status_code=401,
            code="INVALID_API_KEY",
            message="Invalid Platform API key.",
            event_type=PlatformApiAuditEventType.INVALID_KEY,
            decision_reason="invalid_key",
            metadata={"reason": "invalid_key"},
        )

    entitlement = decide_platform_api_entitlement(
        tier=api_key.tier,
        product_id=product_id,
        product_scopes=api_key.product_scopes_json,
    )
    if not entitlement.allowed:
        code = (
            "MISSING_PRODUCT_SCOPE"
            if entitlement.reason is PlatformApiEntitlementReason.MISSING_PRODUCT_SCOPE
            else "ENTITLEMENT_DENIED"
        )
        return _record_denial_and_error(
            session=session,
            api_key=api_key,
            product_id=product_id,
            endpoint=endpoint,
            method=method,
            status_code=403,
            code=code,
            message=entitlement.message,
            event_type=PlatformApiAuditEventType.ENTITLEMENT_DENIED,
            decision_reason=entitlement.reason.value,
            metadata={"reason": entitlement.reason.value, "tier": api_key.tier},
        )

    tier = PlatformApiTier(api_key.tier)
    rate_limit = check_platform_api_rate_limit(
        session,
        platform_api_key_id=api_key.platform_api_key_id,
        tier=tier,
    )
    if not rate_limit.allowed:
        return _record_denial_and_error(
            session=session,
            api_key=api_key,
            product_id=product_id,
            endpoint=endpoint,
            method=method,
            status_code=429,
            code="RATE_LIMIT_EXCEEDED",
            message="Platform API rate limit exceeded.",
            event_type=PlatformApiAuditEventType.RATE_LIMITED,
            decision_reason="rate_limit_exceeded",
            metadata={"rate_limit": rate_limit.model_dump(mode="json")},
        )

    monthly_limit = check_platform_api_monthly_usage_limit(
        session,
        platform_api_key_id=api_key.platform_api_key_id,
        tier=tier,
    )
    if not monthly_limit.allowed:
        return _record_denial_and_error(
            session=session,
            api_key=api_key,
            product_id=product_id,
            endpoint=endpoint,
            method=method,
            status_code=402,
            code="USAGE_LIMIT_EXCEEDED",
            message="Platform API monthly usage limit exceeded.",
            event_type=PlatformApiAuditEventType.USAGE_LIMIT_EXCEEDED,
            decision_reason="monthly_usage_limit_exceeded",
            metadata={"monthly_limit": monthly_limit.model_dump(mode="json")},
        )

    return _PlatformAccessContext(
        api_key=api_key,
        product_id=product_id,
        endpoint=endpoint,
        method=method,
        rate_limit=rate_limit,
        monthly_limit=monthly_limit,
    )


def _deny_authorized_platform_request(
    *,
    session: Session,
    access: _PlatformAccessContext,
    status_code: int,
    code: str,
    message: str,
    decision_reason: str,
    event_type: PlatformApiAuditEventType = PlatformApiAuditEventType.DENIED_REQUEST,
    metadata: dict[str, Any] | None = None,
) -> JSONResponse:
    return _record_denial_and_error(
        session=session,
        api_key=access.api_key,
        product_id=access.product_id,
        endpoint=access.endpoint,
        method=access.method,
        status_code=status_code,
        code=code,
        message=message,
        event_type=event_type,
        decision_reason=decision_reason,
        metadata=metadata,
    )


def _record_denial_and_error(
    *,
    session: Session,
    api_key: PlatformApiKey | None,
    product_id: PlatformApiProductId,
    endpoint: str,
    method: str,
    status_code: int,
    code: str,
    message: str,
    event_type: PlatformApiAuditEventType,
    decision_reason: str,
    metadata: dict[str, Any] | None = None,
) -> JSONResponse:
    record_platform_api_usage(
        session,
        api_key=api_key,
        product_id=product_id,
        endpoint=endpoint,
        method=method,
        request_units=0,
        status_code=status_code,
        outcome=PlatformApiUsageOutcome.DENIED,
        decision_reason=decision_reason,
    )
    record_platform_api_audit_event(
        session,
        api_key=api_key,
        product_id=product_id,
        endpoint=endpoint,
        method=method,
        event_type=event_type,
        decision=PlatformApiAuditDecision.DENIED,
        status_code=status_code,
        metadata=metadata,
    )
    return _platform_error(status_code, product_id, code, message)


def _record_platform_success(
    *,
    session: Session,
    access: _PlatformAccessContext,
) -> None:
    record_platform_api_usage(
        session,
        api_key=access.api_key,
        product_id=access.product_id,
        endpoint=access.endpoint,
        method=access.method,
        request_units=1,
        status_code=200,
        outcome=PlatformApiUsageOutcome.ALLOWED,
        decision_reason="allowed",
    )
    record_platform_api_audit_event(
        session,
        api_key=access.api_key,
        product_id=access.product_id,
        endpoint=access.endpoint,
        method=access.method,
        event_type=PlatformApiAuditEventType.ALLOWED_REQUEST,
        decision=PlatformApiAuditDecision.ALLOWED,
        status_code=200,
        metadata={
            "rate_limit": access.rate_limit.model_dump(mode="json"),
            "monthly_limit": access.monthly_limit.model_dump(mode="json"),
        },
    )
    mark_platform_api_key_used(session, access.api_key)


def _unsupported_query_parameters(
    request: Request,
    *,
    allowed: Iterable[str],
) -> list[str]:
    allowed_set = set(allowed)
    return sorted(set(request.query_params.keys()) - allowed_set)


def _unsupported_query_message(unsupported: list[str]) -> str:
    return f"Unsupported query parameter(s): {', '.join(unsupported)}."


def _parse_limit_query(request: Request) -> tuple[int, str | None]:
    raw = request.query_params.get("limit")
    if raw is None:
        return 50, None
    try:
        value = int(raw)
    except ValueError:
        return 50, "limit must be an integer between 1 and 100."
    if value < 1 or value > 100:
        return 50, "limit must be an integer between 1 and 100."
    return value, None


def _required_query_value(request: Request, name: str) -> str | None:
    value = request.query_params.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _validation_event_type(
    reason: PlatformApiKeyValidationReason,
) -> PlatformApiAuditEventType:
    if reason is PlatformApiKeyValidationReason.MISSING_KEY:
        return PlatformApiAuditEventType.MISSING_KEY
    if reason is PlatformApiKeyValidationReason.REVOKED_KEY:
        return PlatformApiAuditEventType.REVOKED_KEY
    return PlatformApiAuditEventType.INVALID_KEY


def _validation_error_code(reason: PlatformApiKeyValidationReason) -> str:
    if reason is PlatformApiKeyValidationReason.MISSING_KEY:
        return "MISSING_API_KEY"
    if reason is PlatformApiKeyValidationReason.REVOKED_KEY:
        return "REVOKED_API_KEY"
    return "INVALID_API_KEY"


def _platform_error(
    status_code: int,
    product_id: PlatformApiProductId,
    code: str,
    message: str,
) -> JSONResponse:
    envelope = build_public_api_error_envelope(
        product_id=product_id,
        code=code,
        message=message,
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))
