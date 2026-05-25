from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.provenance.models import SourceObservation, SourceRef
from backend.shared.db import Base, CanonicalMixin


class RawIngestionRecord(Base, CanonicalMixin):
    """Externally observed raw information before canonicalization."""

    __tablename__ = "raw_ingestion_records"
    __table_args__ = (
        Index("ix_raw_ingestion_provider", "provider_id"),
        Index("ix_raw_ingestion_source_type", "source_type"),
        Index("ix_raw_ingestion_external_entity", "external_entity_id"),
        Index("ix_raw_ingestion_status", "ingestion_status"),
        Index("ix_raw_ingestion_normalization_status", "normalization_status"),
        Index("ix_raw_ingestion_intended_fact_type", "intended_fact_type"),
        Index("ix_raw_ingestion_source_id", "source_id"),
        Index("ix_raw_ingestion_observation_id", "observation_id"),
        Index("ix_raw_ingestion_payload_checksum", "payload_checksum"),
    )

    raw_record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    url_or_provider: Mapped[str] = mapped_column(String(1024), nullable=False)
    external_entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    normalized_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    payload_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    ingestion_status: Mapped[str] = mapped_column(String(64), nullable=False)
    normalization_status: Mapped[str] = mapped_column(String(64), nullable=False)
    intended_fact_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    source_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("source_refs.source_id"), nullable=True
    )
    observation_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("source_observations.observation_id"), nullable=True
    )

    parsing_notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    parsing_errors: Mapped[list | None] = mapped_column(JSON, nullable=True)

    source_ref: Mapped[SourceRef | None] = relationship(
        "SourceRef", foreign_keys=[source_id]
    )
    source_observation: Mapped[SourceObservation | None] = relationship(
        "SourceObservation", foreign_keys=[observation_id]
    )
