"""Add Layer 23B opportunity submission review workflow.

Revision ID: 0026_opportunity_submission_review
Revises: 0025_opportunity_infrastructure
Create Date: 2026-06-24
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0026_opportunity_submission_review"
down_revision = "0025_opportunity_infrastructure"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "opportunity_submissions",
        sa.Column("opportunity_submission_id", sa.String(length=64), nullable=False),
        sa.Column("opportunity_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("submitter_contact", sa.String(length=255), nullable=False),
        sa.Column("submitted_by", sa.String(length=128), nullable=True),
        sa.Column("submission_source", sa.String(length=128), nullable=True),
        sa.Column("partner_organization_id", sa.String(length=64), nullable=True),
        sa.Column("partner_organization_name", sa.String(length=255), nullable=True),
        sa.Column("paid_partner", sa.Boolean(), nullable=False),
        sa.Column("paid_partner_label", sa.String(length=128), nullable=True),
        sa.Column("raw_submission_json", sa.JSON(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ("
            "'expired', "
            "'needs_correction', "
            "'pending_review', "
            "'rejected', "
            "'reviewed'"
            ")",
            name="ck_opportunity_submissions_status",
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.opportunity_id"]),
        sa.PrimaryKeyConstraint("opportunity_submission_id"),
        sa.UniqueConstraint(
            "opportunity_id",
            name="uq_opportunity_submissions_opportunity",
        ),
    )
    op.create_index(
        "ix_opportunity_submissions_created_at",
        "opportunity_submissions",
        ["created_at"],
    )
    op.create_index(
        "ix_opportunity_submissions_opportunity",
        "opportunity_submissions",
        ["opportunity_id"],
    )
    op.create_index(
        "ix_opportunity_submissions_partner",
        "opportunity_submissions",
        ["partner_organization_id"],
    )
    op.create_index(
        "ix_opportunity_submissions_status",
        "opportunity_submissions",
        ["status"],
    )
    op.create_index(
        "ix_opportunity_submissions_submitted_at",
        "opportunity_submissions",
        ["submitted_at"],
    )

    op.create_table(
        "opportunity_review_actions",
        sa.Column("opportunity_review_action_id", sa.String(length=64), nullable=False),
        sa.Column("submission_id", sa.String(length=64), nullable=False),
        sa.Column("opportunity_id", sa.String(length=64), nullable=False),
        sa.Column("review_action", sa.String(length=64), nullable=False),
        sa.Column("resulting_trust_label", sa.String(length=32), nullable=False),
        sa.Column("resulting_review_status", sa.String(length=32), nullable=False),
        sa.Column("ranking_influence_allowed", sa.Boolean(), nullable=False),
        sa.Column("reviewer_id", sa.String(length=128), nullable=False),
        sa.Column("reviewer_name", sa.String(length=255), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column("source_url_checked", sa.String(length=2048), nullable=True),
        sa.Column("official_employer_url", sa.String(length=2048), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "review_action IN ("
            "'approve_as_source_checked', "
            "'approve_as_verified', "
            "'mark_expired', "
            "'mark_unverified', "
            "'reject', "
            "'request_correction'"
            ")",
            name="ck_opportunity_review_actions_action",
        ),
        sa.CheckConstraint(
            "resulting_trust_label IN ("
            "'expired', "
            "'partner_submitted', "
            "'rejected', "
            "'source_checked', "
            "'unverified', "
            "'verified'"
            ")",
            name="ck_opportunity_review_actions_trust_label",
        ),
        sa.CheckConstraint(
            "resulting_review_status IN ("
            "'approved', "
            "'expired', "
            "'needs_correction', "
            "'pending_review', "
            "'rejected', "
            "'source_checked'"
            ")",
            name="ck_opportunity_review_actions_review_status",
        ),
        sa.CheckConstraint(
            "ranking_influence_allowed = false",
            name="ck_opportunity_review_actions_no_ranking_influence",
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.opportunity_id"]),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["opportunity_submissions.opportunity_submission_id"],
        ),
        sa.PrimaryKeyConstraint("opportunity_review_action_id"),
    )
    op.create_index(
        "ix_opportunity_review_actions_action",
        "opportunity_review_actions",
        ["review_action"],
    )
    op.create_index(
        "ix_opportunity_review_actions_created_at",
        "opportunity_review_actions",
        ["created_at"],
    )
    op.create_index(
        "ix_opportunity_review_actions_opportunity",
        "opportunity_review_actions",
        ["opportunity_id"],
    )
    op.create_index(
        "ix_opportunity_review_actions_reviewed_at",
        "opportunity_review_actions",
        ["reviewed_at"],
    )
    op.create_index(
        "ix_opportunity_review_actions_submission",
        "opportunity_review_actions",
        ["submission_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_opportunity_review_actions_submission",
        table_name="opportunity_review_actions",
    )
    op.drop_index(
        "ix_opportunity_review_actions_reviewed_at",
        table_name="opportunity_review_actions",
    )
    op.drop_index(
        "ix_opportunity_review_actions_opportunity",
        table_name="opportunity_review_actions",
    )
    op.drop_index(
        "ix_opportunity_review_actions_created_at",
        table_name="opportunity_review_actions",
    )
    op.drop_index(
        "ix_opportunity_review_actions_action",
        table_name="opportunity_review_actions",
    )
    op.drop_table("opportunity_review_actions")

    op.drop_index(
        "ix_opportunity_submissions_submitted_at",
        table_name="opportunity_submissions",
    )
    op.drop_index(
        "ix_opportunity_submissions_status",
        table_name="opportunity_submissions",
    )
    op.drop_index(
        "ix_opportunity_submissions_partner",
        table_name="opportunity_submissions",
    )
    op.drop_index(
        "ix_opportunity_submissions_opportunity",
        table_name="opportunity_submissions",
    )
    op.drop_index(
        "ix_opportunity_submissions_created_at",
        table_name="opportunity_submissions",
    )
    op.drop_table("opportunity_submissions")
