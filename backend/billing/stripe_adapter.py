"""Stripe billing provider adapter.

The adapter owns Stripe HTTP calls and webhook signature verification. It does
not decide product access; verified events are normalized for the billing
service, which updates internal monetization plan assignments.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.billing.provider import (
    BillingCheckoutSessionRequest,
    BillingCheckoutSessionResult,
    BillingPlanMapping,
    BillingPortalSessionRequest,
    BillingPortalSessionResult,
    BillingProvider,
    BillingProviderError,
    BillingSignatureError,
    NormalizedBillingWebhookEvent,
)
from backend.config.settings import Settings
from backend.monetization.plans import PlanKey

STRIPE_API_BASE = "https://api.stripe.com/v1"
WEBHOOK_TOLERANCE_SECONDS = 300


class StripeBillingAdapter:
    provider = BillingProvider.STRIPE

    def __init__(self, *, secret_key: str, webhook_secret: str = "") -> None:
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret

    def create_checkout_session(
        self,
        request: BillingCheckoutSessionRequest,
    ) -> BillingCheckoutSessionResult:
        params: dict[str, str] = {
            "mode": "subscription",
            "success_url": request.success_url,
            "cancel_url": request.cancel_url,
            "client_reference_id": request.monetization_account_id,
            "line_items[0][price]": request.provider_price_id,
            "line_items[0][quantity]": "1",
            "metadata[internal_plan_key]": request.plan_key.value,
            "metadata[monetization_account_id]": request.monetization_account_id,
            "subscription_data[metadata][internal_plan_key]": request.plan_key.value,
            "subscription_data[metadata][monetization_account_id]": (
                request.monetization_account_id
            ),
        }
        if request.customer_ref is not None:
            params["customer"] = request.customer_ref.provider_customer_id

        payload = self._post("/checkout/sessions", params)
        session_id = _required_str(payload, "id")
        checkout_url = _required_str(payload, "url")
        customer_id = payload.get("customer")
        return BillingCheckoutSessionResult(
            provider=self.provider,
            checkout_session_id=session_id,
            checkout_url=checkout_url,
            provider_customer_id=customer_id if isinstance(customer_id, str) else None,
        )

    def create_portal_session(
        self,
        request: BillingPortalSessionRequest,
    ) -> BillingPortalSessionResult:
        payload = self._post(
            "/billing_portal/sessions",
            {
                "customer": request.customer_ref.provider_customer_id,
                "return_url": request.return_url,
            },
        )
        return BillingPortalSessionResult(
            provider=self.provider,
            portal_session_id=_required_str(payload, "id"),
            portal_url=_required_str(payload, "url"),
        )

    def verify_webhook_event(
        self,
        *,
        raw_body: bytes,
        signature_header: str | None,
    ) -> NormalizedBillingWebhookEvent:
        if not self._webhook_secret:
            raise BillingSignatureError(
                code="BILLING_WEBHOOK_DISABLED",
                message="Stripe webhook handling is not configured.",
                status_code=503,
            )
        timestamp, signatures = _parse_stripe_signature(signature_header)
        _verify_signature(
            raw_body=raw_body,
            timestamp=timestamp,
            signatures=signatures,
            webhook_secret=self._webhook_secret,
        )
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BillingSignatureError(
                code="BILLING_WEBHOOK_INVALID_PAYLOAD",
                message="Stripe webhook payload is invalid.",
            ) from exc

        data = payload.get("data")
        data_object = data.get("object") if isinstance(data, dict) else None
        if not isinstance(data_object, dict):
            raise BillingSignatureError(
                code="BILLING_WEBHOOK_INVALID_PAYLOAD",
                message="Stripe webhook payload does not include an event object.",
            )

        created = payload.get("created")
        return NormalizedBillingWebhookEvent(
            provider=self.provider,
            provider_event_id=_required_str(payload, "id"),
            event_type=_required_str(payload, "type"),
            created_at=_timestamp_to_datetime(created) if isinstance(created, int) else None,
            data_object=data_object,
        )

    def _post(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        if not self._secret_key:
            raise BillingProviderError(
                code="BILLING_PROVIDER_UNAVAILABLE",
                message="Stripe is not configured.",
                status_code=503,
            )
        encoded = urlencode(params).encode("utf-8")
        auth = base64.b64encode(f"{self._secret_key}:".encode()).decode("ascii")
        request = Request(
            f"{STRIPE_API_BASE}{path}",
            data=encoded,
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310
                body = response.read()
        except HTTPError as exc:
            raise BillingProviderError(
                code="BILLING_PROVIDER_ERROR",
                message="Stripe rejected the billing request.",
                status_code=502,
            ) from exc
        except URLError as exc:
            raise BillingProviderError(
                code="BILLING_PROVIDER_ERROR",
                message="Stripe could not be reached.",
                status_code=502,
            ) from exc

        try:
            parsed = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BillingProviderError(
                code="BILLING_PROVIDER_ERROR",
                message="Stripe returned an invalid response.",
                status_code=502,
            ) from exc
        if not isinstance(parsed, dict):
            raise BillingProviderError(
                code="BILLING_PROVIDER_ERROR",
                message="Stripe returned an invalid response.",
                status_code=502,
            )
        return parsed


def stripe_plan_mappings(settings: Settings) -> tuple[BillingPlanMapping, ...]:
    raw = {
        PlanKey.INDIVIDUAL_MONTHLY: settings.stripe_price_individual_monthly,
        PlanKey.INDIVIDUAL_ANNUAL: settings.stripe_price_individual_annual,
        PlanKey.STUDENT_ANNUAL: settings.stripe_price_student_annual,
        PlanKey.CAREER_CENTER_LICENSE: settings.stripe_price_career_center_license,
        PlanKey.BOOTCAMP_LICENSE: settings.stripe_price_bootcamp_license,
        PlanKey.UNIVERSITY_LICENSE: settings.stripe_price_university_license,
        PlanKey.WORKFORCE_BOARD_LICENSE: settings.stripe_price_workforce_board_license,
    }
    return tuple(
        BillingPlanMapping(
            provider=BillingProvider.STRIPE,
            plan_key=plan_key,
            provider_price_id=price_id,
        )
        for plan_key, price_id in raw.items()
        if price_id
    )


def stripe_price_by_plan(settings: Settings) -> dict[PlanKey, str]:
    return {
        mapping.plan_key: mapping.provider_price_id
        for mapping in stripe_plan_mappings(settings)
    }


def stripe_plan_by_price(settings: Settings) -> dict[str, PlanKey]:
    return {
        mapping.provider_price_id: mapping.plan_key
        for mapping in stripe_plan_mappings(settings)
    }


def _parse_stripe_signature(signature_header: str | None) -> tuple[str, tuple[str, ...]]:
    if not signature_header:
        raise BillingSignatureError(
            code="BILLING_WEBHOOK_SIGNATURE_INVALID",
            message="Stripe signature header is missing.",
        )
    parts: dict[str, list[str]] = {}
    for item in signature_header.split(","):
        key, separator, value = item.partition("=")
        if not separator:
            continue
        parts.setdefault(key, []).append(value)
    timestamp = parts.get("t", [""])[0]
    signatures = tuple(value for value in parts.get("v1", []) if value)
    if not timestamp or not signatures:
        raise BillingSignatureError(
            code="BILLING_WEBHOOK_SIGNATURE_INVALID",
            message="Stripe signature header is invalid.",
        )
    return timestamp, signatures


def _verify_signature(
    *,
    raw_body: bytes,
    timestamp: str,
    signatures: tuple[str, ...],
    webhook_secret: str,
) -> None:
    try:
        event_time = int(timestamp)
    except ValueError as exc:
        raise BillingSignatureError(
            code="BILLING_WEBHOOK_SIGNATURE_INVALID",
            message="Stripe signature timestamp is invalid.",
        ) from exc
    now = int(datetime.now(UTC).timestamp())
    if abs(now - event_time) > WEBHOOK_TOLERANCE_SECONDS:
        raise BillingSignatureError(
            code="BILLING_WEBHOOK_SIGNATURE_INVALID",
            message="Stripe signature timestamp is outside the allowed tolerance.",
        )

    signed_payload = timestamp.encode("utf-8") + b"." + raw_body
    expected = hmac.new(
        webhook_secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        raise BillingSignatureError(
            code="BILLING_WEBHOOK_SIGNATURE_INVALID",
            message="Stripe signature verification failed.",
        )


def _timestamp_to_datetime(value: int) -> datetime:
    return datetime.fromtimestamp(value, tz=UTC)


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise BillingProviderError(
            code="BILLING_PROVIDER_ERROR",
            message="Stripe returned an incomplete response.",
            status_code=502,
        )
    return value
