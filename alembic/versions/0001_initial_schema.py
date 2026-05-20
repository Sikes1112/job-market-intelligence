"""Initial canonical schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("company_id", sa.String(length=64), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_company_name", sa.String(length=255), nullable=False),
        sa.Column("sector_primary", sa.String(length=64), nullable=True),
        sa.Column("sector_secondary", sa.String(length=64), nullable=True),
        sa.Column("public_or_private", sa.String(length=32), nullable=True),
        sa.Column("eligibility_status", sa.String(length=32), nullable=False),
        sa.Column("eligibility_score", sa.Float(), nullable=True),
        sa.Column("eligibility_override_flag", sa.Boolean(), nullable=False),
        sa.Column("eligibility_override_reason", sa.String(length=512), nullable=True),
        sa.Column("classification_confidence", sa.String(length=32), nullable=True),
        sa.Column("is_major_tech", sa.Boolean(), nullable=False),
        sa.Column("major_tech_score", sa.Float(), nullable=True),
        sa.Column("is_mag7", sa.Boolean(), nullable=False),
        sa.Column("prestige_score", sa.Float(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("company_id"),
    )
    op.create_index("ix_companies_eligibility_status", "companies", ["eligibility_status"])
    op.create_index("ix_companies_is_mag7", "companies", ["is_mag7"])
    op.create_index("ix_companies_is_major_tech", "companies", ["is_major_tech"])
    op.create_index("ix_companies_normalized_name", "companies", ["normalized_company_name"])
    op.create_index("ix_companies_sector_primary", "companies", ["sector_primary"])

    op.create_table(
        "jobs",
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("queue_name", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("trigger_type", sa.String(length=32), nullable=True),
        sa.Column("requested_by", sa.String(length=128), nullable=True),
        sa.Column("scope", sa.JSON(), nullable=True),
        sa.Column("scope_hash", sa.String(length=128), nullable=True),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("inputs", sa.JSON(), nullable=True),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("dependency_refs", sa.JSON(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("input_hash", sa.String(length=128), nullable=True),
        sa.Column("output_hash", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=2048), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index("ix_jobs_dedupe_key", "jobs", ["dedupe_key"])
    op.create_index("ix_jobs_job_type", "jobs", ["job_type"])
    op.create_index("ix_jobs_priority", "jobs", ["priority"])
    op.create_index("ix_jobs_queue_name", "jobs", ["queue_name"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index(
        "uq_jobs_active_dedupe_key",
        "jobs",
        ["dedupe_key"],
        unique=True,
        sqlite_where=sa.text("dedupe_key IS NOT NULL AND status IN ('queued', 'running')"),
        postgresql_where=sa.text("dedupe_key IS NOT NULL AND status IN ('queued', 'running')"),
    )

    op.create_table(
        "output_metadata",
        sa.Column("output_id", sa.String(length=64), nullable=False),
        sa.Column("output_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_uri", sa.String(length=1024), nullable=True),
        sa.Column("artifact_hash", sa.String(length=128), nullable=True),
        sa.Column("source_version_bundle", sa.JSON(), nullable=True),
        sa.Column("freshness_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("output_id"),
        sa.UniqueConstraint("output_type", "subject_id", name="uq_output_type_subject"),
    )
    op.create_index("ix_output_metadata_state", "output_metadata", ["state"])
    op.create_index("ix_output_metadata_subject", "output_metadata", ["subject_id"])
    op.create_index("ix_output_metadata_type", "output_metadata", ["output_type"])

    op.create_table(
        "regions",
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("region_name", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("region_type", sa.String(length=32), nullable=False),
        sa.Column("parent_region_id", sa.String(length=64), nullable=True),
        sa.Column("labor_market_group", sa.String(length=64), nullable=True),
        sa.Column("normalization_profile_id", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("region_id"),
    )
    op.create_index("ix_regions_labor_market_group", "regions", ["labor_market_group"])
    op.create_index("ix_regions_parent_region_id", "regions", ["parent_region_id"])
    op.create_index("ix_regions_region_type", "regions", ["region_type"])

    op.create_table(
        "company_region_entry_level",
        sa.Column("entry_level_id", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.String(length=64), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("internship_count", sa.Integer(), nullable=True),
        sa.Column("coop_count", sa.Integer(), nullable=True),
        sa.Column("entry_level_full_time_count", sa.Integer(), nullable=True),
        sa.Column("formal_early_career_program_flag", sa.Boolean(), nullable=False),
        sa.Column("student_season_recurrence_signal", sa.String(length=32), nullable=True),
        sa.Column("entry_level_access_score", sa.Float(), nullable=True),
        sa.Column("entry_level_confidence", sa.String(length=32), nullable=True),
        sa.Column("freshness_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_refs", sa.JSON(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"]),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("entry_level_id"),
        sa.UniqueConstraint("company_id", "region_id", name="uq_entry_level_company_region"),
    )
    op.create_index("ix_entry_level_company_id", "company_region_entry_level", ["company_id"])
    op.create_index(
        "ix_entry_level_region_coop",
        "company_region_entry_level",
        ["region_id", "coop_count"],
    )
    op.create_index("ix_entry_level_region_id", "company_region_entry_level", ["region_id"])
    op.create_index(
        "ix_entry_level_region_internship",
        "company_region_entry_level",
        ["region_id", "internship_count"],
    )
    op.create_index(
        "ix_entry_level_region_score",
        "company_region_entry_level",
        ["region_id", "entry_level_access_score"],
    )

    op.create_table(
        "company_region_hiring",
        sa.Column("hiring_id", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.String(length=64), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("currently_hiring_flag", sa.Boolean(), nullable=False),
        sa.Column("active_posting_count_now", sa.Integer(), nullable=True),
        sa.Column("posting_count_30d", sa.Integer(), nullable=True),
        sa.Column("posting_count_90d", sa.Integer(), nullable=True),
        sa.Column("annualized_trend_signal", sa.String(length=32), nullable=True),
        sa.Column("seasonal_student_hiring_signal", sa.String(length=32), nullable=True),
        sa.Column("hiring_program_count", sa.Integer(), nullable=True),
        sa.Column("role_family_summary", sa.JSON(), nullable=True),
        sa.Column("hiring_confidence", sa.String(length=32), nullable=True),
        sa.Column("freshness_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_refs", sa.JSON(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"]),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("hiring_id"),
        sa.UniqueConstraint("company_id", "region_id", name="uq_hiring_company_region"),
    )
    op.create_index("ix_hiring_company_id", "company_region_hiring", ["company_id"])
    op.create_index(
        "ix_hiring_currently_hiring",
        "company_region_hiring",
        ["currently_hiring_flag"],
    )
    op.create_index(
        "ix_hiring_region_active_now",
        "company_region_hiring",
        ["region_id", "active_posting_count_now"],
    )
    op.create_index(
        "ix_hiring_region_currently_hiring",
        "company_region_hiring",
        ["region_id", "currently_hiring_flag"],
    )
    op.create_index("ix_hiring_region_id", "company_region_hiring", ["region_id"])

    op.create_table(
        "company_region_presence",
        sa.Column("presence_id", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.String(length=64), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("presence_status", sa.String(length=32), nullable=False),
        sa.Column("presence_basis", sa.String(length=64), nullable=True),
        sa.Column("office_evidence_flag", sa.Boolean(), nullable=False),
        sa.Column("operations_evidence_flag", sa.Boolean(), nullable=False),
        sa.Column("hiring_evidence_flag", sa.Boolean(), nullable=False),
        sa.Column("presence_confidence", sa.String(length=32), nullable=True),
        sa.Column("source_refs", sa.JSON(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"]),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("presence_id"),
        sa.UniqueConstraint("company_id", "region_id", name="uq_presence_company_region"),
    )
    op.create_index("ix_presence_company_id", "company_region_presence", ["company_id"])
    op.create_index("ix_presence_region_id", "company_region_presence", ["region_id"])
    op.create_index(
        "ix_presence_region_status",
        "company_region_presence",
        ["region_id", "presence_status"],
    )
    op.create_index("ix_presence_status", "company_region_presence", ["presence_status"])

    op.create_table(
        "region_market_scores",
        sa.Column("region_score_id", sa.String(length=64), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("structural_ecosystem_score", sa.Float(), nullable=True),
        sa.Column("live_market_score", sa.Float(), nullable=True),
        sa.Column("objective_opportunity_score", sa.Float(), nullable=True),
        sa.Column("raw_total_score", sa.Float(), nullable=True),
        sa.Column("general_density_score", sa.Float(), nullable=True),
        sa.Column("tech_market_density_score", sa.Float(), nullable=True),
        sa.Column("early_career_accessibility_score", sa.Float(), nullable=True),
        sa.Column("score_ruleset_version", sa.String(length=64), nullable=True),
        sa.Column("normalization_profile_id", sa.String(length=64), nullable=True),
        sa.Column("source_version_bundle", sa.JSON(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("region_score_id"),
        sa.UniqueConstraint("region_id", name="uq_region_market_scores_region"),
    )
    op.create_index(
        "ix_region_scores_early_career",
        "region_market_scores",
        ["early_career_accessibility_score"],
    )
    op.create_index(
        "ix_region_scores_objective",
        "region_market_scores",
        ["objective_opportunity_score"],
    )
    op.create_index("ix_region_scores_region_id", "region_market_scores", ["region_id"])


def downgrade() -> None:
    op.drop_index("ix_region_scores_region_id", table_name="region_market_scores")
    op.drop_index("ix_region_scores_objective", table_name="region_market_scores")
    op.drop_index("ix_region_scores_early_career", table_name="region_market_scores")
    op.drop_table("region_market_scores")

    op.drop_index("ix_presence_status", table_name="company_region_presence")
    op.drop_index("ix_presence_region_status", table_name="company_region_presence")
    op.drop_index("ix_presence_region_id", table_name="company_region_presence")
    op.drop_index("ix_presence_company_id", table_name="company_region_presence")
    op.drop_table("company_region_presence")

    op.drop_index("ix_hiring_region_id", table_name="company_region_hiring")
    op.drop_index("ix_hiring_region_currently_hiring", table_name="company_region_hiring")
    op.drop_index("ix_hiring_region_active_now", table_name="company_region_hiring")
    op.drop_index("ix_hiring_currently_hiring", table_name="company_region_hiring")
    op.drop_index("ix_hiring_company_id", table_name="company_region_hiring")
    op.drop_table("company_region_hiring")

    op.drop_index("ix_entry_level_region_score", table_name="company_region_entry_level")
    op.drop_index("ix_entry_level_region_internship", table_name="company_region_entry_level")
    op.drop_index("ix_entry_level_region_id", table_name="company_region_entry_level")
    op.drop_index("ix_entry_level_region_coop", table_name="company_region_entry_level")
    op.drop_index("ix_entry_level_company_id", table_name="company_region_entry_level")
    op.drop_table("company_region_entry_level")

    op.drop_index("ix_regions_region_type", table_name="regions")
    op.drop_index("ix_regions_parent_region_id", table_name="regions")
    op.drop_index("ix_regions_labor_market_group", table_name="regions")
    op.drop_table("regions")

    op.drop_index("ix_output_metadata_type", table_name="output_metadata")
    op.drop_index("ix_output_metadata_subject", table_name="output_metadata")
    op.drop_index("ix_output_metadata_state", table_name="output_metadata")
    op.drop_table("output_metadata")

    op.drop_index("uq_jobs_active_dedupe_key", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_queue_name", table_name="jobs")
    op.drop_index("ix_jobs_priority", table_name="jobs")
    op.drop_index("ix_jobs_job_type", table_name="jobs")
    op.drop_index("ix_jobs_dedupe_key", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("ix_companies_sector_primary", table_name="companies")
    op.drop_index("ix_companies_normalized_name", table_name="companies")
    op.drop_index("ix_companies_is_major_tech", table_name="companies")
    op.drop_index("ix_companies_is_mag7", table_name="companies")
    op.drop_index("ix_companies_eligibility_status", table_name="companies")
    op.drop_table("companies")
