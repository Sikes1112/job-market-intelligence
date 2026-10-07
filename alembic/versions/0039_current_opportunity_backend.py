"""Add Layer 38A current opportunity backend.

Revision ID: 0039_current_opportunity_backend
Revises: 0038_deep_decision_intelligence
Create Date: 2026-09-02
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0039_current_opportunity_backend"
down_revision = "0038_deep_decision_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "opportunity_data_sources",
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("acquisition_method", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("allowed_use", sa.String(length=64), nullable=False),
        sa.Column("license_terms", sa.String(length=64), nullable=False),
        sa.Column("trust_classification", sa.String(length=32), nullable=False),
        sa.Column("freshness_sla_hours", sa.Integer(), nullable=False),
        sa.Column("supported_domains", sa.JSON(), nullable=False),
        sa.Column("supported_markets", sa.JSON(), nullable=False),
        sa.Column("supported_opportunity_types", sa.JSON(), nullable=False),
        sa.Column("retention_classification", sa.String(length=64), nullable=True),
        sa.Column("ranking_use_allowed", sa.Boolean(), nullable=False),
        sa.Column("display_use_allowed", sa.Boolean(), nullable=False),
        sa.Column("refresh_config", sa.JSON(), nullable=False),
        sa.Column("provenance_requirements", sa.JSON(), nullable=False),
        sa.Column("operational_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index("ix_opportunity_data_sources_enabled", "opportunity_data_sources", ["enabled"])
    op.create_index(
        "ix_opportunity_data_sources_operational_status",
        "opportunity_data_sources",
        ["operational_status"],
    )
    op.create_index(
        "ix_opportunity_data_sources_provider", "opportunity_data_sources", ["provider"]
    )
    op.create_index(
        "ix_opportunity_data_sources_ranking",
        "opportunity_data_sources",
        ["ranking_use_allowed"],
    )

    op.create_table(
        "current_opportunities",
        sa.Column("current_opportunity_id", sa.String(length=64), nullable=False),
        sa.Column("canonical_identity_key", sa.String(length=255), nullable=False),
        sa.Column("duplicate_group_key", sa.String(length=255), nullable=False),
        sa.Column("company_id", sa.String(length=64), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("original_title", sa.String(length=255), nullable=False),
        sa.Column("normalized_title", sa.String(length=255), nullable=False),
        sa.Column("role_family", sa.String(length=64), nullable=False),
        sa.Column("seniority_level", sa.String(length=64), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=True),
        sa.Column("market_label", sa.String(length=128), nullable=True),
        sa.Column("location_text", sa.String(length=255), nullable=True),
        sa.Column("work_arrangement", sa.String(length=32), nullable=False),
        sa.Column("compensation_min", sa.Float(), nullable=True),
        sa.Column("compensation_max", sa.Float(), nullable=True),
        sa.Column("compensation_currency", sa.String(length=3), nullable=True),
        sa.Column("compensation_interval", sa.String(length=32), nullable=False),
        sa.Column("employment_type", sa.String(length=32), nullable=False),
        sa.Column("opportunity_type", sa.String(length=64), nullable=False),
        sa.Column("posting_date", sa.Date(), nullable=True),
        sa.Column("closing_date", sa.Date(), nullable=True),
        sa.Column("application_url", sa.String(length=2048), nullable=True),
        sa.Column("application_host", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=True),
        sa.Column("skills", sa.JSON(), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("source_values", sa.JSON(), nullable=False),
        sa.Column("normalization_confidence", sa.String(length=32), nullable=False),
        sa.Column("identity_confidence", sa.String(length=32), nullable=False),
        sa.Column("canonical_status", sa.String(length=32), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canonical_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_state", sa.String(length=32), nullable=False),
        sa.Column("ranking_eligible", sa.Boolean(), nullable=False),
        sa.Column("ranking_ineligible_reasons", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"]),
        sa.ForeignKeyConstraint(["market_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("current_opportunity_id"),
        sa.UniqueConstraint("canonical_identity_key", name="uq_current_opportunities_identity_key"),
    )
    op.create_index("ix_current_opportunities_company", "current_opportunities", ["company_id"])
    op.create_index(
        "ix_current_opportunities_company_name",
        "current_opportunities",
        ["company_name"],
    )
    op.create_index(
        "ix_current_opportunities_duplicate_group",
        "current_opportunities",
        ["duplicate_group_key"],
    )
    op.create_index(
        "ix_current_opportunities_freshness",
        "current_opportunities",
        ["freshness_state"],
    )
    op.create_index(
        "ix_current_opportunities_last_observed",
        "current_opportunities",
        ["last_observed_at"],
    )
    op.create_index("ix_current_opportunities_market", "current_opportunities", ["market_id"])
    op.create_index(
        "ix_current_opportunities_ranking",
        "current_opportunities",
        ["ranking_eligible"],
    )
    op.create_index(
        "ix_current_opportunities_role_family",
        "current_opportunities",
        ["role_family"],
    )
    op.create_index(
        "ix_current_opportunities_status", "current_opportunities", ["canonical_status"]
    )

    op.create_table(
        "opportunity_coverage_contracts",
        sa.Column("coverage_id", sa.String(length=64), nullable=False),
        sa.Column("market_key", sa.String(length=128), nullable=False),
        sa.Column("market_id", sa.String(length=64), nullable=True),
        sa.Column("market_label", sa.String(length=128), nullable=True),
        sa.Column("role_family", sa.String(length=64), nullable=False),
        sa.Column("opportunity_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("source_basis", sa.JSON(), nullable=False),
        sa.Column("minimum_expected_sources", sa.Integer(), nullable=False),
        sa.Column("freshness_max_age_hours", sa.Integer(), nullable=True),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operator_override_status", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("coverage_id"),
        sa.UniqueConstraint(
            "market_key", "role_family", "opportunity_type", name="uq_opportunity_coverage_scope"
        ),
    )
    op.create_index(
        "ix_opportunity_coverage_market", "opportunity_coverage_contracts", ["market_key"]
    )
    op.create_index(
        "ix_opportunity_coverage_role", "opportunity_coverage_contracts", ["role_family"]
    )
    op.create_index("ix_opportunity_coverage_status", "opportunity_coverage_contracts", ["status"])
    op.create_index(
        "ix_opportunity_coverage_type", "opportunity_coverage_contracts", ["opportunity_type"]
    )

    op.create_table(
        "opportunity_acquisition_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trigger_type", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor", sa.String(length=512), nullable=True),
        sa.Column("checkpoint", sa.JSON(), nullable=True),
        sa.Column("retry_classification", sa.String(length=32), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acquired_count", sa.Integer(), nullable=False),
        sa.Column("normalized_count", sa.Integer(), nullable=False),
        sa.Column("promoted_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("failure_details", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["opportunity_data_sources.source_id"]),
        sa.PrimaryKeyConstraint("run_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_opportunity_runs_idempotency_key"),
    )
    op.create_index("ix_opportunity_runs_source", "opportunity_acquisition_runs", ["source_id"])
    op.create_index("ix_opportunity_runs_started", "opportunity_acquisition_runs", ["started_at"])
    op.create_index("ix_opportunity_runs_status", "opportunity_acquisition_runs", ["status"])

    op.create_table(
        "opportunity_source_observations",
        sa.Column("source_observation_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("provider_record_id", sa.String(length=255), nullable=False),
        sa.Column("provider_record_key", sa.String(length=255), nullable=False),
        sa.Column("cursor", sa.String(length=512), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("source_values", sa.JSON(), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=True),
        sa.Column("record_status", sa.String(length=32), nullable=False),
        sa.Column("normalization_status", sa.String(length=32), nullable=False),
        sa.Column("validation_errors", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["opportunity_acquisition_runs.run_id"]),
        sa.ForeignKeyConstraint(["source_id"], ["opportunity_data_sources.source_id"]),
        sa.PrimaryKeyConstraint("source_observation_id"),
        sa.UniqueConstraint(
            "source_id",
            "run_id",
            "provider_record_id",
            name="uq_opportunity_observation_run_record",
        ),
    )
    op.create_index(
        "ix_opportunity_observations_hash", "opportunity_source_observations", ["payload_hash"]
    )
    op.create_index(
        "ix_opportunity_observations_observed", "opportunity_source_observations", ["observed_at"]
    )
    op.create_index(
        "ix_opportunity_observations_run", "opportunity_source_observations", ["run_id"]
    )
    op.create_index(
        "ix_opportunity_observations_source_record",
        "opportunity_source_observations",
        ["source_id", "provider_record_id"],
    )

    op.create_table(
        "current_opportunity_source_links",
        sa.Column("current_opportunity_source_link_id", sa.String(length=64), nullable=False),
        sa.Column("current_opportunity_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("provider_record_id", sa.String(length=255), nullable=False),
        sa.Column("latest_observation_id", sa.String(length=64), nullable=False),
        sa.Column("source_identity_key", sa.String(length=255), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("application_url", sa.String(length=2048), nullable=True),
        sa.Column("identity_confidence", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["current_opportunity_id"], ["current_opportunities.current_opportunity_id"]
        ),
        sa.ForeignKeyConstraint(
            ["latest_observation_id"], ["opportunity_source_observations.source_observation_id"]
        ),
        sa.ForeignKeyConstraint(["source_id"], ["opportunity_data_sources.source_id"]),
        sa.PrimaryKeyConstraint("current_opportunity_source_link_id"),
        sa.UniqueConstraint(
            "source_id", "provider_record_id", name="uq_current_opportunity_source_record"
        ),
    )
    op.create_index(
        "ix_current_opportunity_links_active", "current_opportunity_source_links", ["active"]
    )
    op.create_index(
        "ix_current_opportunity_links_observation",
        "current_opportunity_source_links",
        ["latest_observation_id"],
    )
    op.create_index(
        "ix_current_opportunity_links_opportunity",
        "current_opportunity_source_links",
        ["current_opportunity_id"],
    )
    op.create_index(
        "ix_current_opportunity_links_source", "current_opportunity_source_links", ["source_id"]
    )

    op.create_table(
        "current_opportunity_identity_evidence",
        sa.Column("identity_evidence_id", sa.String(length=64), nullable=False),
        sa.Column("current_opportunity_id", sa.String(length=64), nullable=False),
        sa.Column("source_observation_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("provider_record_id", sa.String(length=255), nullable=False),
        sa.Column("resolution_status", sa.String(length=64), nullable=False),
        sa.Column("identity_key", sa.String(length=255), nullable=False),
        sa.Column("duplicate_group_key", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["current_opportunity_id"], ["current_opportunities.current_opportunity_id"]
        ),
        sa.ForeignKeyConstraint(["source_id"], ["opportunity_data_sources.source_id"]),
        sa.ForeignKeyConstraint(
            ["source_observation_id"], ["opportunity_source_observations.source_observation_id"]
        ),
        sa.PrimaryKeyConstraint("identity_evidence_id"),
    )
    op.create_index(
        "ix_current_opportunity_identity_observation",
        "current_opportunity_identity_evidence",
        ["source_observation_id"],
    )
    op.create_index(
        "ix_current_opportunity_identity_opportunity",
        "current_opportunity_identity_evidence",
        ["current_opportunity_id"],
    )
    op.create_index(
        "ix_current_opportunity_identity_status",
        "current_opportunity_identity_evidence",
        ["resolution_status"],
    )

    op.create_table(
        "opportunity_promotion_receipts",
        sa.Column("promotion_receipt_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("diff_summary", sa.JSON(), nullable=False),
        sa.Column("semantic_warnings", sa.JSON(), nullable=False),
        sa.Column("promoted_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("closed_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["opportunity_acquisition_runs.run_id"]),
        sa.ForeignKeyConstraint(["source_id"], ["opportunity_data_sources.source_id"]),
        sa.PrimaryKeyConstraint("promotion_receipt_id"),
        sa.UniqueConstraint("run_id", name="uq_opportunity_promotion_receipts_run"),
    )
    op.create_index(
        "ix_opportunity_promotion_receipts_source", "opportunity_promotion_receipts", ["source_id"]
    )
    op.create_index(
        "ix_opportunity_promotion_receipts_status", "opportunity_promotion_receipts", ["status"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_opportunity_promotion_receipts_status", table_name="opportunity_promotion_receipts"
    )
    op.drop_index(
        "ix_opportunity_promotion_receipts_source", table_name="opportunity_promotion_receipts"
    )
    op.drop_table("opportunity_promotion_receipts")
    op.drop_index(
        "ix_current_opportunity_identity_status", table_name="current_opportunity_identity_evidence"
    )
    op.drop_index(
        "ix_current_opportunity_identity_opportunity",
        table_name="current_opportunity_identity_evidence",
    )
    op.drop_index(
        "ix_current_opportunity_identity_observation",
        table_name="current_opportunity_identity_evidence",
    )
    op.drop_table("current_opportunity_identity_evidence")
    op.drop_index(
        "ix_current_opportunity_links_source", table_name="current_opportunity_source_links"
    )
    op.drop_index(
        "ix_current_opportunity_links_opportunity", table_name="current_opportunity_source_links"
    )
    op.drop_index(
        "ix_current_opportunity_links_observation", table_name="current_opportunity_source_links"
    )
    op.drop_index(
        "ix_current_opportunity_links_active", table_name="current_opportunity_source_links"
    )
    op.drop_table("current_opportunity_source_links")
    op.drop_index(
        "ix_opportunity_observations_source_record", table_name="opportunity_source_observations"
    )
    op.drop_index("ix_opportunity_observations_run", table_name="opportunity_source_observations")
    op.drop_index(
        "ix_opportunity_observations_observed", table_name="opportunity_source_observations"
    )
    op.drop_index("ix_opportunity_observations_hash", table_name="opportunity_source_observations")
    op.drop_table("opportunity_source_observations")
    op.drop_index("ix_opportunity_runs_status", table_name="opportunity_acquisition_runs")
    op.drop_index("ix_opportunity_runs_started", table_name="opportunity_acquisition_runs")
    op.drop_index("ix_opportunity_runs_source", table_name="opportunity_acquisition_runs")
    op.drop_table("opportunity_acquisition_runs")
    op.drop_index("ix_opportunity_coverage_type", table_name="opportunity_coverage_contracts")
    op.drop_index("ix_opportunity_coverage_status", table_name="opportunity_coverage_contracts")
    op.drop_index("ix_opportunity_coverage_role", table_name="opportunity_coverage_contracts")
    op.drop_index("ix_opportunity_coverage_market", table_name="opportunity_coverage_contracts")
    op.drop_table("opportunity_coverage_contracts")
    op.drop_index("ix_current_opportunities_status", table_name="current_opportunities")
    op.drop_index("ix_current_opportunities_role_family", table_name="current_opportunities")
    op.drop_index("ix_current_opportunities_ranking", table_name="current_opportunities")
    op.drop_index("ix_current_opportunities_market", table_name="current_opportunities")
    op.drop_index("ix_current_opportunities_last_observed", table_name="current_opportunities")
    op.drop_index("ix_current_opportunities_freshness", table_name="current_opportunities")
    op.drop_index("ix_current_opportunities_duplicate_group", table_name="current_opportunities")
    op.drop_index("ix_current_opportunities_company_name", table_name="current_opportunities")
    op.drop_index("ix_current_opportunities_company", table_name="current_opportunities")
    op.drop_table("current_opportunities")
    op.drop_index("ix_opportunity_data_sources_ranking", table_name="opportunity_data_sources")
    op.drop_index("ix_opportunity_data_sources_provider", table_name="opportunity_data_sources")
    op.drop_index(
        "ix_opportunity_data_sources_operational_status", table_name="opportunity_data_sources"
    )
    op.drop_index("ix_opportunity_data_sources_enabled", table_name="opportunity_data_sources")
    op.drop_table("opportunity_data_sources")
