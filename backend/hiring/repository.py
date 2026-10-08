"""Thin data-access layer for the CompanyRegionHiring table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.hiring.models import CompanyRegionHiring


class HiringRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def get(self, hiring_id: str) -> CompanyRegionHiring | None:
        return self._session.get(CompanyRegionHiring, hiring_id)

    def get_by_pair(
        self, company_id: str, region_id: str
    ) -> CompanyRegionHiring | None:
        stmt = select(CompanyRegionHiring).where(
            CompanyRegionHiring.company_id == company_id,
            CompanyRegionHiring.region_id == region_id,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def exists(self, hiring_id: str) -> bool:
        return self.get(hiring_id) is not None

    def list(self) -> list[CompanyRegionHiring]:
        rows = self._session.execute(
            select(CompanyRegionHiring).order_by(
                CompanyRegionHiring.company_id, CompanyRegionHiring.region_id
            )
        ).scalars()
        return list(rows)

    def add(self, hiring: CompanyRegionHiring) -> None:
        self._session.add(hiring)

    def flush(self) -> None:
        self._session.flush()
