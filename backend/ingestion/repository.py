"""Thin data-access layer for raw ingestion records."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.ingestion.models import RawIngestionRecord
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.scoring.models import RegionMarketScore


class IngestionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def get_raw_record(self, raw_record_id: str) -> RawIngestionRecord | None:
        return self._session.get(RawIngestionRecord, raw_record_id)

    def list_raw_records(self) -> list[RawIngestionRecord]:
        rows = self._session.execute(
            select(RawIngestionRecord).order_by(RawIngestionRecord.raw_record_id)
        )
        return list(rows.scalars())

    def add_raw_record(self, record: RawIngestionRecord) -> None:
        self._session.add(record)

    def get_source_ref(self, source_id: str) -> SourceRef | None:
        return self._session.get(SourceRef, source_id)

    def get_observation(self, observation_id: str) -> SourceObservation | None:
        return self._session.get(SourceObservation, observation_id)

    def get_fact_source_link(self, link_id: str) -> FactSourceLink | None:
        return self._session.get(FactSourceLink, link_id)

    def get_company(self, company_id: str) -> Company | None:
        return self._session.get(Company, company_id)

    def get_region(self, region_id: str) -> Region | None:
        return self._session.get(Region, region_id)

    def get_presence_by_pair(
        self, company_id: str, region_id: str
    ) -> CompanyRegionPresence | None:
        return self._session.execute(
            select(CompanyRegionPresence).where(
                CompanyRegionPresence.company_id == company_id,
                CompanyRegionPresence.region_id == region_id,
            )
        ).scalar_one_or_none()

    def get_presence(self, presence_id: str) -> CompanyRegionPresence | None:
        return self._session.get(CompanyRegionPresence, presence_id)

    def list_presence_by_company(
        self, company_id: str
    ) -> list[CompanyRegionPresence]:
        rows = self._session.execute(
            select(CompanyRegionPresence)
            .where(CompanyRegionPresence.company_id == company_id)
            .order_by(CompanyRegionPresence.region_id)
        )
        return list(rows.scalars())

    def get_hiring_by_pair(
        self, company_id: str, region_id: str
    ) -> CompanyRegionHiring | None:
        return self._session.execute(
            select(CompanyRegionHiring).where(
                CompanyRegionHiring.company_id == company_id,
                CompanyRegionHiring.region_id == region_id,
            )
        ).scalar_one_or_none()

    def get_hiring(self, hiring_id: str) -> CompanyRegionHiring | None:
        return self._session.get(CompanyRegionHiring, hiring_id)

    def list_hiring_by_company(self, company_id: str) -> list[CompanyRegionHiring]:
        rows = self._session.execute(
            select(CompanyRegionHiring)
            .where(CompanyRegionHiring.company_id == company_id)
            .order_by(CompanyRegionHiring.region_id)
        )
        return list(rows.scalars())

    def get_entry_level_by_pair(
        self, company_id: str, region_id: str
    ) -> CompanyRegionEntryLevel | None:
        return self._session.execute(
            select(CompanyRegionEntryLevel).where(
                CompanyRegionEntryLevel.company_id == company_id,
                CompanyRegionEntryLevel.region_id == region_id,
            )
        ).scalar_one_or_none()

    def get_entry_level(self, entry_level_id: str) -> CompanyRegionEntryLevel | None:
        return self._session.get(CompanyRegionEntryLevel, entry_level_id)

    def list_entry_level_by_company(
        self, company_id: str
    ) -> list[CompanyRegionEntryLevel]:
        rows = self._session.execute(
            select(CompanyRegionEntryLevel)
            .where(CompanyRegionEntryLevel.company_id == company_id)
            .order_by(CompanyRegionEntryLevel.region_id)
        )
        return list(rows.scalars())

    def get_region_score_by_region(self, region_id: str) -> RegionMarketScore | None:
        return self._session.execute(
            select(RegionMarketScore).where(RegionMarketScore.region_id == region_id)
        ).scalar_one_or_none()

    def add_company(self, row: Company) -> None:
        self._session.add(row)

    def add_region(self, row: Region) -> None:
        self._session.add(row)

    def add_presence(self, row: CompanyRegionPresence) -> None:
        self._session.add(row)

    def add_hiring(self, row: CompanyRegionHiring) -> None:
        self._session.add(row)

    def add_entry_level(self, row: CompanyRegionEntryLevel) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()
