"""Thin data-access layer for the Company table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company


class CompanyRepository:
    """Repository for :class:`backend.companies.models.Company`.

    Pure data access. No business validation lives here.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, company_id: str) -> Company | None:
        return self._session.get(Company, company_id)

    def exists(self, company_id: str) -> bool:
        return self.get(company_id) is not None

    def list(self) -> list[Company]:
        rows = self._session.execute(select(Company).order_by(Company.company_id)).scalars()
        return list(rows)

    def add(self, company: Company) -> None:
        self._session.add(company)

    def flush(self) -> None:
        self._session.flush()
