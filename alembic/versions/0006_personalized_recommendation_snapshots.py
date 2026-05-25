"""Add personalized recommendation snapshots.

Revision ID: 0006_rec_snapshots
Revises: 0005_saved_preferences_markets
Create Date: 2026-05-21
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_rec_snapshots"
down_revision = "0005_saved_preferences_markets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "personalized_recommendation_snapshots",
        sa.Column("recommendation_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("preference_profile_id", sa.String(length=64), nullable=True),
        sa.Column("personalized_output", sa.JSON(), nullable=False),
        sa.Column("recommendation_version", sa.String(length=64), nullable=False),
        sa.Column("source_version_bundle", sa.JSON(), nullable=False),
        sa.Column("objective_output_refs", sa.JSON(), nullable=False),
        sa.Column("recommendation_inputs_hash", sa.String(length=128), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["preference_profile_id"], ["user_preference_profiles.user_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("recommendation_snapshot_id"),
    )
    op.create_index(
        "ix_rec_snapshots_inputs_hash",
        "personalized_recommendation_snapshots",
        ["recommendation_inputs_hash"],
    )
    op.create_index(
        "ix_rec_snapshots_user_generated_at",
        "personalized_recommendation_snapshots",
        ["user_id", "generated_at"],
    )
    op.create_index(
        "ix_rec_snapshots_user_id",
        "personalized_recommendation_snapshots",
        ["user_id"],
    )
    op.create_index(
        "ix_rec_snapshots_version",
        "personalized_recommendation_snapshots",
        ["recommendation_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rec_snapshots_version",
        table_name="personalized_recommendation_snapshots",
    )
    op.drop_index(
        "ix_rec_snapshots_user_id",
        table_name="personalized_recommendation_snapshots",
    )
    op.drop_index(
        "ix_rec_snapshots_user_generated_at",
        table_name="personalized_recommendation_snapshots",
    )
    op.drop_index(
        "ix_rec_snapshots_inputs_hash",
        table_name="personalized_recommendation_snapshots",
    )
    op.drop_table("personalized_recommendation_snapshots")
