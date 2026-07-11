from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base, CanonicalMixin


class CompanyRegionHiring(Base, CanonicalMixin):
    """Hiring activity for a company in a specific region.

    Counts are nullable on purpose: an unknown count is not the same as zero.
    Slice 8 will populate these from structured input; Slice 9 reads them for
    entry-level extraction.
    """

    __tablename__ = "company_region_hiring"
    __table_args__ = (
        UniqueConstraint("company_id", "region_id", name="uq_hiring_company_region"),
        Index("ix_hiring_company_id", "company_id"),
        Index("ix_hiring_region_id", "region_id"),
        Index("ix_hiring_currently_hiring", "currently_hiring_flag"),
        Index("ix_hiring_region_currently_hiring", "region_id", "currently_hiring_flag"),
        Index("ix_hiring_region_active_now", "region_id", "active_posting_count_now"),
    )

    hiring_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("companies.company_id"), nullable=False
    )
    region_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("regions.region_id"), nullable=False
    )

    currently_hiring_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active_posting_count_now: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_posting_count_now_status: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    posting_count_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posting_count_30d_status: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    posting_count_90d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posting_count_90d_status: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    annualized_trend_signal: Mapped[str | None] = mapped_column(String(32), nullable=True)
    seasonal_student_hiring_signal: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hiring_program_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hiring_program_count_status: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    role_family_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    hiring_confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    freshness_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_refs: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
