from __future__ import annotations

import ast
import hashlib
import hmac
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.billing.models import BillingCustomerRef, BillingWebhookEvent
from backend.billing.provider import (
    BillingCheckoutSessionRequest,
    BillingCheckoutSessionResult,
    BillingPortalSessionRequest,
    BillingPortalSessionResult,
    BillingProvider,
    NormalizedBillingWebhookEvent,
)
from backend.billing.stripe_adapter import StripeBillingAdapter
from backend.config.settings import Settings
from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.models import MonetizationPlanAssignment
from backend.monetization.plans import PlanKey

REPO_ROOT = Path(__file__).resolve().parents[1]
WEBHOOK_SECRET = "whsec_test_secret"


class FakeStripeProvider:
    provider = BillingProvider.STRIPE

    def __init__(self) -> None:
        self.checkout_requests: list[BillingCheckoutSessionRequest] = []
        self.portal_requests: list[BillingPortalSessionRequest] = []

    def create_checkout_session(
        self,
        request: BillingCheckoutSessionRequest,
    ) -> BillingCheckoutSessionResult:
        self.checkout_requests.append(request)
        return BillingCheckoutSessionResult(
            provider=BillingProvider.STRIPE,
            checkout_session_id="cs_test_mock",
            checkout_url="https://checkout.stripe.test/session/cs_test_mock",
            provider_customer_id=None,
        )

    def create_portal_session(
        self,
        request: BillingPortalSessionRequest,
    ) -> BillingPortalSessionResult:
        self.portal_requests.append(request)
        return BillingPortalSessionResult(
            provider=BillingProvider.STRIPE,
            portal_session_id="bps_test_mock",
            portal_url="https://billing.stripe.test/session/bps_test_mock",
        )

    def verify_webhook_event(
        self,
        *,
        raw_body: bytes,
        signature_header: str | None,
    ) -> NormalizedBillingWebhookEvent:
        return StripeBillingAdapter(
            secret_key="",
            webhook_secret=WEBHOOK_SECRET,
        ).verify_webhook_event(raw_body=raw_body, signature_header=signature_header)


def test_missing_stripe_config_disables_checkout_gracefully(api_client) -> None:
    status = api_client.get("/billing/status")
    checkout = api_client.post(
        "/billing/checkout-session",
        headers=_auth_headers("auth0|billing_missing"),
        json={"plan_key": PlanKey.INDIVIDUAL_MONTHLY.value},
    )

    assert status.status_code == 200
    assert status.json()["data"]["checkout_available"] is False
    assert checkout.status_code == 503
    body = json.dumps(checkout.json()).casefold()
    assert "sk_test" not in body
    assert "whsec" not in body


def test_free_unknown_and_unmapped_plans_cannot_create_checkout(
    session: Session,
) -> None:
    provider = FakeStripeProvider()
    client = _billing_client(session, _stripe_settings(), provider)
    headers = _auth_headers("auth0|billing_plan_validation")

    free = client.post(
        "/billing/checkout-session",
        headers=headers,
        json={"plan_key": PlanKey.FREE.value},
    )
    unknown = client.post(
        "/billing/checkout-session",
        headers=headers,
        json={"plan_key": "not_a_plan"},
    )
    unmapped = client.post(
        "/billing/checkout-session",
        headers=headers,
        json={"plan_key": PlanKey.STUDENT_ANNUAL.value},
    )

    assert free.status_code == 400
    assert free.json()["error"]["code"] == "BILLING_PLAN_NOT_CHECKOUT_ELIGIBLE"
    assert unknown.status_code == 400
    assert unknown.json()["error"]["code"] == "BILLING_PLAN_UNKNOWN"
    assert unmapped.status_code == 400
    assert unmapped.json()["error"]["code"] == "BILLING_PLAN_NOT_MAPPED"
    assert provider.checkout_requests == []


