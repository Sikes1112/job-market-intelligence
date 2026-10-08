"""New-product authority adapters consumed by Career Agent orchestration.

Legacy Career Agent answer routes remain compatible. New geographic orchestration
must enter through this adapter and receives Explore Fit output without an
independent city score. Durable Decisions and current-job matching retain their
own jurisdictions.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from backend.career_decisions.repository import CareerDecisionRepository
from backend.current_opportunities.repository import CurrentOpportunityRepository
from backend.current_opportunities.service import CurrentOpportunityService
from backend.deep_decisions.repository import DeepDecisionRepository
from backend.explore.schemas import (
    ExploreMarketsResponse,
    ExploreSessionOverrides,
)
from backend.explore.service import ExploreFitService


class CareerAgentAuthorityAdapter:
    def __init__(
        self,
        explore_fit: ExploreFitService,
        *,
        current_opportunities: CurrentOpportunityService | None = None,
        decisions: CareerDecisionRepository | None = None,
        deep_decisions: DeepDecisionRepository | None = None,
    ) -> None:
        self._explore_fit = explore_fit
        self._current_opportunities = current_opportunities
        self._decisions = decisions
        self._deep_decisions = deep_decisions

    @classmethod
    def for_session(cls, session: Session) -> CareerAgentAuthorityAdapter:
        return cls(
            ExploreFitService(session),
            current_opportunities=CurrentOpportunityService(
                CurrentOpportunityRepository(session)
            ),
            decisions=CareerDecisionRepository(session),
            deep_decisions=DeepDecisionRepository(session),
        )

    def geographic_fit(
        self,
        user_id: str,
        overrides: ExploreSessionOverrides | None = None,
        *,
        as_of: date | datetime | None = None,
    ) -> ExploreMarketsResponse:
        """Return the geographic authority result without rescoring markets."""

        return self._explore_fit.evaluate(user_id, overrides, as_of=as_of)

    def current_job_matches(
        self,
        user_id: str,
        *,
        request_terms: tuple[str, ...] = (),
        limit: int = 100,
        as_of: datetime | None = None,
    ) -> tuple:
        """Return Layer 38 matches; no legacy Opportunity Route substitution."""

        if self._current_opportunities is None:
            return ()
        return self._current_opportunities.strategic_matches(
            user_id,
            request_terms=request_terms,
            include_ineligible=False,
            limit=limit,
            now=as_of,
        )

    def current_job_coverage(
        self,
        *,
        market_key: str,
        role_family: str,
        opportunity_type: str = "*",
        as_of: datetime | None = None,
    ):
        if self._current_opportunities is None:
            return None
        return self._current_opportunities.coverage(
            market_key=market_key,
            role_family=role_family,
            opportunity_type=opportunity_type,
            now=as_of,
        )

    def durable_decision(self, user_id: str):
        """Return the latest Layer 36 decision plus optional Layer 37 review."""

        if self._decisions is None:
            return None, None, None
        decisions = self._decisions.list_decisions(user_id, limit=1)
        if not decisions:
            return None, None, None
        decision = decisions[0]
        recommendation = (
            self._decisions.get_recommendation(decision.current_recommendation_id)
            if decision.current_recommendation_id
            else None
        )
        review = (
            self._deep_decisions.latest_strategic_review(
                user_id,
                decision_id=decision.decision_id,
            )
            if self._deep_decisions is not None
            else None
        )
        return decision, recommendation, review

    def durable_decision_actions(
        self,
        user_id: str,
        *,
        decision_id: str,
        limit: int = 20,
    ) -> tuple:
        """Return user-owned Layer 36 actions for the active planning decision."""

        if self._decisions is None:
            return ()
        return tuple(
            self._decisions.list_actions(
                user_id,
                decision_id=decision_id,
                limit=limit,
            )
        )
