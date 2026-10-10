"""Persistence for immutable Explore comparison snapshots and Decision provenance."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


COMPARISON_RECOMMENDATION_SQL = (
    "'clear_recommendation', 'near_tie', 'exact_tie', 'insufficient_evidence', "
    "'blocking_contradiction', 'unsupported_member', 'outside_constraints'"
)


class ExploreComparisonSnapshot(Base):
    """A minimized, immutable record of one governed comparison result."""

    __tablename__ = "explore_comparison_snapshots"
    __table_args__ = (
        CheckConstraint(
            "snapshot_schema_version >= 1", name="ck_explore_comparison_schema_version"
        ),
        CheckConstraint(
            f"recommendation_state IN ({COMPARISON_RECOMMENDATION_SQL})",
            name="ck_explore_comparison_recommendation_state",
        ),
        UniqueConstraint(
            "user_id", "comparison_identity", name="uq_explore_comparison_user_identity"
        ),
        Index("ix_explore_comparison_user_saved", "user_id", "saved_at"),
        Index("ix_explore_comparison_user_generated", "user_id", "generated_at"),
        Index("ix_explore_comparison_context", "context_fingerprint"),
    )

    comparison_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    snapshot_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    comparison_identity: Mapped[str] = mapped_column(String(80), nullable=False)
    selected_region_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    selected_public_slugs: Mapped[list] = mapped_column(JSON, nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_context_summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    recommendation_state: Mapped[str] = mapped_column(String(40), nullable=False)
    winner_region_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    tie_region_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_authority_version: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_bundle: Mapped[str] = mapped_column(String(80), nullable=False)
    calibration_version: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    recommendation_summary: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class ExploreDecisionProvenance(Base):
    """Explicit bridge from Explore evidence to the owning Layer 36 Decision."""

    __tablename__ = "explore_decision_provenance"
    __table_args__ = (
        UniqueConstraint("decision_id", name="uq_explore_decision_provenance_decision"),
        Index("ix_explore_decision_provenance_user", "user_id"),
        Index("ix_explore_decision_provenance_comparison", "comparison_id"),
        Index(
            "ix_explore_decision_provenance_equivalent",
            "user_id",
            "context_fingerprint",
            "market_set_fingerprint",
            "user_selected_region_id",
        ),
    )

    provenance_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=False
    )
    comparison_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("explore_comparison_snapshots.comparison_id"), nullable=False
    )
    context_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    market_set_fingerprint: Mapped[str] = mapped_column(String(80), nullable=False)
    system_recommendation_state: Mapped[str] = mapped_column(String(40), nullable=False)
    system_recommended_region_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    user_selected_region_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("regions.region_id"), nullable=False
    )
    choice_matches_recommendation: Mapped[bool | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
