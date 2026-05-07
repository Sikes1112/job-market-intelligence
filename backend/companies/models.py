from __future__ import annotations

from sqlalchemy import Boolean, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base, CanonicalMixin


class Company(Base, CanonicalMixin):
    """Canonical company record.

    Classification truth only — region-specific hiring belongs to
    company_region_hiring (separate table). Confidence enums are stored as
    plain strings; rule enforcement is deferred.
    """

    __tablename__ = "companies"
    __table_args__ = (
        Index("ix_companies_normalized_name", "normalized_company_name"),
        Index("ix_companies_eligibility_status", "eligibility_status"),
        Index("ix_companies_is_major_tech", "is_major_tech"),
        Index("ix_companies_is_mag7", "is_mag7"),
        Index("ix_companies_sector_primary", "sector_primary"),
    )

    company_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_company_name: Mapped[str] = mapped_column(String(255), nullable=False)

    sector_primary: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sector_secondary: Mapped[str | None] = mapped_column(String(64), nullable=True)
    public_or_private: Mapped[str | None] = mapped_column(String(32), nullable=True)

    eligibility_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ineligible"
    )
    eligibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    eligibility_override_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    eligibility_override_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    classification_confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)

    is_major_tech: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    major_tech_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_mag7: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prestige_score: Mapped[float | None] = mapped_column(Float, nullable=True)
