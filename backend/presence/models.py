from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base, CanonicalMixin


class CompanyRegionPresence(Base, CanonicalMixin):
    """Whether a company has meaningful presence in a specific region.

    For MVP one current record per (company, region) pair is acceptable;
    versioning is captured by the ``version`` column on CanonicalMixin.
    """

    __tablename__ = "company_region_presence"
    __table_args__ = (
        UniqueConstraint("company_id", "region_id", name="uq_presence_company_region"),
        Index("ix_presence_company_id", "company_id"),
        Index("ix_presence_region_id", "region_id"),
        Index("ix_presence_status", "presence_status"),
        Index("ix_presence_region_status", "region_id", "presence_status"),
    )

    presence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("companies.company_id"), nullable=False
    )
    region_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("regions.region_id"), nullable=False
    )

    presence_status: Mapped[str] = mapped_column(String(32), nullable=False)
    presence_basis: Mapped[str | None] = mapped_column(String(64), nullable=True)
    office_evidence_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    operations_evidence_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hiring_evidence_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    presence_confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)

    source_refs: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
