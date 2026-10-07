"""Repository helpers for Layer 36A career decision lifecycle records."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.career_decisions.models import (
    CareerAction,
    CareerActionPlan,
    CareerApplication,
    CareerApplicationTransition,
    CareerDecision,
    CareerOutcome,
    DecisionContextSnapshot,
    DecisionOption,
    DecisionRecommendation,
    DecisionVersion,
)


class CareerDecisionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, row: object) -> None:
        self._session.add(row)

    def get_decision(self, decision_id: str) -> CareerDecision | None:
        return self._session.get(CareerDecision, decision_id)

    def list_decisions(self, user_id: str, *, limit: int = 100) -> list[CareerDecision]:
        return list(
            self._session.execute(
                select(CareerDecision)
                .where(CareerDecision.user_id == user_id)
                .order_by(CareerDecision.updated_at.desc(), CareerDecision.decision_id)
                .limit(limit)
            ).scalars()
        )

    def get_context(self, context_snapshot_id: str) -> DecisionContextSnapshot | None:
        return self._session.get(DecisionContextSnapshot, context_snapshot_id)

    def list_options(self, decision_id: str) -> list[DecisionOption]:
        return list(
            self._session.execute(
                select(DecisionOption)
                .where(DecisionOption.decision_id == decision_id)
                .order_by(
                    DecisionOption.position, DecisionOption.created_at, DecisionOption.option_id
                )
            ).scalars()
        )

    def get_option(self, option_id: str) -> DecisionOption | None:
        return self._session.get(DecisionOption, option_id)

    def get_recommendation(self, recommendation_id: str) -> DecisionRecommendation | None:
        return self._session.get(DecisionRecommendation, recommendation_id)

    def list_recommendations(self, decision_id: str) -> list[DecisionRecommendation]:
        return list(
            self._session.execute(
                select(DecisionRecommendation)
                .where(DecisionRecommendation.decision_id == decision_id)
                .order_by(
                    DecisionRecommendation.generated_at.desc(),
                    DecisionRecommendation.recommendation_id,
                )
            ).scalars()
        )

    def list_versions(self, decision_id: str) -> list[DecisionVersion]:
        return list(
            self._session.execute(
                select(DecisionVersion)
                .where(DecisionVersion.decision_id == decision_id)
                .order_by(DecisionVersion.version_number, DecisionVersion.created_at)
            ).scalars()
        )

    def latest_version_number(self, decision_id: str) -> int:
        versions = self.list_versions(decision_id)
        return versions[-1].version_number if versions else 0

    def get_action_plan_for_decision(self, decision_id: str) -> CareerActionPlan | None:
        return self._session.execute(
            select(CareerActionPlan)
            .where(CareerActionPlan.decision_id == decision_id)
            .order_by(CareerActionPlan.created_at.desc(), CareerActionPlan.action_plan_id)
        ).scalar_one_or_none()

    def get_action_plan(self, action_plan_id: str) -> CareerActionPlan | None:
        return self._session.get(CareerActionPlan, action_plan_id)

    def list_actions_for_plan(self, action_plan_id: str) -> list[CareerAction]:
        return list(
            self._session.execute(
                select(CareerAction)
                .where(CareerAction.action_plan_id == action_plan_id)
                .order_by(CareerAction.position, CareerAction.created_at, CareerAction.action_id)
            ).scalars()
        )

    def list_actions(
        self,
        user_id: str,
        *,
        decision_id: str | None = None,
        limit: int = 100,
    ) -> list[CareerAction]:
        stmt = select(CareerAction).where(CareerAction.user_id == user_id)
        if decision_id is not None:
            stmt = stmt.where(CareerAction.decision_id == decision_id)
        return list(
            self._session.execute(
                stmt.order_by(
                    CareerAction.due_at.is_(None),
                    CareerAction.due_at,
                    CareerAction.created_at,
                ).limit(limit)
            ).scalars()
        )

    def get_action(self, action_id: str) -> CareerAction | None:
        return self._session.get(CareerAction, action_id)

    def get_application(self, application_id: str) -> CareerApplication | None:
        return self._session.get(CareerApplication, application_id)

    def list_applications(
        self,
        user_id: str,
        *,
        decision_id: str | None = None,
        limit: int = 100,
    ) -> list[CareerApplication]:
        stmt = select(CareerApplication).where(CareerApplication.user_id == user_id)
        if decision_id is not None:
            stmt = stmt.where(CareerApplication.decision_id == decision_id)
        return list(
            self._session.execute(
                stmt.order_by(
                    CareerApplication.updated_at.desc(), CareerApplication.application_id
                ).limit(limit)
            ).scalars()
        )

    def list_transitions(self, application_id: str) -> list[CareerApplicationTransition]:
        return list(
            self._session.execute(
                select(CareerApplicationTransition)
                .where(CareerApplicationTransition.application_id == application_id)
                .order_by(
                    CareerApplicationTransition.transitioned_at,
                    CareerApplicationTransition.transition_id,
                )
            ).scalars()
        )

    def get_outcome(self, outcome_id: str) -> CareerOutcome | None:
        return self._session.get(CareerOutcome, outcome_id)

    def list_outcomes(
        self,
        user_id: str,
        *,
        decision_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[CareerOutcome]:
        stmt = select(CareerOutcome).where(CareerOutcome.user_id == user_id)
        if decision_id is not None:
            stmt = stmt.where(CareerOutcome.decision_id == decision_id)
        if since is not None:
            stmt = stmt.where(CareerOutcome.occurred_at >= since)
        if until is not None:
            stmt = stmt.where(CareerOutcome.occurred_at <= until)
        return list(
            self._session.execute(
                stmt.order_by(CareerOutcome.occurred_at.desc(), CareerOutcome.outcome_id).limit(
                    limit
                )
            ).scalars()
        )

    def flush(self) -> None:
        self._session.flush()