def test_mapped_paid_plan_creates_checkout_without_granting_entitlement(
    session: Session,
) -> None:
    provider = FakeStripeProvider()
    client = _billing_client(session, _stripe_settings(), provider)
    headers = _auth_headers("auth0|billing_checkout")

    checkout = client.post(
        "/billing/checkout-session",
        headers=headers,
        json={"plan_key": PlanKey.INDIVIDUAL_MONTHLY.value},
    )
    access = client.get(
        "/monetization/access-preview",
        headers=headers,
        params={"feature_key": MonetizationFeatureKey.SAVED_WATCHLISTS.value},
    )

    assert checkout.status_code == 200
    payload = checkout.json()["data"]
    assert payload["checkout_url"].startswith("https://checkout.stripe.test/")
    assert payload["access_granted"] is False
    assert "price_" not in json.dumps(payload)
    assert provider.checkout_requests[0].plan_key is PlanKey.INDIVIDUAL_MONTHLY
    assert access.status_code == 200
    assert access.json()["data"]["decision"]["allowed"] is False


def test_portal_requires_existing_customer_ref_and_returns_safe_url(
    session: Session,
) -> None:
    provider = FakeStripeProvider()
    client = _billing_client(session, _stripe_settings(), provider)
    headers = _auth_headers("auth0|billing_portal")

    missing = client.post("/billing/portal-session", headers=headers)
    assert missing.status_code == 404
    assert "cus_" not in json.dumps(missing.json())

    account_id = _account_id(client, headers)
    session.add(
        BillingCustomerRef(
            billing_customer_ref_id="billcust_test_portal",
            monetization_account_id=account_id,
            provider=BillingProvider.STRIPE.value,
            provider_customer_id="cus_test_portal",
            safe_metadata={},
        )
    )
    session.flush()

    portal = client.post("/billing/portal-session", headers=headers)

    assert portal.status_code == 200
    payload = portal.json()["data"]
    assert payload["portal_url"].startswith("https://billing.stripe.test/")
    assert "cus_test_portal" not in json.dumps(payload)
    assert provider.portal_requests[0].customer_ref.provider_customer_id == "cus_test_portal"


def test_verified_checkout_webhook_grants_internal_plan_and_is_idempotent(
    session: Session,
) -> None:
    provider = FakeStripeProvider()
    client = _billing_client(session, _stripe_settings(), provider)
    headers = _auth_headers("auth0|billing_webhook")
    checkout = client.post(
        "/billing/checkout-session",
        headers=headers,
        json={"plan_key": PlanKey.INDIVIDUAL_MONTHLY.value},
    )
    assert checkout.status_code == 200
    account_id = _account_id(client, headers)

    body, signature = _signed_event(
        {
            "id": "evt_checkout_completed",
            "type": "checkout.session.completed",
            "created": int(datetime.now(UTC).timestamp()),
            "data": {
                "object": {
                    "id": "cs_test_completed",
                    "client_reference_id": account_id,
                    "customer": "cus_test_webhook",
                    "subscription": "sub_test_webhook",
                    "metadata": {
                        "internal_plan_key": PlanKey.INDIVIDUAL_MONTHLY.value,
                        "monetization_account_id": account_id,
                    },
                }
            },
        }
    )

    first = client.post(
        "/billing/stripe/webhook",
        content=body,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )
    second = client.post(
        "/billing/stripe/webhook",
        content=body,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )
    access = client.get(
        "/monetization/access-preview",
        headers=headers,
        params={"feature_key": MonetizationFeatureKey.SAVED_WATCHLISTS.value},
    )

    assert first.status_code == 200
    assert first.json()["data"]["event"]["processed"] is True
    assert second.status_code == 200
    assert second.json()["data"]["event"]["duplicate"] is True
    assert access.json()["data"]["decision"]["allowed"] is True
    assignments = session.execute(
        select(MonetizationPlanAssignment).where(
            MonetizationPlanAssignment.monetization_account_id == account_id,
            MonetizationPlanAssignment.plan_key == PlanKey.INDIVIDUAL_MONTHLY.value,
        )
    ).scalars()
    assert len(list(assignments)) == 1


