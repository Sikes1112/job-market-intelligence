"""Resource insertion quotas for serialized SQLite guest transactions."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import event, func, inspect, select
from sqlalchemy.orm import Session

from backend.api.errors import SafeHTTPException
from backend.career_decisions.models import (
    CareerAction,
    CareerApplication,
    CareerDecision,
    DecisionOption,
)
from backend.career_identity.models import CareerIdentityFact
from backend.explore.models import ExploreComparisonSnapshot
from backend.users.models import PersonalizedRecommendationSnapshot


def install_decision_quota(
    session: Session,
    maximum: int,
    *,
    option_maximum: int,
    action_maximum: int,
    fact_maximum: int | None = None,
    application_maximum: int | None = None,
    snapshot_maximum: int | None = None,
    saved_comparison_maximum: int | None = None,
) -> None:
    """Cover all insert paths, after reuse decisions and before persistence.

    Guest mutations start BEGIN IMMEDIATE before route execution, so SQLite
    serializes this count and insertion until request commit/rollback, including
    across independent app locks. Middleware also serializes each guest session.
    """

    def enforce(session: Session, _flush_context: object, _instances: object) -> None:
        for model, limit, label in (
            (CareerDecision, maximum, "decisions"),
            (DecisionOption, option_maximum, "decision_options"),
            (CareerAction, action_maximum, "actions"),
            (CareerIdentityFact, fact_maximum, "career_identity_facts"),
            (CareerApplication, application_maximum, "applications"),
            (PersonalizedRecommendationSnapshot, snapshot_maximum, "recommendation_snapshots"),
        ):
            if limit is None:
                continue
            owner = model.user_id
            pending = Counter(
                getattr(row, owner.key) for row in session.new if isinstance(row, model)
            )
            for user_id, additions in pending.items():
                stored = session.scalar(
                    select(func.count()).select_from(model).where(owner == user_id)
                )
                if int(stored or 0) + additions > limit:
                    raise SafeHTTPException(
                        429,
                        error_type="guest_quota_exceeded",
                        message=f"Guest demo {label} limit reached",
                    )

        if saved_comparison_maximum is not None:
            # Explicit saves consume capacity, including promotion of an internal
            # evidence snapshot. Re-saving an already saved row is pure reuse.
            additions = Counter(
                row.user_id
                for row in session.new
                if isinstance(row, ExploreComparisonSnapshot) and row.saved_at is not None
            )
            for row in session.dirty:
                if not isinstance(row, ExploreComparisonSnapshot) or row.saved_at is None:
                    continue
                history = inspect(row).attrs.saved_at.history
                if history.has_changes() and history.deleted == [None]:
                    additions[row.user_id] += 1
            for user_id, count in additions.items():
                stored = session.scalar(
                    select(func.count())
                    .select_from(ExploreComparisonSnapshot)
                    .where(
                        ExploreComparisonSnapshot.user_id == user_id,
                        ExploreComparisonSnapshot.saved_at.is_not(None),
                    )
                )
                if int(stored or 0) + count > saved_comparison_maximum:
                    raise SafeHTTPException(
                        429,
                        error_type="guest_quota_exceeded",
                        message="Guest demo saved_comparisons limit reached",
                    )

    event.listen(session, "before_flush", enforce)
