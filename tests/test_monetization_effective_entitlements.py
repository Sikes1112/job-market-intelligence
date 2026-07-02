from __future__ import annotations

import ast
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from backend.api import monetization as monetization_api
from backend.monetization.accounts import (
    MonetizationAccountType,
    PlanAssignmentSource,
    PlanStatus,
)
from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.plans import PlanKey, plan_definition, usage_limit_for_feature
from backend.monetization.repository import MonetizationRepository
from backend.monetization.resolver import resolve_account_entitlements
from backend.monetization.usage import usage_period_for_limit

REPO_ROOT = Path(__file__).resolve().parent.parent
MONETIZATION_ROOT = REPO_ROOT / "backend" / "monetization"
NOW = datetime(2026, 5, 26, 16, tzinfo=UTC)


def test_entitlement_resolver_is_deterministic(session: Session) -> None:
    repo = MonetizationRepository(session)

    first = resolve_account_entitlements(repo, user_id="unknown", now=NOW)
    second = resolve_account_entitlements(repo, user_id="unknown", now=NOW)

    assert first == second
    assert first.plan_key is PlanKey.FREE


def test_account_aware_access_preview_uses_effective_user_plan(
    api_client,
    session: Session,
) -> None:
    headers = _auth_headers("auth0|paid_user")
    user_id = _current_user_id(api_client, headers)
    repo = MonetizationRepository(session)
    account = repo.create_account(
        user_id=user_id,
        account_type=MonetizationAccountType.INDIVIDUAL,
    )
    repo.assign_plan(
        monetization_account_id=account.monetization_account_id,
        plan_key=PlanKey.INDIVIDUAL_MONTHLY.value,
        plan_status=PlanStatus.ACTIVE,
        assignment_source=PlanAssignmentSource.TEST_FIXTURE,
        effective_at=NOW - timedelta(days=1),
    )

    response = api_client.get(
        "/monetization/access-preview",
        headers=headers,
        params={"feature_key": MonetizationFeatureKey.FULL_REPORT_GENERATION.value},
    )

    assert response.status_code == 200
    decision = response.json()["data"]["decision"]
    assert decision["allowed"] is True
    assert decision["plan_key"] == PlanKey.INDIVIDUAL_MONTHLY.value
    assert decision["account_status"] == PlanStatus.ACTIVE.value


def test_monetization_me_and_entitlements_default_to_free(api_client) -> None:
    headers = _auth_headers("auth0|free_user")

    me = api_client.get("/monetization/me", headers=headers)
    entitlements = api_client.get("/monetization/entitlements", headers=headers)

    assert me.status_code == 200
    assert entitlements.status_code == 200
    me_data = me.json()["data"]
    entitlement_data = entitlements.json()["data"]["entitlements"]
    assert me_data["account"]["account_type"] == MonetizationAccountType.INDIVIDUAL.value
    assert me_data["entitlements"]["plan_key"] == PlanKey.FREE.value
    assert entitlement_data["plan_key"] == PlanKey.FREE.value
    assert MonetizationFeatureKey.BASIC_RECOMMENDATION_PREVIEW.value in (
        entitlement_data["included_feature_keys"]
    )


def test_monetization_usage_endpoint_exposes_only_usage_state(
    api_client,
    monkeypatch,
    session: Session,
) -> None:
    monkeypatch.setattr(monetization_api, "_now", lambda: NOW)
    headers = _auth_headers("auth0|usage_user")
    user_id = _current_user_id(api_client, headers)
    repo = MonetizationRepository(session)
    account = repo.create_account(
        user_id=user_id,
        account_type=MonetizationAccountType.INDIVIDUAL,
    )
    repo.assign_plan(
        monetization_account_id=account.monetization_account_id,
        plan_key=PlanKey.FREE.value,
        plan_status=PlanStatus.ACTIVE,
        assignment_source=PlanAssignmentSource.TEST_FIXTURE,
        effective_at=NOW - timedelta(days=1),
    )
    limit = usage_limit_for_feature(
        plan_definition(PlanKey.FREE),
        MonetizationFeatureKey.LIMITED_COMPARISONS,
    )
    assert limit is not None
    period = usage_period_for_limit(limit, now=NOW)
    counter = repo.ensure_usage_counter(
        monetization_account_id=account.monetization_account_id,
        feature_key=MonetizationFeatureKey.LIMITED_COMPARISONS,
        period=period,
        limit_count=limit.limit,
    )
    counter.used_count = 1

    usage = api_client.get("/monetization/usage", headers=headers)

    assert usage.status_code == 200
    data = usage.json()["data"]
    assert data["plan_key"] == PlanKey.FREE.value
    assert data["usage"][0]["feature_key"] == (
        MonetizationFeatureKey.LIMITED_COMPARISONS.value
    )
    assert "recommendation_inputs" not in json.dumps(data)
    assert "stripe" not in json.dumps(data).casefold()


def test_monetization_modules_do_not_introduce_payment_provider_imports() -> None:
    violations: dict[str, list[str]] = {}
    forbidden = ("stripe", "payment_provider", "billing_provider")

    for path in sorted(MONETIZATION_ROOT.glob("*.py")):
        imports = _imports(path)
        bad = [name for name in imports if any(part in name for part in forbidden)]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad

    assert not violations


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


def _current_user_id(api_client, headers: dict[str, str]) -> str:
    response = api_client.get("/me", headers=headers)
    assert response.status_code == 200
    return response.json()["data"]["user"]["user_id"]


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.append(module)
            names.extend(f"{module}.{alias.name}" for alias in node.names)
    return names
