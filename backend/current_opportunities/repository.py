"""Repository helpers for Layer 38A current opportunities."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.current_opportunities.models import (
    CurrentOpportunity,
    CurrentOpportunitySourceLink,
    OpportunityAcquisitionRun,
    OpportunityCoverageContract,
    OpportunityDataSource,
    OpportunityPromotionReceipt,
    OpportunitySourceObservation,
)


class CurrentOpportunityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def add(self, row: object) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()

    def get_source(self, source_id: str) -> OpportunityDataSource | None:
        return self._session.get(OpportunityDataSource, source_id)

    def list_sources(self) -> list[OpportunityDataSource]:
        return list(
            self._session.execute(
                select(OpportunityDataSource).order_by(OpportunityDataSource.source_id)
            ).scalars()
        )

    def get_run(self, run_id: str) -> OpportunityAcquisitionRun | None:
        return self._session.get(OpportunityAcquisitionRun, run_id)

    def get_run_by_idempotency_key(self, idempotency_key: str) -> OpportunityAcquisitionRun | None:
        return self._session.execute(
            select(OpportunityAcquisitionRun).where(
                OpportunityAcquisitionRun.idempotency_key == idempotency_key
            )
        ).scalar_one_or_none()

    def latest_runs(
        self, *, source_id: str | None = None, limit: int = 100
    ) -> list[OpportunityAcquisitionRun]:
        stmt = select(OpportunityAcquisitionRun)
        if source_id is not None:
            stmt = stmt.where(OpportunityAcquisitionRun.source_id == source_id)
        return list(
            self._session.execute(
                stmt.order_by(
                    OpportunityAcquisitionRun.started_at.desc(),
                    OpportunityAcquisitionRun.run_id,
                ).limit(limit)
            ).scalars()
        )

    def get_observation(self, observation_id: str) -> OpportunitySourceObservation | None:
        return self._session.get(OpportunitySourceObservation, observation_id)

    def get_observation_for_run_record(
        self,
        *,
        source_id: str,
        run_id: str,
        provider_record_id: str,
    ) -> OpportunitySourceObservation | None:
        return self._session.execute(
            select(OpportunitySourceObservation).where(
                OpportunitySourceObservation.source_id == source_id,
                OpportunitySourceObservation.run_id == run_id,
                OpportunitySourceObservation.provider_record_id == provider_record_id,
            )
        ).scalar_one_or_none()

    def get_opportunity(self, opportunity_id: str) -> CurrentOpportunity | None:
        return self._session.get(CurrentOpportunity, opportunity_id)

    def get_opportunity_by_identity_key(self, identity_key: str) -> CurrentOpportunity | None:
        return self._session.execute(
            select(CurrentOpportunity).where(
                CurrentOpportunity.canonical_identity_key == identity_key
            )
        ).scalar_one_or_none()

    def get_opportunity_by_duplicate_group(
        self, duplicate_group_key: str
    ) -> CurrentOpportunity | None:
        return self._session.execute(
            select(CurrentOpportunity)
            .where(CurrentOpportunity.duplicate_group_key == duplicate_group_key)
            .order_by(CurrentOpportunity.created_at, CurrentOpportunity.current_opportunity_id)
            .limit(1)
        ).scalar_one_or_none()

    def get_source_link(
        self, *, source_id: str, provider_record_id: str
    ) -> CurrentOpportunitySourceLink | None:
        return self._session.execute(
            select(CurrentOpportunitySourceLink).where(
                CurrentOpportunitySourceLink.source_id == source_id,
                CurrentOpportunitySourceLink.provider_record_id == provider_record_id,
            )
        ).scalar_one_or_none()

    def list_source_links(
        self,
        opportunity_id: str,
        *,
        active_only: bool = False,
    ) -> list[CurrentOpportunitySourceLink]:
        stmt = select(CurrentOpportunitySourceLink).where(
            CurrentOpportunitySourceLink.current_opportunity_id == opportunity_id
        )
        if active_only:
            stmt = stmt.where(CurrentOpportunitySourceLink.active.is_(True))
        return list(
            self._session.execute(stmt.order_by(CurrentOpportunitySourceLink.source_id)).scalars()
        )

    def list_source_links_for_opportunities(
        self,
        opportunity_ids: list[str],
        *,
        active_only: bool = False,
    ) -> dict[str, list[CurrentOpportunitySourceLink]]:
        if not opportunity_ids:
            return {}
        stmt = select(CurrentOpportunitySourceLink).where(
            CurrentOpportunitySourceLink.current_opportunity_id.in_(opportunity_ids)
        )
        if active_only:
            stmt = stmt.where(CurrentOpportunitySourceLink.active.is_(True))
        rows = list(
            self._session.execute(
                stmt.order_by(
                    CurrentOpportunitySourceLink.current_opportunity_id,
                    CurrentOpportunitySourceLink.source_id,
                )
            ).scalars()
        )
        links_by_opportunity = {opportunity_id: [] for opportunity_id in opportunity_ids}
        for row in rows:
            links_by_opportunity.setdefault(row.current_opportunity_id, []).append(row)
        return links_by_opportunity

    def list_sources_by_ids(self, source_ids: set[str]) -> dict[str, OpportunityDataSource]:
        if not source_ids:
            return {}
        rows = self._session.execute(
            select(OpportunityDataSource).where(OpportunityDataSource.source_id.in_(source_ids))
        ).scalars()
        return {row.source_id: row for row in rows}

    def list_opportunities(
        self,
        *,
        market: str | None = None,
        role_family: str | None = None,
        opportunity_type: str | None = None,
        work_arrangement: str | None = None,
        ranking_eligible: bool | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CurrentOpportunity]:
        stmt = select(CurrentOpportunity)
        if market is not None:
            stmt = stmt.where(CurrentOpportunity.market_id == market)
        if role_family is not None:
            stmt = stmt.where(CurrentOpportunity.role_family == role_family)
        if opportunity_type is not None:
            stmt = stmt.where(CurrentOpportunity.opportunity_type == opportunity_type)
        if work_arrangement is not None:
            stmt = stmt.where(CurrentOpportunity.work_arrangement == work_arrangement)
        if ranking_eligible is not None:
            stmt = stmt.where(CurrentOpportunity.ranking_eligible.is_(ranking_eligible))
        if status is not None:
            stmt = stmt.where(CurrentOpportunity.canonical_status == status)
        return list(
            self._session.execute(
                stmt.order_by(
                    CurrentOpportunity.ranking_eligible.desc(),
                    CurrentOpportunity.last_observed_at.desc().nullslast(),
                    CurrentOpportunity.current_opportunity_id,
                )
                .offset(offset)
                .limit(limit)
            ).scalars()
        )

    def list_coverage_contracts(self) -> list[OpportunityCoverageContract]:
        return list(
            self._session.execute(
                select(OpportunityCoverageContract).order_by(
                    OpportunityCoverageContract.market_key,
                    OpportunityCoverageContract.role_family,
                    OpportunityCoverageContract.opportunity_type,
                )
            ).scalars()
        )

    def get_coverage(
        self,
        *,
        market_key: str,
        role_family: str,
        opportunity_type: str,
    ) -> OpportunityCoverageContract | None:
        candidates = [
            (market_key, role_family, opportunity_type),
            (market_key, role_family, "*"),
            (market_key, "*", opportunity_type),
            (market_key, "*", "*"),
            ("*", role_family, opportunity_type),
            ("*", role_family, "*"),
            ("*", "*", opportunity_type),
            ("*", "*", "*"),
        ]
        for scope in candidates:
            market_matches = [OpportunityCoverageContract.market_key == scope[0]]
            if scope[0] != "*":
                market_matches.append(
                    OpportunityCoverageContract.market_id == scope[0]
                )
            for market_match in market_matches:
                row = self._session.execute(
                    select(OpportunityCoverageContract).where(
                        market_match,
                        OpportunityCoverageContract.role_family == scope[1],
                        OpportunityCoverageContract.opportunity_type == scope[2],
                    )
                ).scalars().first()
                if row is not None:
                    return row
        return None

    def latest_promotion_receipt(self, run_id: str) -> OpportunityPromotionReceipt | None:
        return self._session.execute(
            select(OpportunityPromotionReceipt).where(OpportunityPromotionReceipt.run_id == run_id)
        ).scalar_one_or_none()
