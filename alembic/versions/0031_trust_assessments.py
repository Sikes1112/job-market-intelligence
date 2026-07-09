"""Add Layer 30A trust assessment snapshots.

Revision ID: 0031_trust_assessments
Revises: 0030_data_standard_review_merge
Create Date: 2026-07-03
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0031_trust_assessments"
down_revision = "0030_data_standard_review_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trust_assessments",
        sa.Column("trust_assessment_id", sa.String(length=128), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("trust_tier", sa.String(length=64), nullable=False),
        sa.Column("assessment_source", sa.String(length=128), nullable=False),
        sa.Column("assessment_version", sa.String(length=64), nullable=False),
        sa.Column("evidence_requirements_met_json", sa.JSON(), nullable=False),
        sa.Column("evidence_requirements_missing_json", sa.JSON(), nullable=False),
        sa.Column("evidence_requirements_failed_json", sa.JSON(), nullable=False),
        sa.Column(
            "evidence_requirements_not_applicable_json",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("ranking_influence_allowed", sa.Boolean(), nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_assessment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("trust_assessment_id"),
        sa.UniqueConstraint(
            "subject_type",
            "subject_id",
            "assessment_version",
            "assessed_at",
            name="uq_trust_assessments_subject_version_time",
        ),
    )
    op.create_index(
        "ix_trust_assessments_subject",
        "trust_assessments",
        ["subject_type", "subject_id"],
    )
    op.create_index(
        "ix_trust_assessments_tier",
        "trust_assessments",
        ["trust_tier"],
    )
    op.create_index(
        "ix_trust_assessments_assessed_at",
        "trust_assessments",
        ["assessed_at"],
    )
    op.create_index(
        "ix_trust_assessments_next_assessment",
        "trust_assessments",
        ["next_assessment_at"],
    )
    op.create_index(
        "ix_trust_assessments_created_at",
        "trust_assessments",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_trust_assessments_created_at", table_name="trust_assessments")
    op.drop_index(
        "ix_trust_assessments_next_assessment",
        table_name="trust_assessments",
    )
    op.drop_index("ix_trust_assessments_assessed_at", table_name="trust_assessments")
    op.drop_index("ix_trust_assessments_tier", table_name="trust_assessments")
    op.drop_index("ix_trust_assessments_subject", table_name="trust_assessments")
    op.drop_table("trust_assessments")
