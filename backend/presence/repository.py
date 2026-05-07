"""Thin data-access layer for the CompanyRegionPresence table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.presence.models import CompanyRegionPresence


class PresenceRepository:
    """Repository for :class:`backend.presence.models.CompanyRegionPresence`.

    Pure data access. No rule evaluation lives here.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, presence_id: str) -> CompanyRegionPresence | None:
        return self._session.get(CompanyRegionPresence, presence_id)

    def get_by_pair(
        self, company_id: str, region_id: str
    ) -> CompanyRegionPresence | None:
        stmt = select(CompanyRegionPresence).where(
            CompanyRegionPresence.company_id == company_id,
            CompanyRegionPresence.region_id == region_id,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def exists(self, presence_id: str) -> bool:
        return self.get(presence_id) is not None

    def list(self) -> list[CompanyRegionPresence]:
        rows = self._session.execute(
            select(CompanyRegionPresence).order_by(
                CompanyRegionPresence.company_id, CompanyRegionPresence.region_id
            )
        ).scalars()
        return list(rows)

    def add(self, presence: CompanyRegionPresence) -> None:
        self._session.add(presence)

    def flush(self) -> None:
        self._session.flush()
