"""Thin data-access layer for provenance records."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef


class ProvenanceRepository:
    """Repository for source references, observations, and fact-source links."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_source_ref(self, source_id: str) -> SourceRef | None:
        return self._session.get(SourceRef, source_id)

    def list_source_refs(self) -> list[SourceRef]:
        rows = self._session.execute(select(SourceRef).order_by(SourceRef.source_id))
        return list(rows.scalars())

    def add_source_ref(self, source_ref: SourceRef) -> None:
        self._session.add(source_ref)

    def get_observation(self, observation_id: str) -> SourceObservation | None:
        return self._session.get(SourceObservation, observation_id)

    def list_observations(self) -> list[SourceObservation]:
        rows = self._session.execute(
            select(SourceObservation).order_by(SourceObservation.observation_id)
        )
        return list(rows.scalars())

    def add_observation(self, observation: SourceObservation) -> None:
        self._session.add(observation)

    def get_fact_source_link(self, link_id: str) -> FactSourceLink | None:
        return self._session.get(FactSourceLink, link_id)

    def list_fact_source_links(self) -> list[FactSourceLink]:
        rows = self._session.execute(
            select(FactSourceLink).order_by(
                FactSourceLink.fact_type,
                FactSourceLink.fact_id,
                FactSourceLink.link_id,
            )
        )
        return list(rows.scalars())

    def add_fact_source_link(self, link: FactSourceLink) -> None:
        self._session.add(link)

    def flush(self) -> None:
        self._session.flush()
