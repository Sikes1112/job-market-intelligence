"""Provider-neutral billing contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from backend.monetization.plans import PlanKey


class BillingProvider(StrEnum):
    STRIPE = "stripe"


class BillingServiceError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class BillingProviderError(BillingServiceError):
    pass


class BillingSignatureError(BillingServiceError):
    pass


class BillingPlanMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: BillingProvider
    plan_key: PlanKey
    provider_price_id: str = Field(min_length=1, max_length=256)


class BillingCustomerReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: BillingProvider
    provider_customer_id: str = Field(min_length=1, max_length=256)


class BillingCheckoutSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    monetization_account_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=64)
    plan_key: PlanKey
    provider_price_id: str = Field(min_length=1, max_length=256)
    success_url: str = Field(min_length=1, max_length=2048)
    cancel_url: str = Field(min_length=1, max_length=2048)
    customer_ref: BillingCustomerReference | None = None


class BillingCheckoutSessionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: BillingProvider
    checkout_session_id: str = Field(min_length=1, max_length=256)
    checkout_url: str = Field(min_length=1, max_length=2048)
    provider_customer_id: str | None = Field(default=None, min_length=1, max_length=256)


class BillingPortalSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_ref: BillingCustomerReference
    return_url: str = Field(min_length=1, max_length=2048)


class BillingPortalSessionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: BillingProvider
    portal_session_id: str = Field(min_length=1, max_length=256)
    portal_url: str = Field(min_length=1, max_length=2048)


class NormalizedBillingWebhookEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: BillingProvider
    provider_event_id: str = Field(min_length=1, max_length=256)
    event_type: str = Field(min_length=1, max_length=128)
    created_at: datetime | None = None
    data_object: dict[str, Any]


class BillingWebhookProcessingResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: BillingProvider
    provider_event_id: str = Field(min_length=1, max_length=256)
    event_type: str = Field(min_length=1, max_length=128)
    processed: bool
    duplicate: bool = False
    ignored: bool = False
    monetization_account_id: str | None = Field(default=None, min_length=1, max_length=64)
    plan_key: PlanKey | None = None
    account_status: str | None = Field(default=None, min_length=1, max_length=32)


class BillingProviderClient(Protocol):
    provider: BillingProvider

    def create_checkout_session(
        self,
        request: BillingCheckoutSessionRequest,
    ) -> BillingCheckoutSessionResult:
        ...

    def create_portal_session(
        self,
        request: BillingPortalSessionRequest,
    ) -> BillingPortalSessionResult:
        ...

    def verify_webhook_event(
        self,
        *,
        raw_body: bytes,
        signature_header: str | None,
    ) -> NormalizedBillingWebhookEvent:
        ...