def test_checkout_webhook_ignores_unmapped_metadata_plan_without_granting_access(
    session: Session,
) -> None:
    client = _billing_client(session, _stripe_settings(), FakeStripeProvider())
    headers = _auth_headers("auth0|billing_unmapped_webhook")
    checkout = client.post(
        "/billing/checkout-session",
        headers=headers,
        json={"plan_key": PlanKey.INDIVIDUAL_MONTHLY.value},
    )
    assert checkout.status_code == 200
    account_id = _account_id(client, headers)

    body, signature = _signed_event(
        {
            "id": "evt_checkout_unmapped_metadata",
            "type": "checkout.session.completed",
            "created": int(datetime.now(UTC).timestamp()),
            "data": {
                "object": {
                    "id": "cs_test_unmapped_metadata",
                    "client_reference_id": account_id,
                    "customer": "cus_test_unmapped_metadata",
                    "subscription": "sub_test_unmapped_metadata",
                    "metadata": {
                        "internal_plan_key": PlanKey.INDIVIDUAL_ANNUAL.value,
                        "monetization_account_id": account_id,
                    },
                }
            },
        }
    )

    webhook = client.post(
        "/billing/stripe/webhook",
        content=body,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )
    access = client.get(
        "/monetization/access-preview",
        headers=headers,
        params={"feature_key": MonetizationFeatureKey.SAVED_WATCHLISTS.value},
    )

    assert webhook.status_code == 200
    assert webhook.json()["data"]["event"]["ignored"] is True
    assert access.json()["data"]["decision"]["allowed"] is False
    assignments = session.execute(
        select(MonetizationPlanAssignment).where(
            MonetizationPlanAssignment.monetization_account_id == account_id,
        )
    ).scalars()
    assert list(assignments) == []


def test_subscription_deleted_webhook_revokes_internal_paid_assignment(
    session: Session,
) -> None:
    provider = FakeStripeProvider()
    client = _billing_client(session, _stripe_settings(), provider)
    headers = _auth_headers("auth0|billing_cancel")
    client.post(
        "/billing/checkout-session",
        headers=headers,
        json={"plan_key": PlanKey.INDIVIDUAL_MONTHLY.value},
    )
    account_id = _account_id(client, headers)
    completed_body, completed_signature = _signed_event(
        {
            "id": "evt_checkout_for_cancel",
            "type": "checkout.session.completed",
            "created": int(datetime.now(UTC).timestamp()),
            "data": {
                "object": {
                    "id": "cs_test_cancel",
                    "client_reference_id": account_id,
                    "customer": "cus_test_cancel",
                    "subscription": "sub_test_cancel",
                    "metadata": {
                        "internal_plan_key": PlanKey.INDIVIDUAL_MONTHLY.value,
                        "monetization_account_id": account_id,
                    },
                }
            },
        }
    )
    client.post(
        "/billing/stripe/webhook",
        content=completed_body,
        headers={"stripe-signature": completed_signature, "content-type": "application/json"},
    )

    deleted_body, deleted_signature = _signed_event(
        {
            "id": "evt_subscription_deleted",
            "type": "customer.subscription.deleted",
            "created": int(datetime.now(UTC).timestamp()),
            "data": {
                "object": {
                    "id": "sub_test_cancel",
                    "customer": "cus_test_cancel",
                    "status": "canceled",
                    "canceled_at": int(datetime.now(UTC).timestamp()),
                }
            },
        }
    )
    deleted = client.post(
        "/billing/stripe/webhook",
        content=deleted_body,
        headers={"stripe-signature": deleted_signature, "content-type": "application/json"},
    )
    access = client.get(
        "/monetization/access-preview",
        headers=headers,
        params={"feature_key": MonetizationFeatureKey.SAVED_WATCHLISTS.value},
    )

    assert deleted.status_code == 200
    assert deleted.json()["data"]["event"]["account_status"] == "canceled"
    decision = access.json()["data"]["decision"]
    assert decision["allowed"] is False
    assert decision["plan_key"] == PlanKey.FREE.value
    assert decision["account_status"] in {"canceled", "expired"}


