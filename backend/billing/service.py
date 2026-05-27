"""Billing service that maps provider events into internal monetization state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.billing.models import (
    BillingCustomerRef,
    BillingSubscriptionRef,
    BillingWebhookEvent,
)
from backend.billing.provider import (
    BillingCheckoutSessionRequest,
    BillingCheckoutSessionResult,
    BillingCustomerReference,
    BillingPortalSessionRequest,
    BillingPortalSessionResult,
    BillingProvider,
    BillingProviderClient,
    BillingProviderError,
    BillingServiceError,
    BillingWebhookProcessingResult,
    NormalizedBillingWebhookEvent,
)
from backend.billing.stripe_adapter import (
    StripeBillingAdapter,
    stripe_plan_by_price,
    stripe_price_by_plan,
)
from backend.config.settings import AppEnv, Settings
from backend.monetization.accounts import PlanAssignmentSource, PlanStatus
from backend.monetization.models import MonetizationPlanAssignment
from backend.monetization.plans import BuyerKind, PlanKey, plan_definition
from backend.monetization.repository import MonetizationRepository


class BillingStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: BillingProvider | None
    checkout_available: bool
    portal_available: bool
    checkout_plan_keys: tuple[PlanKey, ...] = Field(default_factory=tuple)
    disabled_reason: str | None = Field(default=None, min_length=1, max_length=240)


class BillingService:
    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        provider: BillingProviderClient | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._provider = provider

    def status(self) -> BillingStatus:
        return billing_status(self._settings)

    def create_checkout_session(
        self,
        *,
        user_id: str,
        plan_key: PlanKey | str,
        success_url: str | None = None,
        cancel_url: str | None = None,
    ) -> BillingCheckoutSessionResult:
        status = self.status()
        if not status.checkout_available:
            raise BillingServiceError(
                code="BILLING_CHECKOUT_UNAVAILABLE",
                message=status.disabled_reason or "Checkout is not configured.",
                status_code=503,
            )

        normalized_plan_key = _checkout_plan_key(plan_key)
        if normalized_plan_key not in status.checkout_plan_keys:
            raise BillingServiceError(
                code="BILLING_PLAN_NOT_MAPPED",
                message=(
                    f"{normalized_plan_key.value} is not configured for self-serve checkout."
                ),
            )

        price_id = stripe_price_by_plan(self._settings)[normalized_plan_key]
        provider = self._provider_or_stripe()
        repo = MonetizationRepository(self._session)
        account = repo.ensure_account_for_user(user_id=user_id)
        customer_ref = self._get_customer_ref(
            provider=BillingProvider.STRIPE,
            monetization_account_id=account.monetization_account_id,
        )

        result = provider.create_checkout_session(
            BillingCheckoutSessionRequest(
                monetization_account_id=account.monetization_account_id,
                user_id=user_id,
                plan_key=normalized_plan_key,
                provider_price_id=price_id,
                success_url=_select_redirect_url(
                    configured=self._settings.stripe_success_url,
                    override=success_url,
                    label="success_url",
                ),
                cancel_url=_select_redirect_url(
                    configured=self._settings.stripe_cancel_url,
                    override=cancel_url,
                    label="cancel_url",
                ),
                customer_ref=(
                    BillingCustomerReference(
                        provider=BillingProvider.STRIPE,
                        provider_customer_id=customer_ref.provider_customer_id,
                    )
                    if customer_ref is not None
                    else None
                ),
            )
        )
        if result.provider_customer_id:
            self._upsert_customer_ref(
                provider=BillingProvider.STRIPE,
                monetization_account_id=account.monetization_account_id,
                provider_customer_id=result.provider_customer_id,
            )
        return result

    def create_portal_session(
        self,
        *,
        user_id: str,
    ) -> BillingPortalSessionResult:
        status = self.status()
        if not status.portal_available:
            raise BillingServiceError(
                code="BILLING_PORTAL_UNAVAILABLE",
                message=status.disabled_reason or "Billing portal is not configured.",
                status_code=503,
            )

        repo = MonetizationRepository(self._session)
        account = repo.ensure_account_for_user(user_id=user_id)
        customer_ref = self._get_customer_ref(
            provider=BillingProvider.STRIPE,
            monetization_account_id=account.monetization_account_id,
        )
        if customer_ref is None:
            raise BillingServiceError(
                code="BILLING_CUSTOMER_NOT_FOUND",
                message=(
                    "No billing customer is linked to this account yet. "
                    "Review plan options before opening billing management."
                ),
                status_code=404,
            )

        return self._provider_or_stripe().create_portal_session(
            BillingPortalSessionRequest(
                customer_ref=BillingCustomerReference(
                    provider=BillingProvider.STRIPE,
                    provider_customer_id=customer_ref.provider_customer_id,
                ),
                return_url=self._settings.stripe_billing_portal_return_url,
            )
        )

    def process_stripe_webhook(
        self,
        *,
        raw_body: bytes,
        signature_header: str | None,
    ) -> BillingWebhookProcessingResult:
        event = self._provider_or_stripe().verify_webhook_event(
            raw_body=raw_body,
            signature_header=signature_header,
        )
        existing = self._get_webhook_event(
            provider=event.provider,
            provider_event_id=event.provider_event_id,
        )
        if existing is not None and existing.processing_status in {"processed", "ignored"}:
            return BillingWebhookProcessingResult(
                provider=event.provider,
                provider_event_id=event.provider_event_id,
                event_type=event.event_type,
                processed=False,
                duplicate=True,
                ignored=existing.processing_status == "ignored",
            )

        record = existing or self._create_webhook_event(event)
        try:
            result = self._handle_webhook_event(event)
        except Exception as exc:
            record.processing_status = "failed"
            record.processed_at = _now()
            record.error_code = exc.__class__.__name__[:64]
            self._session.flush()
            raise

        record.processing_status = "ignored" if result.ignored else "processed"
        record.processed_at = _now()
        record.error_code = None
        self._session.flush()
        return result

    def _handle_webhook_event(
        self,
        event: NormalizedBillingWebhookEvent,
    ) -> BillingWebhookProcessingResult:
        if event.event_type == "checkout.session.completed":
            return self._handle_checkout_completed(event)
        if event.event_type in {
            "customer.subscription.created",
            "customer.subscription.updated",
        }:
            return self._handle_subscription_upsert(event)
        if event.event_type == "customer.subscription.deleted":
            return self._handle_subscription_deleted(event)
        if event.event_type in {"invoice.payment_succeeded", "invoice.payment_failed"}:
            return self._ignored_event(event)
        return self._ignored_event(event)

    def _handle_checkout_completed(
        self,
        event: NormalizedBillingWebhookEvent,
    ) -> BillingWebhookProcessingResult:
        obj = event.data_object
        metadata = _metadata(obj)
        account_id = _string_value(obj, "client_reference_id") or metadata.get(
            "monetization_account_id"
        )
        plan_key = _checkout_plan_from_metadata(metadata, settings=self._settings)
        subscription_id = _string_value(obj, "subscription")
        customer_id = _string_value(obj, "customer")

        if account_id is None or plan_key is None or subscription_id is None:
            return self._ignored_event(event)

        self._upsert_customer_ref(
            provider=event.provider,
            monetization_account_id=account_id,
            provider_customer_id=customer_id,
        )
        subscription = self._upsert_subscription_ref(
            provider=event.provider,
            monetization_account_id=account_id,
            provider_subscription_id=subscription_id,
            provider_customer_id=customer_id,
            provider_price_id=stripe_price_by_plan(self._settings).get(plan_key),
            plan_key=plan_key,
            provider_status="checkout_completed",
            current_period_end=None,
            canceled_at=None,
        )
        self._grant_subscription_plan(
            subscription,
            plan_key=plan_key,
            provider_status="active",
            current_period_end=None,
        )
        return BillingWebhookProcessingResult(
            provider=event.provider,
            provider_event_id=event.provider_event_id,
            event_type=event.event_type,
            processed=True,
            monetization_account_id=account_id,
            plan_key=plan_key,
            account_status=PlanStatus.ACTIVE.value,
        )

    def _handle_subscription_upsert(
        self,
        event: NormalizedBillingWebhookEvent,
    ) -> BillingWebhookProcessingResult:
        obj = event.data_object
        subscription_id = _string_value(obj, "id")
        customer_id = _string_value(obj, "customer")
        provider_status = _string_value(obj, "status") or "unknown"
        price_id = _subscription_price_id(obj)
        plan_key = stripe_plan_by_price(self._settings).get(price_id or "")
        account_id = self._account_id_for_subscription_event(
            provider=event.provider,
            subscription_id=subscription_id,
            customer_id=customer_id,
            metadata=_metadata(obj),
        )
        if subscription_id is None or plan_key is None or account_id is None:
            return self._ignored_event(event)

        self._upsert_customer_ref(
            provider=event.provider,
            monetization_account_id=account_id,
            provider_customer_id=customer_id,
        )
        current_period_end = _timestamp_to_datetime(obj.get("current_period_end"))
        subscription = self._upsert_subscription_ref(
            provider=event.provider,
            monetization_account_id=account_id,
            provider_subscription_id=subscription_id,
            provider_customer_id=customer_id,
            provider_price_id=price_id,
            plan_key=plan_key,
            provider_status=provider_status,
            current_period_end=current_period_end,
            canceled_at=_timestamp_to_datetime(obj.get("canceled_at")),
        )
        internal_status = _internal_status_for_subscription(provider_status)
        if internal_status in {PlanStatus.ACTIVE, PlanStatus.TRIALING}:
            self._grant_subscription_plan(
                subscription,
                plan_key=plan_key,
                provider_status=provider_status,
                current_period_end=current_period_end,
            )
        else:
            self._revoke_subscription_plan(subscription, status=internal_status)

        return BillingWebhookProcessingResult(
            provider=event.provider,
            provider_event_id=event.provider_event_id,
            event_type=event.event_type,
            processed=True,
            monetization_account_id=account_id,
            plan_key=plan_key,
            account_status=internal_status.value,
        )

    def _handle_subscription_deleted(
        self,
        event: NormalizedBillingWebhookEvent,
    ) -> BillingWebhookProcessingResult:
        obj = event.data_object
        subscription_id = _string_value(obj, "id")
        subscription = (
            self._get_subscription_ref(
                provider=event.provider,
                provider_subscription_id=subscription_id,
            )
            if subscription_id is not None
            else None
        )
        if subscription is None:
            return self._ignored_event(event)
        subscription.provider_status = _string_value(obj, "status") or "canceled"
        subscription.canceled_at = _timestamp_to_datetime(obj.get("canceled_at")) or _now()
        self._revoke_subscription_plan(subscription, status=PlanStatus.CANCELED)
        return BillingWebhookProcessingResult(
            provider=event.provider,
            provider_event_id=event.provider_event_id,
            event_type=event.event_type,
            processed=True,
            monetization_account_id=subscription.monetization_account_id,
            plan_key=PlanKey(subscription.plan_key),
            account_status=PlanStatus.CANCELED.value,
        )

    def _ignored_event(
        self,
        event: NormalizedBillingWebhookEvent,
    ) -> BillingWebhookProcessingResult:
        return BillingWebhookProcessingResult(
            provider=event.provider,
            provider_event_id=event.provider_event_id,
            event_type=event.event_type,
            processed=True,
            ignored=True,
        )

    def _grant_subscription_plan(
        self,
        subscription: BillingSubscriptionRef,
        *,
        plan_key: PlanKey,
        provider_status: str,
        current_period_end: datetime | None,
    ) -> MonetizationPlanAssignment:
        internal_status = _internal_status_for_subscription(provider_status)
        if internal_status not in {PlanStatus.ACTIVE, PlanStatus.TRIALING}:
            raise BillingProviderError(
                code="BILLING_PROVIDER_EVENT_INVALID",
                message="Subscription status does not grant paid access.",
            )

        existing = (
            self._session.get(
                MonetizationPlanAssignment,
                subscription.active_plan_assignment_id,
            )
            if subscription.active_plan_assignment_id is not None
            else None
        )
        if existing is None:
            self._expire_other_provider_assignments(
                monetization_account_id=subscription.monetization_account_id,
            )
            existing = MonetizationRepository(self._session).assign_plan(
                monetization_account_id=subscription.monetization_account_id,
                plan_key=plan_key,
                plan_status=internal_status,
                assignment_source=PlanAssignmentSource.FUTURE_BILLING_PROVIDER,
                effective_at=_now(),
                expires_at=current_period_end,
                safe_metadata={},
            )
            subscription.active_plan_assignment_id = existing.plan_assignment_id
        else:
            existing.plan_key = plan_key.value
            existing.plan_status = internal_status.value
            existing.expires_at = current_period_end
            existing.updated_at = _now()

        subscription.plan_key = plan_key.value
        subscription.provider_status = provider_status
        subscription.current_period_end = current_period_end
        subscription.canceled_at = None
        self._session.flush()
        return existing

    def _revoke_subscription_plan(
        self,
        subscription: BillingSubscriptionRef,
        *,
        status: PlanStatus,
    ) -> None:
        assignment = (
            self._session.get(
                MonetizationPlanAssignment,
                subscription.active_plan_assignment_id,
            )
            if subscription.active_plan_assignment_id is not None
            else None
        )
        if assignment is not None:
            assignment.plan_status = status.value
            assignment.expires_at = _now()
            assignment.updated_at = _now()
        subscription.provider_status = status.value
        subscription.canceled_at = subscription.canceled_at or _now()
        self._session.flush()

    def _account_id_for_subscription_event(
        self,
        *,
        provider: BillingProvider,
        subscription_id: str | None,
        customer_id: str | None,
        metadata: dict[str, str],
    ) -> str | None:
        subscription = (
            self._get_subscription_ref(
                provider=provider,
                provider_subscription_id=subscription_id,
            )
            if subscription_id is not None
            else None
        )
        if subscription is not None:
            return subscription.monetization_account_id
        if customer_id is not None:
            customer = self._get_customer_ref_by_provider_id(
                provider=provider,
                provider_customer_id=customer_id,
            )
            if customer is not None:
                return customer.monetization_account_id
        return metadata.get("monetization_account_id")

    def _provider_or_stripe(self) -> BillingProviderClient:
        if self._provider is not None:
            return self._provider
        return StripeBillingAdapter(
            secret_key=self._settings.stripe_secret_key,
            webhook_secret=self._settings.stripe_webhook_secret,
        )

    def _get_customer_ref(
        self,
        *,
        provider: BillingProvider,
        monetization_account_id: str,
    ) -> BillingCustomerRef | None:
        return self._session.execute(
            select(BillingCustomerRef).where(
                BillingCustomerRef.provider == provider.value,
                BillingCustomerRef.monetization_account_id == monetization_account_id,
            )
        ).scalar_one_or_none()

    def _get_customer_ref_by_provider_id(
        self,
        *,
        provider: BillingProvider,
        provider_customer_id: str,
    ) -> BillingCustomerRef | None:
        return self._session.execute(
            select(BillingCustomerRef).where(
                BillingCustomerRef.provider == provider.value,
                BillingCustomerRef.provider_customer_id == provider_customer_id,
            )
        ).scalar_one_or_none()

    def _upsert_customer_ref(
        self,
        *,
        provider: BillingProvider,
        monetization_account_id: str,
        provider_customer_id: str | None,
    ) -> BillingCustomerRef | None:
        if not provider_customer_id:
            return None
        row = self._get_customer_ref_by_provider_id(
            provider=provider,
            provider_customer_id=provider_customer_id,
        )
        if row is None:
            row = self._get_customer_ref(
                provider=provider,
                monetization_account_id=monetization_account_id,
            )
        if row is None:
            row = BillingCustomerRef(
                billing_customer_ref_id=_new_id("billcust"),
                monetization_account_id=monetization_account_id,
                provider=provider.value,
                provider_customer_id=provider_customer_id,
                safe_metadata={},
            )
            self._session.add(row)
        else:
            row.monetization_account_id = monetization_account_id
            row.provider_customer_id = provider_customer_id
            row.updated_at = _now()
        self._session.flush()
        return row

    def _get_subscription_ref(
        self,
        *,
        provider: BillingProvider,
        provider_subscription_id: str,
    ) -> BillingSubscriptionRef | None:
        return self._session.execute(
            select(BillingSubscriptionRef).where(
                BillingSubscriptionRef.provider == provider.value,
                BillingSubscriptionRef.provider_subscription_id == provider_subscription_id,
            )
        ).scalar_one_or_none()

    def _upsert_subscription_ref(
        self,
        *,
        provider: BillingProvider,
        monetization_account_id: str,
        provider_subscription_id: str,
        provider_customer_id: str | None,
        provider_price_id: str | None,
        plan_key: PlanKey,
        provider_status: str,
        current_period_end: datetime | None,
        canceled_at: datetime | None,
    ) -> BillingSubscriptionRef:
        row = self._get_subscription_ref(
            provider=provider,
            provider_subscription_id=provider_subscription_id,
        )
        if row is None:
            row = BillingSubscriptionRef(
                billing_subscription_ref_id=_new_id("billsub"),
                monetization_account_id=monetization_account_id,
                provider=provider.value,
                provider_subscription_id=provider_subscription_id,
                provider_customer_id=provider_customer_id,
                provider_price_id=provider_price_id,
                plan_key=plan_key.value,
                provider_status=provider_status,
                current_period_end=current_period_end,
                canceled_at=canceled_at,
                active_plan_assignment_id=None,
                safe_metadata={},
            )
            self._session.add(row)
        else:
            row.monetization_account_id = monetization_account_id
            row.provider_customer_id = provider_customer_id
            row.provider_price_id = provider_price_id
            row.plan_key = plan_key.value
            row.provider_status = provider_status
            row.current_period_end = current_period_end
            row.canceled_at = canceled_at
            row.updated_at = _now()
        self._session.flush()
        return row

    def _get_webhook_event(
        self,
        *,
        provider: BillingProvider,
        provider_event_id: str,
    ) -> BillingWebhookEvent | None:
        return self._session.execute(
            select(BillingWebhookEvent).where(
                BillingWebhookEvent.provider == provider.value,
                BillingWebhookEvent.provider_event_id == provider_event_id,
            )
        ).scalar_one_or_none()

    def _create_webhook_event(
        self,
        event: NormalizedBillingWebhookEvent,
    ) -> BillingWebhookEvent:
        row = BillingWebhookEvent(
            billing_webhook_event_id=_new_id("billwh"),
            provider=event.provider.value,
            provider_event_id=event.provider_event_id,
            event_type=event.event_type,
            processing_status="pending",
            received_at=_now(),
            processed_at=None,
            error_code=None,
            safe_metadata={},
        )
        self._session.add(row)
        self._session.flush()
        return row

    def _expire_other_provider_assignments(
        self,
        *,
        monetization_account_id: str,
    ) -> None:
        rows = self._session.execute(
            select(MonetizationPlanAssignment).where(
                MonetizationPlanAssignment.monetization_account_id
                == monetization_account_id,
                MonetizationPlanAssignment.assignment_source
                == PlanAssignmentSource.FUTURE_BILLING_PROVIDER.value,
                MonetizationPlanAssignment.plan_status.in_(
                    [PlanStatus.ACTIVE.value, PlanStatus.TRIALING.value]
                ),
            )
        ).scalars()
        for row in rows:
            row.plan_status = PlanStatus.CANCELED.value
            row.expires_at = _now()
            row.updated_at = _now()


def billing_status(settings: Settings) -> BillingStatus:
    mapped_plan_keys = tuple(_checkout_eligible_plan_keys(settings))
    if settings.app_env == AppEnv.PUBLIC_DEMO:
        return BillingStatus(
            provider=BillingProvider.STRIPE if settings.stripe_secret_key else None,
            checkout_available=False,
            portal_available=False,
            checkout_plan_keys=(),
            disabled_reason="Checkout and billing portal are disabled in public demo.",
        )
    if not settings.stripe_secret_key:
        return BillingStatus(
            provider=None,
            checkout_available=False,
            portal_available=False,
            checkout_plan_keys=(),
            disabled_reason="Stripe secret key is not configured.",
        )
    if not settings.stripe_success_url or not settings.stripe_cancel_url:
        return BillingStatus(
            provider=BillingProvider.STRIPE,
            checkout_available=False,
            portal_available=bool(settings.stripe_billing_portal_return_url),
            checkout_plan_keys=(),
            disabled_reason="Stripe checkout redirect URLs are not configured.",
        )
    if not mapped_plan_keys:
        return BillingStatus(
            provider=BillingProvider.STRIPE,
            checkout_available=False,
            portal_available=bool(settings.stripe_billing_portal_return_url),
            checkout_plan_keys=(),
            disabled_reason="No paid plans are mapped to Stripe prices.",
        )
    return BillingStatus(
        provider=BillingProvider.STRIPE,
        checkout_available=True,
        portal_available=bool(settings.stripe_billing_portal_return_url),
        checkout_plan_keys=mapped_plan_keys,
        disabled_reason=None,
    )


def _checkout_eligible_plan_keys(settings: Settings) -> tuple[PlanKey, ...]:
    price_by_plan = stripe_price_by_plan(settings)
    eligible: list[PlanKey] = []
    for plan_key in (PlanKey.INDIVIDUAL_MONTHLY, PlanKey.INDIVIDUAL_ANNUAL, PlanKey.STUDENT_ANNUAL):
        if price_by_plan.get(plan_key):
            eligible.append(plan_key)
    return tuple(eligible)


def _checkout_plan_key(plan_key: PlanKey | str) -> PlanKey:
    try:
        normalized = PlanKey(plan_key)
    except ValueError as exc:
        raise BillingServiceError(
            code="BILLING_PLAN_UNKNOWN",
            message="Unknown plan key.",
        ) from exc
    if normalized is PlanKey.FREE:
        raise BillingServiceError(
            code="BILLING_PLAN_NOT_CHECKOUT_ELIGIBLE",
            message="The free plan does not require checkout.",
        )
    plan = plan_definition(normalized)
    if plan.buyer_kind is BuyerKind.INSTITUTIONAL:
        raise BillingServiceError(
            code="BILLING_PLAN_SALES_ASSISTED",
            message="Institutional licenses are handled through a sales-assisted workflow.",
        )
    return normalized


def _select_redirect_url(*, configured: str, override: str | None, label: str) -> str:
    if not override:
        return configured
    _validate_redirect_url(override, label=label)
    if _origin(override) != _origin(configured):
        raise BillingServiceError(
            code="BILLING_REDIRECT_URL_INVALID",
            message=f"{label} must use the configured application origin.",
        )
    return override


def _validate_redirect_url(value: str, *, label: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise BillingServiceError(
            code="BILLING_REDIRECT_URL_INVALID",
            message=f"{label} must be an HTTP(S) URL.",
        )
    if parsed.username or parsed.password or parsed.fragment:
        raise BillingServiceError(
            code="BILLING_REDIRECT_URL_INVALID",
            message=f"{label} is not an allowed redirect URL.",
        )


def _origin(value: str) -> str:
    parsed = urlsplit(value)
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _checkout_plan_from_metadata(
    metadata: dict[str, str],
    *,
    settings: Settings,
) -> PlanKey | None:
    raw = metadata.get("internal_plan_key")
    if raw is None:
        return None
    try:
        plan_key = PlanKey(raw)
    except ValueError:
        return None
    if plan_key not in _checkout_eligible_plan_keys(settings):
        return None
    return plan_key


def _internal_status_for_subscription(provider_status: str) -> PlanStatus:
    normalized = provider_status.casefold()
    if normalized == "trialing":
        return PlanStatus.TRIALING
    if normalized == "active":
        return PlanStatus.ACTIVE
    if normalized in {"past_due", "unpaid", "incomplete", "paused"}:
        return PlanStatus.PAUSED
    if normalized in {"canceled", "cancelled"}:
        return PlanStatus.CANCELED
    return PlanStatus.EXPIRED


def _metadata(obj: dict[str, Any]) -> dict[str, str]:
    raw = obj.get("metadata")
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _subscription_price_id(obj: dict[str, Any]) -> str | None:
    items = obj.get("items")
    data = items.get("data") if isinstance(items, dict) else None
    if not isinstance(data, list) or not data:
        return None
    first = data[0]
    if not isinstance(first, dict):
        return None
    price = first.get("price")
    if not isinstance(price, dict):
        return None
    value = price.get("id")
    return value if isinstance(value, str) and value else None


def _string_value(obj: dict[str, Any], key: str) -> str | None:
    value = obj.get(key)
    return value if isinstance(value, str) and value else None


def _timestamp_to_datetime(value: Any) -> datetime | None:
    if not isinstance(value, int):
        return None
    return datetime.fromtimestamp(value, tz=UTC)


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"
