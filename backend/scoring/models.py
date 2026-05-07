from __future__ import annotations

from sqlalchemy import (
    JSON,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base, CanonicalMixin


class RegionMarketScore(Base, CanonicalMixin):
    """Region-level scores derived from canonical truth.

    Slice 2 stores the columns; the formulas live in Slice 10. Scores are
    nullable so a partial score record (some components missing) can be
    represented honestly rather than zeroed out.
    """

    __tablename__ = "region_market_scores"
    __table_args__ = (
        UniqueConstraint("region_id", name="uq_region_market_scores_region"),
        Index("ix_region_scores_region_id", "region_id"),
        Index("ix_region_scores_objective", "objective_opportunity_score"),
        Index("ix_region_scores_early_career", "early_career_accessibility_score"),
    )

    region_score_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    region_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("regions.region_id"), nullable=False
    )

    structural_ecosystem_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    live_market_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    objective_opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    general_density_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    tech_market_density_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    early_career_accessibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    score_ruleset_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalization_profile_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_version_bundle: Mapped[dict | None] = mapped_column(JSON, nullable=True)
