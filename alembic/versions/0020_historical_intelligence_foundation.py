"""Add Layer 18A historical intelligence foundation.

Revision ID: 0020_historical_intelligence_foundation
Revises: 0019_controlled_api_career_platforms
Create Date: 2026-06-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0020_historical_intelligence_foundation"
down_revision = "0019_controlled_api_career_platforms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_snapshots",
        sa.Column("market_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("snapshot_type", sa.String(length=32), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("entry_level_access_score", sa.Float(), nullable=True),
        sa.Column("internship_density_score", sa.Float(), nullable=True),
        sa.Column("ai_opportunity_score", sa.Float(), nullable=True),
        sa.Column("product_opportunity_score", sa.Float(), nullable=True),
        sa.Column("company_presence_score", sa.Float(), nullable=True),
        sa.Column("hidden_opportunity_score", sa.Float(), nullable=True),
        sa.Column("coverage_tier", sa.String(length=32), nullable=True),
        sa.Column("freshness_state", sa.String(length=32), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("provenance_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("market_snapshot_id"),
    )
    op.create_index("ix_market_snapshots_created_at", "market_snapshots", ["created_at"])
    op.create_index(
        "ix_market_snapshots_region_date",
        "market_snapshots",
        ["region_id", "snapshot_date"],
    )
    op.create_index("ix_market_snapshots_type", "market_snapshots", ["snapshot_type"])

    op.create_table(
        "company_region_snapshots",
        sa.Column("company_region_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.String(length=64), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("snapshot_type", sa.String(length=32), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("entry_level_access_score", sa.Float(), nullable=True),
        sa.Column("internship_density_score", sa.Float(), nullable=True),
        sa.Column("ai_opportunity_score", sa.Float(), nullable=True),
        sa.Column("product_opportunity_score", sa.Float(), nullable=True),
        sa.Column("company_presence_score", sa.Float(), nullable=True),
        sa.Column("hiring_activity_score", sa.Float(), nullable=True),
        sa.Column("hidden_opportunity_score", sa.Float(), nullable=True),
        sa.Column("presence_status", sa.String(length=32), nullable=True),
        sa.Column("currently_hiring_flag", sa.Boolean(), nullable=True),
        sa.Column("active_posting_count", sa.Integer(), nullable=True),
        sa.Column("posting_count_30d", sa.Integer(), nullable=True),
        sa.Column("posting_count_90d", sa.Integer(), nullable=True),
        sa.Column("internship_count", sa.Integer(), nullable=True),
        sa.Column("coverage_tier", sa.String(length=32), nullable=True),
        sa.Column("freshness_state", sa.String(length=32), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("provenance_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"]),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("company_region_snapshot_id"),
    )
    op.create_index(
        "ix_company_region_snapshots_company_region_date",
        "company_region_snapshots",
        ["company_id", "region_id", "snapshot_date"],
    )
    op.create_index(
        "ix_company_region_snapshots_created_at",
        "company_region_snapshots",
        ["created_at"],
    )
    op.create_index(
        "ix_company_region_snapshots_region",
        "company_region_snapshots",
        ["region_id"],
    )
    op.create_index(
        "ix_company_region_snapshots_type",
        "company_region_snapshots",
        ["snapshot_type"],
    )

    op.create_table(
        "sector_region_snapshots",
        sa.Column("sector_region_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("sector_id", sa.String(length=64), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("snapshot_type", sa.String(length=32), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("entry_level_access_score", sa.Float(), nullable=True),
        sa.Column("internship_density_score", sa.Float(), nullable=True),
        sa.Column("ai_opportunity_score", sa.Float(), nullable=True),
        sa.Column("product_opportunity_score", sa.Float(), nullable=True),
        sa.Column("company_presence_score", sa.Float(), nullable=True),
        sa.Column("hiring_activity_score", sa.Float(), nullable=True),
        sa.Column("hidden_opportunity_score", sa.Float(), nullable=True),
        sa.Column("sector_company_count", sa.Integer(), nullable=True),
        sa.Column("active_company_count", sa.Integer(), nullable=True),
        sa.Column("coverage_tier", sa.String(length=32), nullable=True),
        sa.Column("freshness_state", sa.String(length=32), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("provenance_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("sector_region_snapshot_id"),
    )
    op.create_index(
        "ix_sector_region_snapshots_created_at",
        "sector_region_snapshots",
        ["created_at"],
    )
    op.create_index(
        "ix_sector_region_snapshots_region",
        "sector_region_snapshots",
        ["region_id"],
    )
    op.create_index(
        "ix_sector_region_snapshots_sector_region_date",
        "sector_region_snapshots",
        ["sector_id", "region_id", "snapshot_date"],
    )
    op.create_index(
        "ix_sector_region_snapshots_type",
        "sector_region_snapshots",
        ["snapshot_type"],
    )

    op.create_table(
        "market_score_history",
        sa.Column("market_score_history_id", sa.String(length=64), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("market_snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("score_name", sa.String(length=64), nullable=False),
        sa.Column("score_value", sa.Float(), nullable=False),
        sa.Column("score_ruleset_version", sa.String(length=64), nullable=True),
        sa.Column("ranking_position", sa.Integer(), nullable=True),
        sa.Column("coverage_tier", sa.String(length=32), nullable=True),
        sa.Column("freshness_state", sa.String(length=32), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("provenance_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["market_snapshot_id"],
            ["market_snapshots.market_snapshot_id"],
        ),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("market_score_history_id"),
    )
    op.create_index(
        "ix_market_score_history_created_at",
        "market_score_history",
        ["created_at"],
    )
    op.create_index(
        "ix_market_score_history_region_date",
        "market_score_history",
        ["region_id", "snapshot_date"],
    )
    op.create_index(
        "ix_market_score_history_score_name",
        "market_score_history",
        ["score_name"],
    )
    op.create_index(
        "ix_market_score_history_snapshot",
        "market_score_history",
        ["market_snapshot_id"],
    )

    op.create_table(
        "historical_observations",
        sa.Column("historical_observation_id", sa.String(length=64), nullable=False),
        sa.Column("observation_type", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=True),
        sa.Column("previous_snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("current_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("delta_value", sa.Float(), nullable=True),
        sa.Column("delta_direction", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("evidence_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _historical_observation_type_check(),
        sa.CheckConstraint(
            "target_type IN ('region', 'company_region', 'sector_region')",
            name="ck_historical_observations_target_type",
        ),
        sa.CheckConstraint(
            "delta_direction IN ('increased', 'decreased', 'changed')",
            name="ck_historical_observations_direction",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high')",
            name="ck_historical_observations_severity",
        ),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("historical_observation_id"),
    )
    op.create_index(
        "ix_historical_observations_created_at",
        "historical_observations",
        ["created_at"],
    )
    op.create_index(
        "ix_historical_observations_current",
        "historical_observations",
        ["current_snapshot_id"],
    )
    op.create_index(
        "ix_historical_observations_region",
        "historical_observations",
        ["region_id"],
    )
    op.create_index(
        "ix_historical_observations_target",
        "historical_observations",
        ["target_type", "target_id"],
    )
    op.create_index(
        "ix_historical_observations_type",
        "historical_observations",
        ["observation_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_historical_observations_type", table_name="historical_observations")
    op.drop_index("ix_historical_observations_target", table_name="historical_observations")
    op.drop_index("ix_historical_observations_region", table_name="historical_observations")
    op.drop_index("ix_historical_observations_current", table_name="historical_observations")
    op.drop_index("ix_historical_observations_created_at", table_name="historical_observations")
    op.drop_table("historical_observations")

    op.drop_index("ix_market_score_history_snapshot", table_name="market_score_history")
    op.drop_index("ix_market_score_history_score_name", table_name="market_score_history")
    op.drop_index("ix_market_score_history_region_date", table_name="market_score_history")
    op.drop_index("ix_market_score_history_created_at", table_name="market_score_history")
    op.drop_table("market_score_history")

    op.drop_index("ix_sector_region_snapshots_type", table_name="sector_region_snapshots")
    op.drop_index(
        "ix_sector_region_snapshots_sector_region_date",
        table_name="sector_region_snapshots",
    )
    op.drop_index("ix_sector_region_snapshots_region", table_name="sector_region_snapshots")
    op.drop_index(
        "ix_sector_region_snapshots_created_at",
        table_name="sector_region_snapshots",
    )
    op.drop_table("sector_region_snapshots")

    op.drop_index("ix_company_region_snapshots_type", table_name="company_region_snapshots")
    op.drop_index(
        "ix_company_region_snapshots_region",
        table_name="company_region_snapshots",
    )
    op.drop_index(
        "ix_company_region_snapshots_created_at",
        table_name="company_region_snapshots",
    )
    op.drop_index(
        "ix_company_region_snapshots_company_region_date",
        table_name="company_region_snapshots",
    )
    op.drop_table("company_region_snapshots")

    op.drop_index("ix_market_snapshots_type", table_name="market_snapshots")
    op.drop_index("ix_market_snapshots_region_date", table_name="market_snapshots")
    op.drop_index("ix_market_snapshots_created_at", table_name="market_snapshots")
    op.drop_table("market_snapshots")


def _historical_observation_type_check() -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "observation_type IN ("
        "'company_presence_increased', "
        "'company_presence_decreased', "
        "'hiring_activity_increased', "
        "'hiring_activity_decreased', "
        "'entry_level_access_improved', "
        "'entry_level_access_declined', "
        "'regional_score_increased', "
        "'regional_score_decreased', "
        "'sector_growth_detected', "
        "'sector_decline_detected', "
        "'internship_density_changed'"
        ")",
        name="ck_historical_observations_type",
    )
