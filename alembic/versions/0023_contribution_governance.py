"""Add Layer 18D contribution governance.

Revision ID: 0023_contribution_governance
Revises: 0022_benchmark_reports
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0023_contribution_governance"
down_revision = "0022_benchmark_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_contributions",
        sa.Column("data_contribution_id", sa.String(length=64), nullable=False),
        sa.Column("contributor_type", sa.String(length=32), nullable=False),
        sa.Column("contributor_id", sa.String(length=64), nullable=True),
        sa.Column("institution_id", sa.String(length=64), nullable=True),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=True),
        sa.Column("contribution_type", sa.String(length=64), nullable=False),
        sa.Column("structured_payload", sa.JSON(), nullable=False),
        sa.Column("summary", sa.String(length=1024), nullable=False),
        sa.Column("claimed_confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        _contributor_type_check(),
        _contribution_target_type_check(),
        _contribution_type_check(),
        _contribution_status_check(),
        sa.CheckConstraint(
            "claimed_confidence IS NULL OR "
            "(claimed_confidence >= 0.0 AND claimed_confidence <= 1.0)",
            name="ck_data_contributions_claimed_confidence",
        ),
        sa.ForeignKeyConstraint(["institution_id"], ["organizations.organization_id"]),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("data_contribution_id"),
    )
    op.create_index(
        "ix_data_contributions_contributor",
        "data_contributions",
        ["contributor_type", "contributor_id"],
    )
    op.create_index(
        "ix_data_contributions_created_at",
        "data_contributions",
        ["created_at"],
    )
    op.create_index(
        "ix_data_contributions_institution",
        "data_contributions",
        ["institution_id"],
    )
    op.create_index(
        "ix_data_contributions_region",
        "data_contributions",
        ["region_id"],
    )
    op.create_index(
        "ix_data_contributions_status",
        "data_contributions",
        ["status"],
    )
    op.create_index(
        "ix_data_contributions_target",
        "data_contributions",
        ["target_type", "target_id"],
    )
    op.create_index(
        "ix_data_contributions_type",
        "data_contributions",
        ["contribution_type"],
    )

    op.create_table(
        "contribution_evidence",
        sa.Column("contribution_evidence_id", sa.String(length=64), nullable=False),
        sa.Column("contribution_id", sa.String(length=64), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("reference", sa.String(length=512), nullable=True),
        sa.Column("description", sa.String(length=2048), nullable=True),
        sa.Column("uploaded_reference_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evidence_type IN ('url', 'reference', 'description', 'uploaded_reference')",
            name="ck_contribution_evidence_type",
        ),
        sa.ForeignKeyConstraint(
            ["contribution_id"],
            ["data_contributions.data_contribution_id"],
        ),
        sa.PrimaryKeyConstraint("contribution_evidence_id"),
    )
    op.create_index(
        "ix_contribution_evidence_contribution",
        "contribution_evidence",
        ["contribution_id"],
    )
    op.create_index(
        "ix_contribution_evidence_created_at",
        "contribution_evidence",
        ["created_at"],
    )
    op.create_index(
        "ix_contribution_evidence_type",
        "contribution_evidence",
        ["evidence_type"],
    )

    op.create_table(
        "contribution_reviews",
        sa.Column("contribution_review_id", sa.String(length=64), nullable=False),
        sa.Column("contribution_id", sa.String(length=64), nullable=False),
        sa.Column("reviewer_id", sa.String(length=64), nullable=True),
        sa.Column("review_decision", sa.String(length=32), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column(
            "canonical_update_candidate_created",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "canonical_update_candidate_ref",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column("refresh_task_created", sa.Boolean(), nullable=False),
        sa.Column("refresh_task_ref", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "review_decision IN "
            "('needs_review', 'verified', 'rejected', 'merged', 'superseded')",
            name="ck_contribution_reviews_decision",
        ),
        sa.ForeignKeyConstraint(
            ["contribution_id"],
            ["data_contributions.data_contribution_id"],
        ),
        sa.PrimaryKeyConstraint("contribution_review_id"),
    )
    op.create_index(
        "ix_contribution_reviews_contribution",
        "contribution_reviews",
        ["contribution_id"],
    )
    op.create_index(
        "ix_contribution_reviews_created_at",
        "contribution_reviews",
        ["created_at"],
    )
    op.create_index(
        "ix_contribution_reviews_decision",
        "contribution_reviews",
        ["review_decision"],
    )
    op.create_index(
        "ix_contribution_reviews_reviewer",
        "contribution_reviews",
        ["reviewer_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_contribution_reviews_reviewer", table_name="contribution_reviews")
    op.drop_index("ix_contribution_reviews_decision", table_name="contribution_reviews")
    op.drop_index("ix_contribution_reviews_created_at", table_name="contribution_reviews")
    op.drop_index("ix_contribution_reviews_contribution", table_name="contribution_reviews")
    op.drop_table("contribution_reviews")

    op.drop_index("ix_contribution_evidence_type", table_name="contribution_evidence")
    op.drop_index("ix_contribution_evidence_created_at", table_name="contribution_evidence")
    op.drop_index(
        "ix_contribution_evidence_contribution",
        table_name="contribution_evidence",
    )
    op.drop_table("contribution_evidence")

    op.drop_index("ix_data_contributions_type", table_name="data_contributions")
    op.drop_index("ix_data_contributions_target", table_name="data_contributions")
    op.drop_index("ix_data_contributions_status", table_name="data_contributions")
    op.drop_index("ix_data_contributions_region", table_name="data_contributions")
    op.drop_index("ix_data_contributions_institution", table_name="data_contributions")
    op.drop_index("ix_data_contributions_created_at", table_name="data_contributions")
    op.drop_index("ix_data_contributions_contributor", table_name="data_contributions")
    op.drop_table("data_contributions")


def _contributor_type_check() -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "contributor_type IN ('user', 'institution', 'partner', 'admin')",
        name="ck_data_contributions_contributor_type",
    )


def _contribution_target_type_check() -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "target_type IN ("
        "'region', "
        "'company', "
        "'company_region', "
        "'sector_region', "
        "'source', "
        "'market', "
        "'role_family'"
        ")",
        name="ck_data_contributions_target_type",
    )


def _contribution_type_check() -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "contribution_type IN ("
        "'verified_correction', "
        "'company_presence_update', "
        "'regional_employer_list', "
        "'career_center_intelligence', "
        "'internship_program_information', "
        "'role_access_feedback', "
        "'source_suggestion', "
        "'market_quality_feedback', "
        "'outdated_data_report'"
        ")",
        name="ck_data_contributions_type",
    )


def _contribution_status_check() -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "status IN ("
        "'submitted', "
        "'needs_review', "
        "'verified', "
        "'rejected', "
        "'merged', "
        "'superseded'"
        ")",
        name="ck_data_contributions_status",
    )
