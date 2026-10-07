from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.geography.models import Region
from backend.monetization.accounts import (
    MonetizationAccountType,
    PlanAssignmentSource,
    PlanStatus,
)
from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.plans import PlanKey
from backend.monetization.repository import MonetizationRepository
from backend.scoring.models import RegionMarketScore

NOW = datetime(2026, 5, 26, 17, tzinfo=UTC)


def test_basic_recommendation_preview_remains_free(api_client) -> None:
    response = api_client.get(
        "/monetization/access-preview",
        params={"plan_key": "free", "feature_key": "basic_recommendation_preview"},
    )

    assert response.status_code == 200
    decision = response.json()["data"]["decision"]
    assert decision["allowed"] is True
    assert decision["plan_key"] == "free"


def test_free_user_is_blocked_from_saved_watchlist_creation(api_client) -> None:
    headers = _auth_headers("auth0|free_watchlist")

    response = api_client.post(
        "/me/saved-market-artifacts",
        headers=headers,
        json={"artifact_type": "region", "artifact_ref": "greater_boston"},
    )

    assert response.status_code == 403
    body = response.json()
    decision = body["data"]["decision"]
    assert decision["allowed"] is False
    assert decision["feature_key"] == MonetizationFeatureKey.SAVED_WATCHLISTS.value
    assert decision["upgrade_plan_keys"]
    assert "recommendation" not in json.dumps(body).casefold()


