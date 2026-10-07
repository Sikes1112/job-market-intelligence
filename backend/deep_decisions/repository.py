"""Repository helpers for Layer 37 deep decision intelligence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.deep_decisions.models import (
    AdvisoryFinding,
    DecisionFactor,
    LongitudinalContextSnapshot,
    RecommendationEvolution,
    StrategicCareerReview,
)


class DeepDecisionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, row: object) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()

    def list_factors(
        self, user_id: str, decision_id: str, *, limit: int = 500
    ) -> list[DecisionFactor]:
        return list(
            self._session.execute(
                select(DecisionFactor)
                .where(
                    DecisionFactor.user_id == user_id,
                    DecisionFactor.decision_id == decision_id,
                )
                .order_by(DecisionFactor.generated_at.desc(), DecisionFactor.factor_id)
                .limit(limit)
            ).scalars()
        )

    def latest_longitudinal_context(
        self,
        user_id: str,
        decision_id: str | None,
    ) -> LongitudinalContextSnapshot | None:
        stmt = select(LongitudinalContextSnapshot).where(
            LongitudinalContextSnapshot.user_id == user_id
        )
        if decision_id is None:
            stmt = stmt.where(LongitudinalContextSnapshot.decision_id.is_(None))
        else:
            stmt = stmt.where(LongitudinalContextSnapshot.decision_id == decision_id)
        return self._session.execute(
            stmt.order_by(
                LongitudinalContextSnapshot.generated_at.desc(),
                LongitudinalContextSnapshot.longitudinal_context_id,
            ).limit(1)
        ).scalar_one_or_none()

    def latest_evolution(
        self,
        user_id: str,
        decision_id: str,
    ) -> RecommendationEvolution | None:
        return self._session.execute(
            select(RecommendationEvolution)
            .where(
                RecommendationEvolution.user_id == user_id,
                RecommendationEvolution.decision_id == decision_id,
            )
            .order_by(
                RecommendationEvolution.generated_at.desc(),
                RecommendationEvolution.evolution_id,
            )
            .limit(1)
        ).scalar_one_or_none()

    def list_evolutions(
        self,
        user_id: str,
        decision_id: str,
        *,
        limit: int = 100,
    ) -> list[RecommendationEvolution]:
        return list(
            self._session.execute(
                select(RecommendationEvolution)
                .where(
                    RecommendationEvolution.user_id == user_id,
                    RecommendationEvolution.decision_id == decision_id,
                )
                .order_by(
                    RecommendationEvolution.generated_at.desc(),
                    RecommendationEvolution.evolution_id,
                )
                .limit(limit)
            ).scalars()
        )

    def list_findings(
        self,
        user_id: str,
        *,
        decision_id: str | None = None,
        limit: int = 100,
    ) -> list[AdvisoryFinding]:
        stmt = select(AdvisoryFinding).where(AdvisoryFinding.user_id == user_id)
        if decision_id is not None:
            stmt = stmt.where(AdvisoryFinding.decision_id == decision_id)
        return list(
            self._session.execute(
                stmt.order_by(
                    AdvisoryFinding.generated_at.desc(), AdvisoryFinding.advisory_finding_id
                ).limit(limit)
            ).scalars()
        )

    def latest_strategic_review(
        self,
        user_id: str,
        *,
        decision_id: str | None = None,
    ) -> StrategicCareerReview | None:
        stmt = select(StrategicCareerReview).where(StrategicCareerReview.user_id == user_id)
        if decision_id is not None:
            stmt = stmt.where(StrategicCareerReview.decision_id == decision_id)
        return self._session.execute(
            stmt.order_by(
                StrategicCareerReview.generated_at.desc(),
                StrategicCareerReview.strategic_review_id,
            ).limit(1)
        ).scalar_one_or_none()

    def list_strategic_reviews(
        self,
        user_id: str,
        *,
        decision_id: str | None = None,
        limit: int = 100,
    ) -> list[StrategicCareerReview]:
        stmt = select(StrategicCareerReview).where(StrategicCareerReview.user_id == user_id)
        if decision_id is not None:
            stmt = stmt.where(StrategicCareerReview.decision_id == decision_id)
        return list(
            self._session.execute(
                stmt.order_by(
                    StrategicCareerReview.generated_at.desc(),
                    StrategicCareerReview.strategic_review_id,
                ).limit(limit)
            ).scalars()
        )
