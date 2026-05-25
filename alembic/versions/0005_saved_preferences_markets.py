"""Add saved preferences and saved market artifacts.

Revision ID: 0005_saved_preferences_markets
Revises: 0004_auth_user_foundation
Create Date: 2026-05-21
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_saved_preferences_markets"
down_revision = "0004_auth_user_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_preference_profiles",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("role_interests", sa.JSON(), nullable=False),
        sa.Column("industry_interests", sa.JSON(), nullable=False),
        sa.Column("preferred_regions", sa.JSON(), nullable=False),
        sa.Column("prestige_weighting", sa.String(length=16), nullable=True),
        sa.Column("brand_weighting", sa.String(length=16), nullable=True),
        sa.Column("career_stage", sa.String(length=32), nullable=True),
        sa.Column("remote_hybrid_preference", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "prestige_weighting IS NULL OR prestige_weighting IN ('low', 'medium', 'high')",
            name="ck_user_preference_profiles_prestige_weighting",
        ),
        sa.CheckConstraint(
            "brand_weighting IS NULL OR brand_weighting IN ('low', 'medium', 'high')",
            name="ck_user_preference_profiles_brand_weighting",
        ),
        sa.CheckConstraint(
            "career_stage IS NULL OR career_stage IN ('entry_level')",
            name="ck_user_preference_profiles_career_stage",
        ),
        sa.CheckConstraint(
            "remote_hybrid_preference IS NULL OR "
            "remote_hybrid_preference IN ('remote', 'hybrid', 'onsite', 'flexible')",
            name="ck_user_preference_profiles_remote_hybrid_preference",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "saved_market_artifacts",
        sa.Column("saved_artifact_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column("artifact_ref", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.String(length=2048), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "artifact_type IN ('region', 'company', 'comparison', 'discovery_result')",
            name="ck_saved_market_artifacts_artifact_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("saved_artifact_id"),
        sa.UniqueConstraint(
            "user_id",
            "artifact_type",
            "artifact_ref",
            name="uq_saved_market_artifacts_user_type_ref",
        ),
    )
    op.create_index(
        "ix_saved_market_artifacts_artifact_type",
        "saved_market_artifacts",
        ["artifact_type"],
    )
    op.create_index(
        "ix_saved_market_artifacts_user_id",
        "saved_market_artifacts",
        ["user_id"],
    )
    op.create_index(
        "ix_saved_market_artifacts_user_type",
        "saved_market_artifacts",
        ["user_id", "artifact_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_saved_market_artifacts_user_type",
        table_name="saved_market_artifacts",
    )
    op.drop_index(
        "ix_saved_market_artifacts_user_id",
        table_name="saved_market_artifacts",
    )
    op.drop_index(
        "ix_saved_market_artifacts_artifact_type",
        table_name="saved_market_artifacts",
    )
    op.drop_table("saved_market_artifacts")
    op.drop_table("user_preference_profiles")

