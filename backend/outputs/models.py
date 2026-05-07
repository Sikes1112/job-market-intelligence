from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base, CanonicalMixin


class OutputMetadata(Base, CanonicalMixin):
    """Metadata pointing at derived output artifacts.

    The actual payloads (region/company/comparison/contextual challenge JSON)
    live in object storage or cache; this row is the queryable index. Slice 11
    populates these records during output assembly.
    """

    __tablename__ = "output_metadata"
    __table_args__ = (
        UniqueConstraint("output_type", "subject_id", name="uq_output_type_subject"),
        Index("ix_output_metadata_type", "output_type"),
        Index("ix_output_metadata_subject", "subject_id"),
        Index("ix_output_metadata_state", "state"),
    )

    output_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    output_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)

    artifact_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    artifact_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_version_bundle: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    freshness_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
