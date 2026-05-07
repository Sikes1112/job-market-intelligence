"""Thin data-access layer for the OutputMetadata table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.outputs.models import OutputMetadata


class OutputMetadataRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, output_id: str) -> OutputMetadata | None:
        return self._session.get(OutputMetadata, output_id)

    def get_by_type_and_subject(
        self, output_type: str, subject_id: str
    ) -> OutputMetadata | None:
        stmt = select(OutputMetadata).where(
            OutputMetadata.output_type == output_type,
            OutputMetadata.subject_id == subject_id,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def list(self) -> list[OutputMetadata]:
        rows = self._session.execute(
            select(OutputMetadata).order_by(
                OutputMetadata.output_type, OutputMetadata.subject_id
            )
        ).scalars()
        return list(rows)

    def add(self, row: OutputMetadata) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()
