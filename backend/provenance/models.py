from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.shared.db import Base, CanonicalMixin


class SourceRef(Base, CanonicalMixin):
    """Reference to a source or provider from which observations can be made."""

    __tablename__ = "source_refs"
    __table_args__ = (
        Index("ix_source_refs_source_type", "source_type"),
        Index("ix_source_refs_data_origin", "data_origin"),
        Index("ix_source_refs_license", "license_or_terms_category"),
    )

    source_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    url_or_provider: Mapped[str] = mapped_column(String(1024), nullable=False)
    collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    license_or_terms_category: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    observations: Mapped[list[SourceObservation]] = relationship(
        "SourceObservation",
        back_populates="source_ref",
        cascade="all, delete-orphan",
    )


class SourceObservation(Base, CanonicalMixin):
    """A dated observation made against a source reference."""

    __tablename__ = "source_observations"
    __table_args__ = (
        Index("ix_source_observations_source_id", "source_id"),
        Index("ix_source_observations_source_type", "source_type"),
        Index("ix_source_observations_data_origin", "data_origin"),
        Index("ix_source_observations_collected_at", "collected_at"),
        Index("ix_source_observations_observed_at", "observed_at"),
    )

    observation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("source_refs.source_id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    url_or_provider: Mapped[str] = mapped_column(String(1024), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    license_or_terms_category: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(64), nullable=False)
    observation_status: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    source_ref: Mapped[SourceRef] = relationship(
        "SourceRef",
        back_populates="observations",
    )
    fact_links: Mapped[list[FactSourceLink]] = relationship(
        "FactSourceLink",
        back_populates="observation",
        cascade="all, delete-orphan",
        foreign_keys="FactSourceLink.observation_id",
    )


class FactSourceLink(Base, CanonicalMixin):
    """Polymorphic link from a market fact to a source observation."""

    __tablename__ = "fact_source_links"
    __table_args__ = (
        UniqueConstraint(
            "fact_type",
            "fact_id",
            "fact_field",
            "observation_id",
            name="uq_fact_source_link_fact_observation",
        ),
        Index("ix_fact_source_links_observation_id", "observation_id"),
        Index("ix_fact_source_links_source_id", "source_id"),
        Index("ix_fact_source_links_fact", "fact_type", "fact_id"),
        Index("ix_fact_source_links_data_origin", "data_origin"),
    )

    link_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    observation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("source_observations.observation_id"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("source_refs.source_id"), nullable=False
    )
    fact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    fact_id: Mapped[str] = mapped_column(String(128), nullable=False)
    fact_field: Mapped[str | None] = mapped_column(String(128), nullable=True)

    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    url_or_provider: Mapped[str] = mapped_column(String(1024), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    license_or_terms_category: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(64), nullable=False)
    observation_status: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    observation: Mapped[SourceObservation] = relationship(
        "SourceObservation",
        back_populates="fact_links",
        foreign_keys=[observation_id],
    )
    source_ref: Mapped[SourceRef] = relationship("SourceRef")
