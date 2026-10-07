"""Repository helpers for Layer 40A product measurement records."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.product_measurement.models import (
    BetaCohort,
    BetaCohortMembership,
    CommercialExperimentSignal,
    DecisionReflection,
    ExperimentAssignment,
    ProductAnalyticsEvent,
    ProductUserVisit,
    ProductEntitlementGrant,
    ProductFeatureGate,
    RecommendationFeedback,
    StrategyChange,
    SupportCase,
    SupportCaseEvent,
)


class ProductMeasurementRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, row: object) -> None:
        self._session.add(row)

    def get_event(self, event_id: str) -> ProductAnalyticsEvent | None:
        return self._session.get(ProductAnalyticsEvent, event_id)

    def list_events(
        self,
        *,
        user_id: str | None = None,
        cohort_key: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 500,
    ) -> list[ProductAnalyticsEvent]:
        stmt = select(ProductAnalyticsEvent)
        if user_id is not None:
            stmt = stmt.where(ProductAnalyticsEvent.user_id == user_id)
        if cohort_key is not None:
            stmt = stmt.where(ProductAnalyticsEvent.cohort_key == cohort_key)
        if event_type is not None:
            stmt = stmt.where(ProductAnalyticsEvent.event_type == event_type)
        if since is not None:
            stmt = stmt.where(ProductAnalyticsEvent.occurred_at >= since)
        if until is not None:
            stmt = stmt.where(ProductAnalyticsEvent.occurred_at <= until)
        return list(
            self._session.execute(
                stmt.order_by(
                    ProductAnalyticsEvent.occurred_at.desc(),
                    ProductAnalyticsEvent.event_id.desc(),
                ).limit(limit)
            ).scalars()
        )

    def get_latest_visit(self, user_id: str) -> ProductUserVisit | None:
        return self._session.execute(
            select(ProductUserVisit)
            .where(ProductUserVisit.user_id == user_id)
            .order_by(
                ProductUserVisit.visit_started_at.desc(),
                ProductUserVisit.visit_id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

    def get_recommendation_feedback(self, feedback_id: str) -> RecommendationFeedback | None:
        return self._session.get(RecommendationFeedback, feedback_id)

    def list_recommendation_feedback(
        self,
        *,
        user_id: str | None = None,
        recommendation_id: str | None = None,
        limit: int = 500,
    ) -> list[RecommendationFeedback]:
        stmt = select(RecommendationFeedback)
        if user_id is not None:
            stmt = stmt.where(RecommendationFeedback.user_id == user_id)
        if recommendation_id is not None:
            stmt = stmt.where(RecommendationFeedback.recommendation_id == recommendation_id)
        return list(
            self._session.execute(
                stmt.order_by(
                    RecommendationFeedback.created_at.desc(),
                    RecommendationFeedback.feedback_id.desc(),
                ).limit(limit)
            ).scalars()
        )

    def get_cohort_by_key(self, cohort_key: str) -> BetaCohort | None:
        return self._session.execute(
            select(BetaCohort).where(BetaCohort.cohort_key == cohort_key)
        ).scalar_one_or_none()

    def list_cohorts(self, *, limit: int = 500) -> list[BetaCohort]:
        return list(
            self._session.execute(
                select(BetaCohort)
                .order_by(BetaCohort.created_at.desc(), BetaCohort.cohort_key)
                .limit(limit)
            ).scalars()
        )

    def get_membership(
        self,
        *,
        user_id: str,
        cohort_id: str,
    ) -> BetaCohortMembership | None:
        return self._session.execute(
            select(BetaCohortMembership).where(
                BetaCohortMembership.user_id == user_id,
                BetaCohortMembership.cohort_id == cohort_id,
            )
        ).scalar_one_or_none()

    def list_memberships(
        self,
        *,
        user_id: str | None = None,
        cohort_id: str | None = None,
        active_only: bool = False,
        limit: int = 500,
    ) -> list[BetaCohortMembership]:
        stmt = select(BetaCohortMembership)
        if user_id is not None:
            stmt = stmt.where(BetaCohortMembership.user_id == user_id)
        if cohort_id is not None:
            stmt = stmt.where(BetaCohortMembership.cohort_id == cohort_id)
        if active_only:
            stmt = stmt.where(BetaCohortMembership.status == "active")
        return list(
            self._session.execute(
                stmt.order_by(
                    BetaCohortMembership.created_at.desc(),
                    BetaCohortMembership.membership_id.desc(),
                ).limit(limit)
            ).scalars()
        )

    def get_feature_gate(self, feature_key: str) -> ProductFeatureGate | None:
        return self._session.execute(
            select(ProductFeatureGate).where(ProductFeatureGate.feature_key == feature_key)
        ).scalar_one_or_none()

    def list_feature_gates(self, *, limit: int = 500) -> list[ProductFeatureGate]:
        return list(
            self._session.execute(
                select(ProductFeatureGate)
                .order_by(ProductFeatureGate.feature_key)
                .limit(limit)
            ).scalars()
        )

    def get_assignment(self, *, user_id: str, experiment_key: str) -> ExperimentAssignment | None:
        return self._session.execute(
            select(ExperimentAssignment).where(
                ExperimentAssignment.user_id == user_id,
                ExperimentAssignment.experiment_key == experiment_key,
            )
        ).scalar_one_or_none()

    def list_assignments(
        self,
        *,
        user_id: str | None = None,
        experiment_key: str | None = None,
        limit: int = 500,
    ) -> list[ExperimentAssignment]:
        stmt = select(ExperimentAssignment)
        if user_id is not None:
            stmt = stmt.where(ExperimentAssignment.user_id == user_id)
        if experiment_key is not None:
            stmt = stmt.where(ExperimentAssignment.experiment_key == experiment_key)
        return list(
            self._session.execute(
                stmt.order_by(
                    ExperimentAssignment.assigned_at.desc(),
                    ExperimentAssignment.assignment_id.desc(),
                ).limit(limit)
            ).scalars()
        )

    def get_support_case(self, support_case_id: str) -> SupportCase | None:
        return self._session.get(SupportCase, support_case_id)

    def list_support_cases(
        self,
        *,
        user_id: str | None = None,
        status: str | None = None,
        case_type: str | None = None,
        limit: int = 500,
    ) -> list[SupportCase]:
        stmt = select(SupportCase)
        if user_id is not None:
            stmt = stmt.where(SupportCase.user_id == user_id)
        if status is not None:
            stmt = stmt.where(SupportCase.status == status)
        if case_type is not None:
            stmt = stmt.where(SupportCase.case_type == case_type)
        return list(
            self._session.execute(
                stmt.order_by(SupportCase.updated_at.desc(), SupportCase.support_case_id).limit(
                    limit
                )
            ).scalars()
        )

    def list_entitlement_grants(
        self,
        *,
        user_id: str,
        feature_key: str | None = None,
        active_only: bool = True,
    ) -> list[ProductEntitlementGrant]:
        stmt = select(ProductEntitlementGrant).where(ProductEntitlementGrant.user_id == user_id)
        if feature_key is not None:
            stmt = stmt.where(ProductEntitlementGrant.feature_key == feature_key)
        if active_only:
            stmt = stmt.where(ProductEntitlementGrant.status == "active")
        return list(
            self._session.execute(
                stmt.order_by(
                    ProductEntitlementGrant.effective_at.desc(),
                    ProductEntitlementGrant.entitlement_grant_id.desc(),
                )
            ).scalars()
        )

    def list_commercial_signals(
        self,
        *,
        user_id: str | None = None,
        experiment_key: str | None = None,
        limit: int = 500,
    ) -> list[CommercialExperimentSignal]:
        stmt = select(CommercialExperimentSignal)
        if user_id is not None:
            stmt = stmt.where(CommercialExperimentSignal.user_id == user_id)
        if experiment_key is not None:
            stmt = stmt.where(CommercialExperimentSignal.experiment_key == experiment_key)
        return list(
            self._session.execute(
                stmt.order_by(
                    CommercialExperimentSignal.created_at.desc(),
                    CommercialExperimentSignal.signal_id.desc(),
                ).limit(limit)
            ).scalars()
        )

    def flush(self) -> None:
        self._session.flush()
