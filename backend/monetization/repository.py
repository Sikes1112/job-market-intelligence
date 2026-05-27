"""Repository helpers for monetization account and usage state."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.monetization.accounts import (
    MonetizationAccountSnapshot,
    MonetizationAccountType,
    PlanAssignmentSnapshot,
    PlanAssignmentSource,
    PlanStatus,
)
from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.models import (
    MonetizationAccount,
    MonetizationPlanAssignment,
    MonetizationUsageCounter,
)
from backend.monetization.usage import UsagePeriod


class MonetizationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_account(self, monetization_account_id: str) -> MonetizationAccount | None:
        return self._session.get(MonetizationAccount, monetization_account_id)

    def get_account_for_user(self, user_id: str) -> MonetizationAccount | None:
        return self._session.execute(
            select(MonetizationAccount).where(MonetizationAccount.user_id == user_id)
        ).scalar_one_or_none()

    def create_account(
        self,
        *,
        user_id: str | None,
        account_type: MonetizationAccountType,
        assigned_seats_count: int | None = None,
        safe_metadata: dict | None = None,
    ) -> MonetizationAccount:
        snapshot = MonetizationAccountSnapshot(
            user_id=user_id,
            account_type=account_type,
            assigned_seats_count=assigned_seats_count,
            safe_metadata=dict(safe_metadata or {}),
        )
        row = MonetizationAccount(
            monetization_account_id=_new_id("monacct"),
            user_id=snapshot.user_id,
            account_type=snapshot.account_type.value,
            assigned_seats_count=snapshot.assigned_seats_count,
            safe_metadata=snapshot.safe_metadata,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def ensure_account_for_user(
        self,
        *,
        user_id: str,
        account_type: MonetizationAccountType = MonetizationAccountType.INDIVIDUAL,
    ) -> MonetizationAccount:
        row = self.get_account_for_user(user_id)
        if row is not None:
            return row
        return self.create_account(user_id=user_id, account_type=account_type)

    def assign_plan(
        self,
        *,
        monetization_account_id: str,
        plan_key: str,
        plan_status: PlanStatus,
        assignment_source: PlanAssignmentSource,
        effective_at: datetime,
        expires_at: datetime | None = None,
        seat_limit: int | None = None,
        safe_metadata: dict | None = None,
    ) -> MonetizationPlanAssignment:
        snapshot = PlanAssignmentSnapshot(
            monetization_account_id=monetization_account_id,
            plan_key=plan_key,
            plan_status=plan_status,
            assignment_source=assignment_source,
            effective_at=effective_at,
            expires_at=expires_at,
            seat_limit=seat_limit,
            safe_metadata=dict(safe_metadata or {}),
        )
        row = MonetizationPlanAssignment(
            plan_assignment_id=_new_id("planasg"),
            monetization_account_id=snapshot.monetization_account_id,
            plan_key=snapshot.plan_key.value,
            plan_status=snapshot.plan_status.value,
            assignment_source=snapshot.assignment_source.value,
            effective_at=snapshot.effective_at,
            expires_at=snapshot.expires_at,
            seat_limit=snapshot.seat_limit,
            safe_metadata=snapshot.safe_metadata,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def list_plan_assignments(
        self,
        monetization_account_id: str,
    ) -> list[MonetizationPlanAssignment]:
        rows = self._session.execute(
            select(MonetizationPlanAssignment)
            .where(
                MonetizationPlanAssignment.monetization_account_id
                == monetization_account_id
            )
            .order_by(
                MonetizationPlanAssignment.effective_at.desc(),
                MonetizationPlanAssignment.created_at.desc(),
                MonetizationPlanAssignment.plan_assignment_id.desc(),
            )
        ).scalars()
        return list(rows)

    def get_usage_counter(
        self,
        *,
        monetization_account_id: str,
        feature_key: MonetizationFeatureKey | str,
        period: UsagePeriod,
    ) -> MonetizationUsageCounter | None:
        return self._session.execute(
            select(MonetizationUsageCounter).where(
                MonetizationUsageCounter.monetization_account_id
                == monetization_account_id,
                MonetizationUsageCounter.feature_key
                == MonetizationFeatureKey(feature_key).value,
                MonetizationUsageCounter.period_start == period.period_start,
                MonetizationUsageCounter.period_end == period.period_end,
            )
        ).scalar_one_or_none()

    def ensure_usage_counter(
        self,
        *,
        monetization_account_id: str,
        feature_key: MonetizationFeatureKey | str,
        period: UsagePeriod,
        limit_count: int,
    ) -> MonetizationUsageCounter:
        row = self.get_usage_counter(
            monetization_account_id=monetization_account_id,
            feature_key=feature_key,
            period=period,
        )
        if row is not None:
            if row.limit_count != limit_count:
                row.limit_count = limit_count
            return row

        row = MonetizationUsageCounter(
            usage_counter_id=_new_id("usage"),
            monetization_account_id=monetization_account_id,
            feature_key=MonetizationFeatureKey(feature_key).value,
            period_start=period.period_start,
            period_end=period.period_end,
            used_count=0,
            limit_count=limit_count,
            reset_policy=period.reset_policy.value,
            last_incremented_at=None,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def list_usage_counters(
        self,
        *,
        monetization_account_id: str,
        now: datetime | None = None,
    ) -> list[MonetizationUsageCounter]:
        stmt = select(MonetizationUsageCounter).where(
            MonetizationUsageCounter.monetization_account_id
            == monetization_account_id
        )
        if now is not None:
            stmt = stmt.where(
                MonetizationUsageCounter.period_start <= now,
                MonetizationUsageCounter.period_end > now,
            )
        rows = self._session.execute(
            stmt.order_by(
                MonetizationUsageCounter.feature_key,
                MonetizationUsageCounter.period_start.desc(),
            )
        ).scalars()
        return list(rows)

    def increment_usage(
        self,
        counter: MonetizationUsageCounter,
        *,
        amount: int,
        now: datetime,
    ) -> MonetizationUsageCounter:
        if amount < 1:
            raise ValueError("usage increment amount must be positive")
        counter.used_count += amount
        counter.last_incremented_at = now
        self._session.flush()
        return counter


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"
