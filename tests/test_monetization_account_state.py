from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.monetization.accounts import (
    MonetizationAccountSnapshot,
    MonetizationAccountType,
    PlanAssignmentSource,
    PlanStatus,
)
from backend.monetization.enforcement import evaluate_account_access
from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.plans import PlanKey
from backend.monetization.repository import MonetizationRepository
from backend.monetization.resolver import resolve_account_entitlements
from backend.users.models import User

NOW = datetime(2026, 5, 26, 14, tzinfo=UTC)


def test_unknown_and_public_users_default_to_free(session: Session) -> None:
    repo = MonetizationRepository(session)

    public_snapshot = resolve_account_entitlements(repo, now=NOW)
    user_snapshot = resolve_account_entitlements(repo, user_id="missing_user", now=NOW)

    assert public_snapshot.plan_key is PlanKey.FREE
    assert public_snapshot.account_type is MonetizationAccountType.PUBLIC_DEMO
    assert user_snapshot.plan_key is PlanKey.FREE
    assert user_snapshot.account_type is MonetizationAccountType.INDIVIDUAL
    assert MonetizationFeatureKey.BASIC_RECOMMENDATION_PREVIEW in (
        user_snapshot.included_feature_keys
    )


def test_explicit_account_plan_assignment_overrides_default(
    session: Session,
) -> None:
    repo = MonetizationRepository(session)
    _seed_user(session, "user_paid")
    account = repo.create_account(
        user_id="user_paid",
        account_type=MonetizationAccountType.INDIVIDUAL,
    )
    repo.assign_plan(
        monetization_account_id=account.monetization_account_id,
        plan_key=PlanKey.INDIVIDUAL_MONTHLY.value,
        plan_status=PlanStatus.ACTIVE,
        assignment_source=PlanAssignmentSource.MANUAL,
        effective_at=NOW - timedelta(days=1),
    )

    snapshot = resolve_account_entitlements(repo, user_id="user_paid", now=NOW)
    decision = evaluate_account_access(
        repo,
        user_id="user_paid",
        feature_key=MonetizationFeatureKey.FULL_REPORT_GENERATION,
        now=NOW,
    )

    assert snapshot.plan_key is PlanKey.INDIVIDUAL_MONTHLY
    assert decision.allowed is True
    assert decision.account_status == PlanStatus.ACTIVE.value


@pytest.mark.parametrize(
    ("status", "expires_delta"),
    (
        (PlanStatus.CANCELED, timedelta(days=10)),
        (PlanStatus.PAUSED, timedelta(days=10)),
        (PlanStatus.EXPIRED, timedelta(days=10)),
        (PlanStatus.ACTIVE, timedelta(days=-1)),
    ),
)
def test_non_entitling_or_expired_assignments_fall_back_to_free(
    session: Session,
    status: PlanStatus,
    expires_delta: timedelta,
) -> None:
    repo = MonetizationRepository(session)
    user_id = f"user_{status.value}_{expires_delta.days}"
    _seed_user(session, user_id)
    account = repo.create_account(
        user_id=user_id,
        account_type=MonetizationAccountType.INDIVIDUAL,
    )
    repo.assign_plan(
        monetization_account_id=account.monetization_account_id,
        plan_key=PlanKey.INDIVIDUAL_ANNUAL.value,
        plan_status=status,
        assignment_source=PlanAssignmentSource.MANUAL,
        effective_at=NOW - timedelta(days=5),
        expires_at=NOW + expires_delta,
    )

    snapshot = resolve_account_entitlements(repo, user_id=user_id, now=NOW)
    decision = evaluate_account_access(
        repo,
        user_id=user_id,
        feature_key=MonetizationFeatureKey.FULL_REPORT_GENERATION,
        now=NOW,
    )

    assert snapshot.plan_key is PlanKey.FREE
    assert decision.allowed is False
    assert decision.upgrade_plan_keys
    assert decision.account_status in {
        PlanStatus.CANCELED.value,
        PlanStatus.PAUSED.value,
        PlanStatus.EXPIRED.value,
    }


def test_free_users_keep_basic_access(session: Session) -> None:
    repo = MonetizationRepository(session)

    preview = evaluate_account_access(
        repo,
        user_id="unknown_free_user",
        feature_key=MonetizationFeatureKey.BASIC_RECOMMENDATION_PREVIEW,
        now=NOW,
    )
    paid_report = evaluate_account_access(
        repo,
        user_id="unknown_free_user",
        feature_key=MonetizationFeatureKey.FULL_REPORT_GENERATION,
        now=NOW,
    )

    assert preview.allowed is True
    assert paid_report.allowed is False


def test_institutional_account_snapshot_carries_license_context(
    session: Session,
) -> None:
    repo = MonetizationRepository(session)
    account = repo.create_account(
        user_id=None,
        account_type=MonetizationAccountType.INSTITUTIONAL,
        assigned_seats_count=42,
        safe_metadata={"organization": "Example University"},
    )
    repo.assign_plan(
        monetization_account_id=account.monetization_account_id,
        plan_key=PlanKey.UNIVERSITY_LICENSE.value,
        plan_status=PlanStatus.MANUAL,
        assignment_source=PlanAssignmentSource.ADMIN_SEED,
        effective_at=NOW,
        seat_limit=2500,
    )

    snapshot = resolve_account_entitlements(
        repo,
        monetization_account_id=account.monetization_account_id,
        now=NOW,
    )
    decision = evaluate_account_access(
        repo,
        monetization_account_id=account.monetization_account_id,
        feature_key=MonetizationFeatureKey.INSTITUTIONAL_LICENSE_MANAGEMENT,
        now=NOW,
    )

    assert snapshot.plan_key is PlanKey.UNIVERSITY_LICENSE
    assert snapshot.account_type is MonetizationAccountType.INSTITUTIONAL
    assert snapshot.seat_limit == 2500
    assert snapshot.assigned_seats_count == 42
    assert decision.allowed is True


def test_safe_monetization_metadata_rejects_private_or_provider_keys() -> None:
    with pytest.raises(ValidationError):
        MonetizationAccountSnapshot(
            account_type=MonetizationAccountType.INDIVIDUAL,
            safe_metadata={"stripe_customer_id": "cus_test"},
        )

    with pytest.raises(ValidationError):
        MonetizationAccountSnapshot(
            account_type=MonetizationAccountType.INDIVIDUAL,
            safe_metadata={"recommendation_internals_ref": "private"},
        )


def _seed_user(session: Session, user_id: str) -> None:
    session.add(User(user_id=user_id, status="active"))
    session.flush()
