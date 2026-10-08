"""Repository helpers for region expansion workflows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.region_expansion.models import RegionExpansionWorkflow


class RegionExpansionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def add(self, row: RegionExpansionWorkflow) -> None:
        self._session.add(row)

    def get(self, workflow_id: str) -> RegionExpansionWorkflow | None:
        return self._session.get(RegionExpansionWorkflow, workflow_id)

    def get_by_region_key(self, region_key: str) -> RegionExpansionWorkflow | None:
        return self._session.execute(
            select(RegionExpansionWorkflow).where(
                RegionExpansionWorkflow.region_key == region_key
            )
        ).scalar_one_or_none()

    def list_workflows(self) -> list[RegionExpansionWorkflow]:
        rows = self._session.execute(
            select(RegionExpansionWorkflow).order_by(
                RegionExpansionWorkflow.region_key
            )
        ).scalars()
        return list(rows)

    def flush(self) -> None:
        self._session.flush()
