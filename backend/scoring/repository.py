"""Data-access layer for the RegionMarketScore table and the canonical-truth
reads scoring needs.

Reading from upstream models (companies / presence / hiring / entry-level)
is allowed; importing upstream *services* is not. This repository keeps the
scoring slice's queries in one place so the service stays clean and the
layer-isolation test has one obvious surface to inspect.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.data_standards.ranking_gate import ranking_eligible_fact_ids
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.hiring.models import CompanyRegionHiring
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore


class RegionScoreRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- score CRUD ------------------------------------------------------

    def get_score(self, region_score_id: str) -> RegionMarketScore | None:
        return self._session.get(RegionMarketScore, region_score_id)

    def get_score_by_region(self, region_id: str) -> RegionMarketScore | None:
        stmt = select(RegionMarketScore).where(
            RegionMarketScore.region_id == region_id
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def list_scores(self) -> list[RegionMarketScore]:
        rows = self._session.execute(
            select(RegionMarketScore).order_by(RegionMarketScore.region_id)
        ).scalars()
        return list(rows)

    def add_score(self, score: RegionMarketScore) -> None:
        self._session.add(score)

    def flush(self) -> None:
        self._session.flush()

    # --- canonical-truth reads (no upstream services) --------------------

    def list_present_companies_for_region(self, region_id: str) -> list[Company]:
        """Return Company rows that have presence_status='present' in the region."""
        stmt = (
            select(Company, CompanyRegionPresence)
            .join(
                CompanyRegionPresence,
                Company.company_id == CompanyRegionPresence.company_id,
            )
            .where(
                CompanyRegionPresence.region_id == region_id,
                CompanyRegionPresence.presence_status == "present",
            )
            .order_by(Company.company_id)
        )
        rows = list(self._session.execute(stmt).all())
        eligible_presence_ids = ranking_eligible_fact_ids(
            self._session,
            "company_region_presence",
            [presence.presence_id for _company, presence in rows],
            allow_legacy_unassessed=True,
        )
        eligible_company_ids = ranking_eligible_fact_ids(
            self._session,
            "company",
            [company.company_id for company, _presence in rows],
            allow_legacy_unassessed=True,
        )
        return [
            company
            for company, presence in rows
            if presence.presence_id in eligible_presence_ids
            and company.company_id in eligible_company_ids
        ]

    def list_hiring_for_region(self, region_id: str) -> list[CompanyRegionHiring]:
        stmt = (
            select(CompanyRegionHiring)
            .where(CompanyRegionHiring.region_id == region_id)
            .order_by(CompanyRegionHiring.company_id)
        )
        rows = list(self._session.execute(stmt).scalars())
        eligible_ids = ranking_eligible_fact_ids(
            self._session,
            "company_region_hiring",
            [row.hiring_id for row in rows],
            allow_legacy_unassessed=True,
        )
        return [row for row in rows if row.hiring_id in eligible_ids]

    def list_entry_level_for_region(
        self, region_id: str
    ) -> list[CompanyRegionEntryLevel]:
        stmt = (
            select(CompanyRegionEntryLevel)
            .where(CompanyRegionEntryLevel.region_id == region_id)
            .order_by(CompanyRegionEntryLevel.company_id)
        )
        rows = list(self._session.execute(stmt).scalars())
        eligible_ids = ranking_eligible_fact_ids(
            self._session,
            "company_region_entry_level",
            [row.entry_level_id for row in rows],
            allow_legacy_unassessed=True,
        )
        return [row for row in rows if row.entry_level_id in eligible_ids]
