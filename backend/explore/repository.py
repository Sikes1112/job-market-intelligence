"""Data access for saved Explore comparisons and Decision provenance."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.career_decisions.models import CareerDecision
from backend.explore.models import ExploreComparisonSnapshot, ExploreDecisionProvenance
from backend.users.models import User


class ExploreComparisonRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, row: object) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()

    def serialize_user_writes(self, user_id: str) -> None:
        """Serialize same-user save/prioritize decisions on PostgreSQL."""

        self._session.execute(
            select(User.user_id).where(User.user_id == user_id).with_for_update()
        ).scalar_one()

    def get(self, comparison_id: str) -> ExploreComparisonSnapshot | None:
        return self._session.get(ExploreComparisonSnapshot, comparison_id)

    def get_by_identity(
        self, user_id: str, comparison_identity: str
    ) -> ExploreComparisonSnapshot | None:
        return self._session.execute(
            select(ExploreComparisonSnapshot).where(
                ExploreComparisonSnapshot.user_id == user_id,
                ExploreComparisonSnapshot.comparison_identity == comparison_identity,
            )
        ).scalar_one_or_none()

    def list_saved(self, user_id: str, *, limit: int = 100) -> list[ExploreComparisonSnapshot]:
        return list(
            self._session.execute(
                select(ExploreComparisonSnapshot)
                .where(
                    ExploreComparisonSnapshot.user_id == user_id,
                    ExploreComparisonSnapshot.saved_at.is_not(None),
                )
                .order_by(
                    ExploreComparisonSnapshot.saved_at.desc(),
                    ExploreComparisonSnapshot.comparison_id,
                )
                .limit(limit)
            ).scalars()
        )

    def find_active_equivalent_decision(
        self,
        *,
        user_id: str,
        context_fingerprint: str,
        market_set_fingerprint: str,
        selected_region_id: str,
    ) -> tuple[ExploreDecisionProvenance, CareerDecision] | None:
        return self._session.execute(
            select(ExploreDecisionProvenance, CareerDecision)
            .join(
                CareerDecision, CareerDecision.decision_id == ExploreDecisionProvenance.decision_id
            )
            .where(
                ExploreDecisionProvenance.user_id == user_id,
                ExploreDecisionProvenance.context_fingerprint == context_fingerprint,
                ExploreDecisionProvenance.market_set_fingerprint == market_set_fingerprint,
                ExploreDecisionProvenance.user_selected_region_id == selected_region_id,
                CareerDecision.status.in_(("draft", "evaluating", "decided", "reconsidering")),
            )
            .order_by(CareerDecision.updated_at.desc(), CareerDecision.decision_id)
            .limit(1)
        ).one_or_none()

    def get_decision_provenance(self, decision_id: str) -> ExploreDecisionProvenance | None:
        return self._session.execute(
            select(ExploreDecisionProvenance).where(
                ExploreDecisionProvenance.decision_id == decision_id
            )
        ).scalar_one_or_none()
