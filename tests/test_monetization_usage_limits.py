from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.monetization.accounts import (
    MonetizationAccountType,
    PlanAssignmentSource,
    PlanStatus,
)
from backend.monetization.enforcement import (
    evaluate_account_access,
    increment_feature_usage,
)
from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.plans import PlanKey, plan_definition, usage_limit_for_feature
from backend.monetization.repository import MonetizationRepository
from backend.monetization.usage import usage_period_for_limit
from backend.users.models import User

NOW = datetime(2026, 5, 26, 15, tzinfo=UTC)


def test_usage_limit_allows_access_when_remaining_usage_exists(
    session: Session,
) -> None:
    repo, account_id = _seed_account(
        session,
        user_id="user_free_remaining",
        plan_key=PlanKey.FREE,
    )
    _set_used_count(
        repo,
        account_id=account_id,
        feature_key=MonetizationFeatureKey.LIMITED_COMPARISONS,
        used_count=2,
    )

    decision = evaluate_account_access(
        repo,
        user_id="user_free_remaining",
        feature_key=MonetizationFeatureKey.LIMITED_COMPARISONS,
        now=NOW,
    )

    assert decision.allowed is True
    assert decision.usage_limit is not None
    assert decision.usage_limit.limit == 3
    assert decision.remaining_usage == 1


def test_usage_limit_blocks_access_when_exhausted(session: Session) -> None:
    repo, account_id = _seed_account(
        session,
        user_id="user_free_exhausted",
        plan_key=PlanKey.FREE,
    )
    _set_used_count(
        repo,
        account_id=account_id,
        feature_key=MonetizationFeatureKey.LIMITED_COMPARISONS,
        used_count=3,
    )

    decision = evaluate_account_access(
        repo,
        user_id="user_free_exhausted",
        feature_key=MonetizationFeatureKey.LIMITED_COMPARISONS,
        now=NOW,
    )

    assert decision.allowed is False
    assert decision.remaining_usage == 0
    assert PlanKey.INDIVIDUAL_MONTHLY in decision.upgrade_plan_keys


def test_paid_individual_report_generation_uses_account_counter(
    session: Session,
) -> None:
    repo, account_id = _seed_account(
        session,
        user_id="user_paid_reports",
        plan_key=PlanKey.INDIVIDUAL_MONTHLY,
    )
    _set_used_count(
        repo,
        account_id=account_id,
        feature_key=MonetizationFeatureKey.FULL_REPORT_GENERATION,
        used_count=1,
    )

    decision = evaluate_account_access(
        repo,
        user_id="user_paid_reports",
        feature_key=MonetizationFeatureKey.FULL_REPORT_GENERATION,
        now=NOW,
    )

    assert decision.allowed is True
    assert decision.usage_limit is not None
    assert decision.usage_limit.limit == 3
    assert decision.remaining_usage == 2


def test_increment_feature_usage_flows_through_central_enforcement(
    session: Session,
) -> None:
    repo, _account_id = _seed_account(
        session,
        user_id="user_increment_usage",
        plan_key=PlanKey.FREE,
    )

    first = increment_feature_usage(
        repo,
        user_id="user_increment_usage",
        feature_key=MonetizationFeatureKey.LIMITED_PERSONALIZED_DISCOVERY,
        now=NOW,
    )
    second = evaluate_account_access(
        repo,
        user_id="user_increment_usage",
        feature_key=MonetizationFeatureKey.LIMITED_PERSONALIZED_DISCOVERY,
        now=NOW,
    )

    assert first.allowed is True
    assert first.remaining_usage == 4
    assert second.allowed is True
    assert second.remaining_usage == 4


def _seed_account(
    session: Session,
    *,
    user_id: str,
    plan_key: PlanKey,
) -> tuple[MonetizationRepository, str]:
    session.add(User(user_id=user_id, status="active"))
    session.flush()
    repo = MonetizationRepository(session)
    account = repo.create_account(
        user_id=user_id,
        account_type=MonetizationAccountType.INDIVIDUAL,
    )
    repo.assign_plan(
        monetization_account_id=account.monetization_account_id,
        plan_key=plan_key.value,
        plan_status=PlanStatus.ACTIVE,
        assignment_source=PlanAssignmentSource.TEST_FIXTURE,
        effective_at=NOW - timedelta(days=1),
    )
    return repo, account.monetization_account_id


def _set_used_count(
    repo: MonetizationRepository,
    *,
    account_id: str,
    feature_key: MonetizationFeatureKey,
    used_count: int,
) -> None:
    limit = usage_limit_for_feature(plan_definition(PlanKey.FREE), feature_key)
    if limit is None:
        limit = usage_limit_for_feature(
            plan_definition(PlanKey.INDIVIDUAL_MONTHLY),
            feature_key,
        )
    assert limit is not None
    period = usage_period_for_limit(limit, now=NOW)
    counter = repo.ensure_usage_counter(
        monetization_account_id=account_id,
        feature_key=feature_key,
        period=period,
        limit_count=limit.limit,
    )
    counter.used_count = used_count
