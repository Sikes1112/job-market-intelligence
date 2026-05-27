"""Billing adapter API routes.

These endpoints expose checkout/portal session creation and Stripe webhook
ingestion without making Stripe the product authority. Entitlements continue to
come from internal monetization plan assignments.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.api.dependencies import CurrentUser, get_current_user, get_session
from backend.api.envelope import error_envelope, lightweight_success_envelope
from backend.billing.provider import BillingServiceError
from backend.billing.service import BillingService

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_key: str = Field(min_length=1, max_length=64)
    success_url: str | None = Field(default=None, min_length=1, max_length=2048)
    cancel_url: str | None = Field(default=None, min_length=1, max_length=2048)


@router.get("/status")
def get_billing_status(request: Request, session: Session = Depends(get_session)) -> dict:
    service = _service(request=request, session=session)
    return lightweight_success_envelope(data=service.status().model_dump(mode="json"))


@router.post("/checkout-session", response_model=None)
def create_checkout_session(
    body: CheckoutSessionRequest,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    service = _service(request=request, session=session)
    try:
        result = service.create_checkout_session(
            user_id=current.user.user_id,
            plan_key=body.plan_key,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
    except BillingServiceError as exc:
        return _billing_error(exc)

    return lightweight_success_envelope(
        data={
            "provider": result.provider.value,
            "checkout_session_id": result.checkout_session_id,
            "checkout_url": result.checkout_url,
            "plan_key": body.plan_key,
            "access_granted": False,
        }
    )


@router.post("/portal-session", response_model=None)
def create_portal_session(
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    service = _service(request=request, session=session)
    try:
        result = service.create_portal_session(user_id=current.user.user_id)
    except BillingServiceError as exc:
        return _billing_error(exc)

    return lightweight_success_envelope(
        data={
            "provider": result.provider.value,
            "portal_session_id": result.portal_session_id,
            "portal_url": result.portal_url,
        }
    )


@router.post("/stripe/webhook", response_model=None)
async def stripe_webhook(
    request: Request,
    session: Session = Depends(get_session),
) -> JSONResponse | dict:
    service = _service(request=request, session=session)
    try:
        result = service.process_stripe_webhook(
            raw_body=await request.body(),
            signature_header=request.headers.get("stripe-signature"),
        )
    except BillingServiceError as exc:
        return _billing_error(exc)

    return lightweight_success_envelope(data={"event": result.model_dump(mode="json")})


def _service(*, request: Request, session: Session) -> BillingService:
    return BillingService(
        session=session,
        settings=request.app.state.settings,
        provider=getattr(request.app.state, "billing_provider", None),
    )


def _billing_error(exc: BillingServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(code=exc.code, message=exc.message),
    )
