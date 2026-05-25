from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    """Shared timestamps for non-market user-account tables."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
    )


class User(Base, TimestampMixin):
    """Internal app user identity.

    This id is the app-facing user key. It is deliberately separate from any
    managed-auth provider subject so a provider migration does not rewrite
    internal ownership references.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "admin_role IS NULL OR "
            "admin_role IN ('admin', 'data_reviewer', 'read_only_operator')",
            name="ck_users_admin_role",
        ),
        Index("ix_users_admin_role", "admin_role"),
        Index("ix_users_status", "status"),
    )

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    admin_role: Mapped[str | None] = mapped_column(String(32), nullable=True)


class ExternalAuthIdentity(Base, TimestampMixin):
    """Stable mapping from a managed-auth identity to an internal user."""

    __tablename__ = "external_auth_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "issuer",
            "subject",
            name="uq_external_auth_identity_provider_subject",
        ),
        Index("ix_external_auth_identities_user_id", "user_id"),
        Index("ix_external_auth_identities_provider", "provider"),
    )

    external_identity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_verified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )


class UserProfile(Base, TimestampMixin):
    """Non-preference profile metadata sourced from the managed provider."""

    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id"), primary_key=True
    )
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class UserPreferenceProfile(Base, TimestampMixin):
    """Durable user-owned personalization inputs.

    These fields are inputs for personalization only. They do not write to
    objective market truth, scores, source freshness, or canonical region /
    company state.
    """

    __tablename__ = "user_preference_profiles"
    __table_args__ = (
        CheckConstraint(
            "prestige_weighting IS NULL OR prestige_weighting IN ('low', 'medium', 'high')",
            name="ck_user_preference_profiles_prestige_weighting",
        ),
        CheckConstraint(
            "brand_weighting IS NULL OR brand_weighting IN ('low', 'medium', 'high')",
            name="ck_user_preference_profiles_brand_weighting",
        ),
        CheckConstraint(
            "career_stage IS NULL OR career_stage IN ('entry_level')",
            name="ck_user_preference_profiles_career_stage",
        ),
        CheckConstraint(
            "remote_hybrid_preference IS NULL OR "
            "remote_hybrid_preference IN ('remote', 'hybrid', 'onsite', 'flexible')",
            name="ck_user_preference_profiles_remote_hybrid_preference",
        ),
    )

    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id"), primary_key=True
    )
    role_interests: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    industry_interests: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    preferred_regions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    prestige_weighting: Mapped[str | None] = mapped_column(String(16), nullable=True)
    brand_weighting: Mapped[str | None] = mapped_column(String(16), nullable=True)
    career_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    remote_hybrid_preference: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    scoring_weights: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class SavedMarketArtifact(Base, TimestampMixin):
    """User-owned saved reference or lightweight snapshot.

    ``artifact_ref`` points at objective artifacts such as a region id, company
    id, canonical comparison id, or caller-supplied discovery result reference.
    ``snapshot`` is user-owned display context and is never promoted into
    canonical market records.
    """

    __tablename__ = "saved_market_artifacts"
    __table_args__ = (
        CheckConstraint(
            "artifact_type IN "
            "('region', 'company', 'role_family', 'comparison', 'discovery_result')",
            name="ck_saved_market_artifacts_artifact_type",
        ),
        UniqueConstraint(
            "user_id",
            "artifact_type",
            "artifact_ref",
            name="uq_saved_market_artifacts_user_type_ref",
        ),
        Index("ix_saved_market_artifacts_user_id", "user_id"),
        Index("ix_saved_market_artifacts_artifact_type", "artifact_type"),
        Index("ix_saved_market_artifacts_user_type", "user_id", "artifact_type"),
    )

    saved_artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id"), nullable=False
    )
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    snapshot: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class PersonalizedRecommendationSnapshot(Base, TimestampMixin):
    """Derived user-owned personalized recommendation output.

    Snapshots may point at objective outputs through ``objective_output_refs``
    and carry the source/input versions used to derive the recommendation.
    They are never canonical market truth and do not write back to market rows.
    """

    __tablename__ = "personalized_recommendation_snapshots"
    __table_args__ = (
        Index("ix_rec_snapshots_user_id", "user_id"),
        Index("ix_rec_snapshots_user_generated_at", "user_id", "generated_at"),
        Index("ix_rec_snapshots_version", "recommendation_version"),
        Index("ix_rec_snapshots_inputs_hash", "recommendation_inputs_hash"),
    )

    recommendation_snapshot_id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id"), nullable=False
    )
    preference_profile_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("user_preference_profiles.user_id"), nullable=True
    )
    personalized_output: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    recommendation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_version_bundle: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    objective_output_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recommendation_inputs_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
