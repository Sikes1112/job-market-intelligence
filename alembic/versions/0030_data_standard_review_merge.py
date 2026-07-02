"""Add Layer 28 data standard review and merge controls.

Revision ID: 0030_data_standard_review_merge
Revises: 0029_data_standards_partner_submissions
Create Date: 2026-07-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0030_data_standard_review_merge"
down_revision = "0029_data_standards_partner_submissions"
branch_labels = None
depends_on = None

CANDIDATE_FACT_STATE_SQL = (
    "'pending_review', "
    "'approved_for_merge', "
    "'rejected', "
    "'needs_correction', "
    "'conflict', "
    "'duplicate', "
    "'low_confidence', "
    "'escalated', "
    "'merged'"
)
CANDIDATE_REVIEW_DECISION_SQL = (
    "'approve_candidate', "
    "'reject_candidate', "
    "'request_changes', "
    "'mark_duplicate', "
    "'mark_low_confidence', "
    "'escalate', "
    "'merge_to_canonical', "
    "'resolve_conflicts', "
    "'approve_for_merge', "
    "'reject', "
    "'request_correction', "
    "'mark_conflict'"
)
CANDIDATE_TARGET_TYPE_SQL = (
    "'company', "
    "'region', "
    "'company_region_presence', "
    "'company_region_hiring', "
    "'unsupported'"
)
PARTNER_RECORD_TYPE_SQL = (
    "'company', "
    "'region', "
    "'early_career_program', "
    "'hiring_signal', "
    "'company_region_presence'"
)
CANONICAL_MERGE_ACTION_SQL = "'create', 'noop'"
CANONICAL_MERGE_STATUS_SQL = "'preview_ready', 'blocked', 'merged'"
SUBMISSION_REVIEW_LIFECYCLE_STATE_SQL = (
    "'submitted', "
    "'validation_failed', "
    "'validation_passed', "
    "'under_review', "
    "'needs_changes', "
    "'accepted_as_candidate', "
    "'rejected', "
    "'merged', "
    "'superseded', "
    "'withdrawn'"
)


def upgrade() -> None:
    op.add_column(
        "data_standard_partner_submissions",
        sa.Column(
            "review_lifecycle_state",
            sa.String(length=32),
            nullable=False,
            server_default="validation_passed",
        ),
    )
    op.add_column(
        "data_standard_partner_submissions",
        sa.Column(
            "review_state_history_json",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
    )
    op.create_index(
        "ix_data_standard_partner_submissions_review_state",
        "data_standard_partner_submissions",
        ["review_lifecycle_state"],
    )
    op.create_table(
        "data_standard_candidate_facts",
        sa.Column("candidate_fact_id", sa.String(length=128), nullable=False),
        sa.Column("partner_submission_id", sa.String(length=128), nullable=False),
        sa.Column("partner_id", sa.String(length=128), nullable=False),
        sa.Column("partner_name", sa.String(length=255), nullable=True),
        sa.Column("partner_type", sa.String(length=64), nullable=True),
        sa.Column("partner_verification_status", sa.String(length=64), nullable=False),
        sa.Column("partner_trust_tier", sa.String(length=64), nullable=False),
        sa.Column("submitter_type", sa.String(length=64), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_id", sa.String(length=128), nullable=False),
        sa.Column("record_type", sa.String(length=64), nullable=False),
        sa.Column("candidate_state", sa.String(length=32), nullable=False),
        sa.Column("canonical_target_type", sa.String(length=64), nullable=False),
        sa.Column("canonical_target_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_target_key_json", sa.JSON(), nullable=False),
        sa.Column("fact_payload_json", sa.JSON(), nullable=False),
        sa.Column("source_refs_json", sa.JSON(), nullable=False),
        sa.Column("freshness_json", sa.JSON(), nullable=False),
        sa.Column("confidence_json", sa.JSON(), nullable=False),
        sa.Column("provenance_complete", sa.Boolean(), nullable=False),
        sa.Column("provenance_warnings_json", sa.JSON(), nullable=False),
        sa.Column("raw_record_json", sa.JSON(), nullable=False),
        sa.Column("ranking_influence_allowed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"candidate_state IN ({CANDIDATE_FACT_STATE_SQL})",
            name="ck_data_standard_candidate_facts_state",
        ),
        sa.CheckConstraint(
            f"record_type IN ({PARTNER_RECORD_TYPE_SQL})",
            name="ck_data_standard_candidate_facts_record_type",
        ),
        sa.CheckConstraint(
            f"canonical_target_type IN ({CANDIDATE_TARGET_TYPE_SQL})",
            name="ck_data_standard_candidate_facts_target_type",
        ),
        sa.CheckConstraint(
            "ranking_influence_allowed = false",
            name="ck_data_standard_candidate_facts_no_ranking_influence",
        ),
        sa.ForeignKeyConstraint(
            ["partner_submission_id"],
            ["data_standard_partner_submissions.partner_submission_id"],
        ),
        sa.PrimaryKeyConstraint("candidate_fact_id"),
        sa.UniqueConstraint(
            "partner_submission_id",
            "record_id",
            name="uq_data_standard_candidate_facts_submission_record",
        ),
    )
    op.create_index(
        "ix_data_standard_candidate_facts_created_at",
        "data_standard_candidate_facts",
        ["created_at"],
    )
    op.create_index(
        "ix_data_standard_candidate_facts_partner",
        "data_standard_candidate_facts",
        ["partner_id"],
    )
    op.create_index(
        "ix_data_standard_candidate_facts_state",
        "data_standard_candidate_facts",
        ["candidate_state"],
    )
    op.create_index(
        "ix_data_standard_candidate_facts_submission",
        "data_standard_candidate_facts",
        ["partner_submission_id"],
    )
    op.create_index(
        "ix_data_standard_candidate_facts_target",
        "data_standard_candidate_facts",
        ["canonical_target_type"],
    )
    op.create_index(
        "ix_data_standard_candidate_facts_target_id",
        "data_standard_candidate_facts",
        ["canonical_target_type", "canonical_target_id"],
    )

    op.create_table(
        "data_standard_candidate_reviews",
        sa.Column("candidate_review_id", sa.String(length=128), nullable=False),
        sa.Column("candidate_fact_id", sa.String(length=128), nullable=False),
        sa.Column("partner_submission_id", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=64), nullable=False),
        sa.Column("resulting_candidate_state", sa.String(length=32), nullable=False),
        sa.Column("reviewer_id", sa.String(length=128), nullable=False),
        sa.Column("reviewer_name", sa.String(length=255), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column("reason", sa.String(length=2048), nullable=False),
        sa.Column("decision_notes", sa.Text(), nullable=False),
        sa.Column("source_basis_json", sa.JSON(), nullable=False),
        sa.Column("before_after_diff_json", sa.JSON(), nullable=False),
        sa.Column("resolved_conflict_codes_json", sa.JSON(), nullable=False),
        sa.Column("audit_event_id", sa.String(length=64), nullable=False),
        sa.Column("provenance_complete", sa.Boolean(), nullable=False),
        sa.Column("provenance_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("ranking_influence_allowed", sa.Boolean(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"decision IN ({CANDIDATE_REVIEW_DECISION_SQL})",
            name="ck_data_standard_candidate_reviews_decision",
        ),
        sa.CheckConstraint(
            f"resulting_candidate_state IN ({CANDIDATE_FACT_STATE_SQL})",
            name="ck_data_standard_candidate_reviews_state",
        ),
        sa.CheckConstraint(
            "ranking_influence_allowed = false",
            name="ck_data_standard_candidate_reviews_no_ranking_influence",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_fact_id"],
            ["data_standard_candidate_facts.candidate_fact_id"],
        ),
        sa.ForeignKeyConstraint(
            ["partner_submission_id"],
            ["data_standard_partner_submissions.partner_submission_id"],
        ),
        sa.ForeignKeyConstraint(
            ["audit_event_id"],
            ["admin_event_logs.admin_event_id"],
        ),
        sa.PrimaryKeyConstraint("candidate_review_id"),
    )
    op.create_index(
        "ix_data_standard_candidate_reviews_audit_event",
        "data_standard_candidate_reviews",
        ["audit_event_id"],
    )
    op.create_index(
        "ix_data_standard_candidate_reviews_candidate",
        "data_standard_candidate_reviews",
        ["candidate_fact_id"],
    )
    op.create_index(
        "ix_data_standard_candidate_reviews_created_at",
        "data_standard_candidate_reviews",
        ["created_at"],
    )
    op.create_index(
        "ix_data_standard_candidate_reviews_decision",
        "data_standard_candidate_reviews",
        ["decision"],
    )
    op.create_index(
        "ix_data_standard_candidate_reviews_reviewed_at",
        "data_standard_candidate_reviews",
        ["reviewed_at"],
    )
    op.create_index(
        "ix_data_standard_candidate_reviews_submission",
        "data_standard_candidate_reviews",
        ["partner_submission_id"],
    )

    op.create_table(
        "data_standard_canonical_merges",
        sa.Column("merge_record_id", sa.String(length=128), nullable=False),
        sa.Column("candidate_fact_id", sa.String(length=128), nullable=False),
        sa.Column("partner_submission_id", sa.String(length=128), nullable=False),
        sa.Column("review_decision_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_target_type", sa.String(length=64), nullable=False),
        sa.Column("canonical_target_id", sa.String(length=128), nullable=False),
        sa.Column("merge_action", sa.String(length=32), nullable=False),
        sa.Column("merge_status", sa.String(length=32), nullable=False),
        sa.Column("conflict_detected", sa.Boolean(), nullable=False),
        sa.Column("conflicts_json", sa.JSON(), nullable=False),
        sa.Column("canonical_before_json", sa.JSON(), nullable=True),
        sa.Column("canonical_after_json", sa.JSON(), nullable=False),
        sa.Column("provenance_binding_json", sa.JSON(), nullable=False),
        sa.Column("invalidation_json", sa.JSON(), nullable=False),
        sa.Column("stale_output_ids_json", sa.JSON(), nullable=False),
        sa.Column("audit_event_id", sa.String(length=64), nullable=False),
        sa.Column("ranking_influence_allowed", sa.Boolean(), nullable=False),
        sa.Column("merged_by", sa.String(length=128), nullable=False),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"canonical_target_type IN ({CANDIDATE_TARGET_TYPE_SQL})",
            name="ck_data_standard_canonical_merges_target_type",
        ),
        sa.CheckConstraint(
            f"merge_action IN ({CANONICAL_MERGE_ACTION_SQL})",
            name="ck_data_standard_canonical_merges_action",
        ),
        sa.CheckConstraint(
            f"merge_status IN ({CANONICAL_MERGE_STATUS_SQL})",
            name="ck_data_standard_canonical_merges_status",
        ),
        sa.CheckConstraint(
            "ranking_influence_allowed = false",
            name="ck_data_standard_canonical_merges_no_ranking_influence",
        ),
        sa.ForeignKeyConstraint(
            ["audit_event_id"],
            ["admin_event_logs.admin_event_id"],
        ),
        sa.ForeignKeyConstraint(
            ["candidate_fact_id"],
            ["data_standard_candidate_facts.candidate_fact_id"],
        ),
        sa.ForeignKeyConstraint(
            ["partner_submission_id"],
            ["data_standard_partner_submissions.partner_submission_id"],
        ),
        sa.ForeignKeyConstraint(
            ["review_decision_id"],
            ["data_standard_candidate_reviews.candidate_review_id"],
        ),
        sa.PrimaryKeyConstraint("merge_record_id"),
        sa.UniqueConstraint(
            "candidate_fact_id",
            name="uq_data_standard_canonical_merges_candidate",
        ),
    )
    op.create_index(
        "ix_data_standard_canonical_merges_audit_event",
        "data_standard_canonical_merges",
        ["audit_event_id"],
    )
    op.create_index(
        "ix_data_standard_canonical_merges_candidate",
        "data_standard_canonical_merges",
        ["candidate_fact_id"],
    )
    op.create_index(
        "ix_data_standard_canonical_merges_review_decision",
        "data_standard_canonical_merges",
        ["review_decision_id"],
    )
    op.create_index(
        "ix_data_standard_canonical_merges_created_at",
        "data_standard_canonical_merges",
        ["created_at"],
    )
    op.create_index(
        "ix_data_standard_canonical_merges_merged_at",
        "data_standard_canonical_merges",
        ["merged_at"],
    )
    op.create_index(
        "ix_data_standard_canonical_merges_submission",
        "data_standard_canonical_merges",
        ["partner_submission_id"],
    )
    op.create_index(
        "ix_data_standard_canonical_merges_target",
        "data_standard_canonical_merges",
        ["canonical_target_type", "canonical_target_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_standard_canonical_merges_target",
        table_name="data_standard_canonical_merges",
    )
    op.drop_index(
        "ix_data_standard_canonical_merges_submission",
        table_name="data_standard_canonical_merges",
    )
    op.drop_index(
        "ix_data_standard_canonical_merges_merged_at",
        table_name="data_standard_canonical_merges",
    )
    op.drop_index(
        "ix_data_standard_canonical_merges_created_at",
        table_name="data_standard_canonical_merges",
    )
    op.drop_index(
        "ix_data_standard_canonical_merges_candidate",
        table_name="data_standard_canonical_merges",
    )
    op.drop_index(
        "ix_data_standard_canonical_merges_review_decision",
        table_name="data_standard_canonical_merges",
    )
    op.drop_index(
        "ix_data_standard_canonical_merges_audit_event",
        table_name="data_standard_canonical_merges",
    )
    op.drop_table("data_standard_canonical_merges")

    op.drop_index(
        "ix_data_standard_candidate_reviews_submission",
        table_name="data_standard_candidate_reviews",
    )
    op.drop_index(
        "ix_data_standard_candidate_reviews_reviewed_at",
        table_name="data_standard_candidate_reviews",
    )
    op.drop_index(
        "ix_data_standard_candidate_reviews_decision",
        table_name="data_standard_candidate_reviews",
    )
    op.drop_index(
        "ix_data_standard_candidate_reviews_created_at",
        table_name="data_standard_candidate_reviews",
    )
    op.drop_index(
        "ix_data_standard_candidate_reviews_candidate",
        table_name="data_standard_candidate_reviews",
    )
    op.drop_index(
        "ix_data_standard_candidate_reviews_audit_event",
        table_name="data_standard_candidate_reviews",
    )
    op.drop_table("data_standard_candidate_reviews")

    op.drop_index(
        "ix_data_standard_candidate_facts_target_id",
        table_name="data_standard_candidate_facts",
    )
    op.drop_index(
        "ix_data_standard_candidate_facts_target",
        table_name="data_standard_candidate_facts",
    )
    op.drop_index(
        "ix_data_standard_candidate_facts_submission",
        table_name="data_standard_candidate_facts",
    )
    op.drop_index(
        "ix_data_standard_candidate_facts_state",
        table_name="data_standard_candidate_facts",
    )
    op.drop_index(
        "ix_data_standard_candidate_facts_partner",
        table_name="data_standard_candidate_facts",
    )
    op.drop_index(
        "ix_data_standard_candidate_facts_created_at",
        table_name="data_standard_candidate_facts",
    )
    op.drop_table("data_standard_candidate_facts")
    op.drop_index(
        "ix_data_standard_partner_submissions_review_state",
        table_name="data_standard_partner_submissions",
    )
    op.drop_column("data_standard_partner_submissions", "review_state_history_json")
    op.drop_column("data_standard_partner_submissions", "review_lifecycle_state")
