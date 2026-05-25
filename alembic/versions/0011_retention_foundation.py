"""Add retention foundation user-owned controls.

Revision ID: 0011_retention_foundation
Revises: 0010_admin_overrides_repairs
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0011_retention_foundation"
down_revision = "0010_admin_overrides_repairs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_preference_profiles",
        sa.Column("scoring_weights", sa.JSON(), nullable=True),
    )
    with op.batch_alter_table("saved_market_artifacts") as batch_op:
        batch_op.drop_constraint(
            "ck_saved_market_artifacts_artifact_type",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_saved_market_artifacts_artifact_type",
            "artifact_type IN "
            "('region', 'company', 'role_family', 'comparison', 'discovery_result')",
        )


def downgrade() -> None:
    with op.batch_alter_table("saved_market_artifacts") as batch_op:
        batch_op.drop_constraint(
            "ck_saved_market_artifacts_artifact_type",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_saved_market_artifacts_artifact_type",
            "artifact_type IN ('region', 'company', 'comparison', 'discovery_result')",
        )
    op.drop_column("user_preference_profiles", "scoring_weights")