def test_paid_individual_can_create_saved_watchlist(api_client, session: Session) -> None:
    headers = _auth_headers("auth0|paid_watchlist")
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.flush()
    _assign_plan(api_client, session, "auth0|paid_watchlist", PlanKey.INDIVIDUAL_MONTHLY)

    response = api_client.post(
        "/me/saved-market-artifacts",
        headers=headers,
        json={"artifact_type": "region", "artifact_ref": "greater_boston"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["artifact_ref"] == "greater_boston"


def test_free_user_is_blocked_from_alert_workflow(api_client) -> None:
    response = api_client.get("/me/alerts", headers=_auth_headers("auth0|free_alerts"))

    assert response.status_code == 403
    decision = response.json()["data"]["decision"]
    assert decision["feature_key"] == MonetizationFeatureKey.ALERTS.value
    assert decision["upgrade_plan_keys"]


def test_paid_individual_can_open_empty_alert_feed(api_client, session: Session) -> None:
    subject = "auth0|paid_alerts"
    _assign_plan(api_client, session, subject, PlanKey.INDIVIDUAL_MONTHLY)

    response = api_client.get("/me/alerts", headers=_auth_headers(subject))

    assert response.status_code == 200
    assert response.json()["data"]["alerts"] == []


def test_full_report_stub_requires_paid_entitlement_and_does_not_increment_when_blocked(
    api_client,
) -> None:
    headers = _auth_headers("auth0|free_report")

    blocked = api_client.post(
        "/monetization/reports/personalized_market_strategy_report/generate",
        headers=headers,
    )
    usage = api_client.get("/monetization/usage", headers=headers)

    assert blocked.status_code == 403
    decision = blocked.json()["data"]["decision"]
    assert decision["allowed"] is False
    assert decision["upgrade_plan_keys"]
    assert usage.status_code == 200
    assert usage.json()["data"]["usage"] == []


def test_paid_report_and_export_stubs_increment_usage_after_success(
    api_client,
    session: Session,
) -> None:
    subject = "auth0|paid_report"
    headers = _auth_headers(subject)
    _assign_plan(api_client, session, subject, PlanKey.INDIVIDUAL_MONTHLY)

    generated = api_client.post(
        "/monetization/reports/personalized_market_strategy_report/generate",
        headers=headers,
    )
    exported = api_client.post(
        "/monetization/reports/personalized_market_strategy_report/export",
        headers=headers,
    )
    usage = api_client.get("/monetization/usage", headers=headers)

    assert generated.status_code == 200
    report = generated.json()["data"]["report"]
    assert report["workflow"] == "full_report_generation"
    assert report["access_decision"]["feature_key"] == (
        MonetizationFeatureKey.FULL_REPORT_GENERATION.value
    )
    assert "PDF" in report["note"]

    assert exported.status_code == 200
    export = exported.json()["data"]["export"]
    assert export["workflow"] == "exportable_strategy_plan"
    assert export["access_decision"]["feature_key"] == (
        MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS.value
    )

    counters = {row["feature_key"]: row for row in usage.json()["data"]["usage"]}
    assert counters[MonetizationFeatureKey.FULL_REPORT_GENERATION.value]["used_count"] == 1
    assert counters[MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS.value]["used_count"] == 1


def test_authenticated_free_comparison_usage_blocks_only_after_successful_requests(
    api_client,
    session: Session,
) -> None:
    subject = "auth0|compare_usage"
    headers = _auth_headers(subject)
    _current_user_id(api_client, subject)
    _seed_regions_for_comparison(session)

    invalid = api_client.get(
        "/compare",
        headers=headers,
        params={"region_a": "greater_boston", "region_b": "greater_boston"},
    )
    assert invalid.status_code == 400

    for _ in range(3):
        allowed = api_client.get(
            "/compare",
            headers=headers,
            params={"region_a": "greater_boston", "region_b": "greater_sf"},
        )
        assert allowed.status_code == 200

    blocked = api_client.get(
        "/compare",
        headers=headers,
        params={"region_a": "greater_boston", "region_b": "greater_sf"},
    )
    usage = api_client.get("/monetization/usage", headers=headers)

    assert blocked.status_code == 403
    decision = blocked.json()["data"]["decision"]
    assert decision["feature_key"] == MonetizationFeatureKey.LIMITED_COMPARISONS.value
    assert decision["remaining_usage"] == 0
    counters = {row["feature_key"]: row for row in usage.json()["data"]["usage"]}
    assert counters[MonetizationFeatureKey.LIMITED_COMPARISONS.value]["used_count"] == 3


def test_authenticated_free_discovery_usage_increments_after_success(
    api_client,
    session: Session,
) -> None:
    subject = "auth0|discovery_usage"
    headers = _auth_headers(subject)
    _current_user_id(api_client, subject)
    _seed_regions_for_comparison(session)

    response = api_client.post(
        "/discover/personalized",
        headers=headers,
        json={
            "role_targets": [],
            "industry_preferences": [],
            "career_stage": "entry_level",
            "prestige_preference": "medium",
            "brand_preference": "medium",
            "region_ids": ["greater_boston"],
            "limit": 5,
        },
    )
    usage = api_client.get("/monetization/usage", headers=headers)

    assert response.status_code == 200
    counters = {row["feature_key"]: row for row in usage.json()["data"]["usage"]}
    assert counters[MonetizationFeatureKey.LIMITED_PERSONALIZED_DISCOVERY.value]["used_count"] == 1


def test_institutional_plan_allows_institutional_entitlement_preview(
    api_client,
    session: Session,
) -> None:
    subject = "auth0|institutional_user"
    headers = _auth_headers(subject)
    _assign_plan(api_client, session, subject, PlanKey.UNIVERSITY_LICENSE)

    response = api_client.get(
        "/monetization/access-preview",
        headers=headers,
        params={"feature_key": "institutional_license_management"},
    )

    assert response.status_code == 200
    decision = response.json()["data"]["decision"]
    assert decision["allowed"] is True
    assert decision["plan_key"] == PlanKey.UNIVERSITY_LICENSE.value


def _auth_headers(subject: str) -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"User {suffix}",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _current_user_id(api_client, subject: str) -> str:
    response = api_client.get("/me", headers=_auth_headers(subject))
    assert response.status_code == 200
    return response.json()["data"]["user"]["user_id"]


def _assign_plan(
    api_client,
    session: Session,
    subject: str,
    plan_key: PlanKey,
) -> str:
    user_id = _current_user_id(api_client, subject)
    repo = MonetizationRepository(session)
    account = repo.ensure_account_for_user(
        user_id=user_id,
        account_type=(
            MonetizationAccountType.INSTITUTIONAL
            if plan_key is PlanKey.UNIVERSITY_LICENSE
            else MonetizationAccountType.INDIVIDUAL
        ),
    )
    repo.assign_plan(
        monetization_account_id=account.monetization_account_id,
        plan_key=plan_key.value,
        plan_status=PlanStatus.ACTIVE,
        assignment_source=PlanAssignmentSource.TEST_FIXTURE,
        effective_at=NOW,
        seat_limit=2500 if plan_key is PlanKey.UNIVERSITY_LICENSE else None,
    )
    return user_id


def _seed_regions_for_comparison(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Region(
                region_id="greater_sf",
                region_name="greater_sf",
                display_name="Greater SF",
                region_type="greater_region",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            RegionMarketScore(
                region_score_id="score_boston_workflow",
                region_id="greater_boston",
                objective_opportunity_score=0.74,
                early_career_accessibility_score=0.72,
                score_ruleset_version="marketscore_v1",
            ),
            RegionMarketScore(
                region_score_id="score_sf_workflow",
                region_id="greater_sf",
                objective_opportunity_score=0.7,
                early_career_accessibility_score=0.68,
                score_ruleset_version="marketscore_v1",
            ),
        ]
    )
    session.flush()
