from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base, CanonicalMixin


class CompanyRegionEntryLevel(Base, CanonicalMixin):
    """Early-career opportunity signals for a company in a specific region.

    Internships and co-ops are stored as separate counts but are weighted
    equally downstream (Slice 9). Counts default to NULL because unknown
    metadata must not be silently treated as zero.
    """

    __tablename__ = "company_region_entry_level"
    __table_args__ = (
        UniqueConstraint("company_id", "region_id", name="uq_entry_level_company_region"),
        Index("ix_entry_level_company_id", "company_id"),
        Index("ix_entry_level_region_id", "region_id"),
        Index("ix_entry_level_region_score", "region_id", "entry_level_access_score"),
        Index("ix_entry_level_region_internship", "region_id", "internship_count"),
        Index("ix_entry_level_region_coop", "region_id", "coop_count"),
    )

    entry_level_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("companies.company_id"), nullable=False
    )
    region_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("regions.region_id"), nullable=False
    )

    internship_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    internship_count_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    coop_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coop_count_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_level_full_time_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_level_full_time_count_status: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    formal_early_career_program_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    student_season_recurrence_signal: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entry_level_access_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_level_confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)

    freshness_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_refs: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
