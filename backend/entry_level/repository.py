"""Thin data-access layer for the CompanyRegionEntryLevel table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.entry_level.models import CompanyRegionEntryLevel


class EntryLevelRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def get(self, entry_level_id: str) -> CompanyRegionEntryLevel | None:
        return self._session.get(CompanyRegionEntryLevel, entry_level_id)

    def get_by_pair(
        self, company_id: str, region_id: str
    ) -> CompanyRegionEntryLevel | None:
        stmt = select(CompanyRegionEntryLevel).where(
            CompanyRegionEntryLevel.company_id == company_id,
            CompanyRegionEntryLevel.region_id == region_id,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def exists(self, entry_level_id: str) -> bool:
        return self.get(entry_level_id) is not None

    def list(self) -> list[CompanyRegionEntryLevel]:
        rows = self._session.execute(
            select(CompanyRegionEntryLevel).order_by(
                CompanyRegionEntryLevel.company_id,
                CompanyRegionEntryLevel.region_id,
            )
        ).scalars()
        return list(rows)

    def add(self, row: CompanyRegionEntryLevel) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()
