"""Thin data-access layer for the Region table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.geography.models import Region


class RegionRepository:
    """Repository for :class:`backend.geography.models.Region`.

    Pure data access. No business validation lives here.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, region_id: str) -> Region | None:
        return self._session.get(Region, region_id)

    def exists(self, region_id: str) -> bool:
        return self.get(region_id) is not None

    def list(self) -> list[Region]:
        rows = self._session.execute(select(Region).order_by(Region.region_id)).scalars()
        return list(rows)

    def add(self, region: Region) -> None:
        self._session.add(region)

    def flush(self) -> None:
        self._session.flush()