def test_subscription_created_maps_price_to_internal_plan_without_exposing_provider_ids(
    session: Session,
) -> None:
    client = _billing_client(session, _stripe_settings(), FakeStripeProvider())
    headers = _auth_headers("auth0|billing_subscription_created")
    client.post(
        "/billing/checkout-session",
        headers=headers,
        json={"plan_key": PlanKey.INDIVIDUAL_MONTHLY.value},
    )
    account_id = _account_id(client, headers)

    body, signature = _signed_event(
        {
            "id": "evt_subscription_created",
            "type": "customer.subscription.created",
            "created": int(datetime.now(UTC).timestamp()),
            "data": {
                "object": {
                    "id": "sub_test_created",
                    "customer": "cus_test_created",
                    "status": "active",
                    "current_period_end": int(datetime.now(UTC).timestamp()) + 3600,
                    "metadata": {"monetization_account_id": account_id},
                    "items": {
                        "data": [
                            {
                                "price": {
                                    "id": "price_individual_monthly_test",
                                }
                            }
                        ]
                    },
                }
            },
        }
    )

    webhook = client.post(
        "/billing/stripe/webhook",
        content=body,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )
    access = client.get(
        "/monetization/access-preview",
        headers=headers,
        params={"feature_key": MonetizationFeatureKey.ALERTS.value},
    )

    assert webhook.status_code == 200
    assert webhook.json()["data"]["event"]["plan_key"] == PlanKey.INDIVIDUAL_MONTHLY.value
    serialized_decision = json.dumps(access.json())
    assert access.json()["data"]["decision"]["allowed"] is True
    assert "cus_test_created" not in serialized_decision
    assert "sub_test_created" not in serialized_decision
    assert "price_individual_monthly_test" not in serialized_decision


def test_invalid_webhook_signature_is_rejected_without_event_record(
    session: Session,
) -> None:
    client = _billing_client(session, _stripe_settings(), FakeStripeProvider())

    response = client.post(
        "/billing/stripe/webhook",
        content=b'{"id":"evt_bad","type":"checkout.session.completed","data":{"object":{}}}',
        headers={"stripe-signature": "t=1,v1=bad", "content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BILLING_WEBHOOK_SIGNATURE_INVALID"
    assert session.query(BillingWebhookEvent).count() == 0


def test_billing_modules_do_not_import_recommendation_ranking() -> None:
    billing_root = REPO_ROOT / "backend" / "billing"
    for path in billing_root.glob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(name.startswith("backend.recommendations") for name in imports), path


def _billing_client(
    session: Session,
    settings: Settings,
    provider: FakeStripeProvider | None = None,
) -> TestClient:
    app = create_app(engine=session.bind, settings=settings)

    def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    app.state.billing_provider = provider
    return TestClient(app)


def _stripe_settings() -> Settings:
    return Settings(
        app_env="test",
        stripe_secret_key="sk_test_secret",
        stripe_webhook_secret=WEBHOOK_SECRET,
        stripe_success_url="https://app.example/billing/success",
        stripe_cancel_url="https://app.example/markets/plans",
        stripe_billing_portal_return_url="https://app.example/account",
        stripe_price_individual_monthly="price_individual_monthly_test",
        _env_file=None,
    )


def _account_id(client: TestClient, headers: dict[str, str]) -> str:
    response = client.get("/monetization/me", headers=headers)
    assert response.status_code == 200
    account_id = response.json()["data"]["account"]["monetization_account_id"]
    assert isinstance(account_id, str)
    return account_id


def _signed_event(payload: dict[str, Any]) -> tuple[bytes, str]:
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(datetime.now(UTC).timestamp()))
    signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return body, f"t={timestamp},v1={signature}"


def _auth_headers(subject: str) -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"User {suffix}",
        "picture": f"https://cdn.example.com/{suffix}.png",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}
