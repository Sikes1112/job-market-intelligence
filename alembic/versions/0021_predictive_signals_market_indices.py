"""Add Layer 18B predictive signals and market indices.

Revision ID: 0021_predictive_signals_market_indices
Revises: 0020_historical_intelligence_foundation
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0021_predictive_signals_market_indices"
down_revision = "0020_historical_intelligence_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "predictive_signals",
        sa.Column("predictive_signal_id", sa.String(length=64), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=True),
        sa.Column("signal_strength", sa.String(length=32), nullable=False),
        sa.Column("confidence_level", sa.String(length=32), nullable=False),
        sa.Column("evidence_window_start", sa.Date(), nullable=False),
        sa.Column("evidence_window_end", sa.Date(), nullable=False),
        sa.Column("snapshot_count", sa.Integer(), nullable=False),
        sa.Column("minimum_snapshot_count_met", sa.Boolean(), nullable=False),
        sa.Column("summary", sa.String(length=1024), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        _predictive_signal_type_check(),
        sa.CheckConstraint(
            "target_type IN ('region', 'company_region', 'sector_region')",
            name="ck_predictive_signals_target_type",
        ),
        sa.CheckConstraint(
            "signal_strength IN ('weak', 'moderate', 'strong')",
            name="ck_predictive_signals_strength",
        ),
        sa.CheckConstraint(
            "confidence_level IN ('low', 'medium', 'high', 'unknown')",
            name="ck_predictive_signals_confidence_level",
        ),
        sa.CheckConstraint(
            "status IN ('candidate', 'active', 'expired', 'rejected', 'superseded')",
            name="ck_predictive_signals_status",
        ),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("predictive_signal_id"),
    )
    op.create_index(
        "ix_predictive_signals_created_at",
        "predictive_signals",
        ["created_at"],
    )
    op.create_index(
        "ix_predictive_signals_region",
        "predictive_signals",
        ["region_id"],
    )
    op.create_index(
        "ix_predictive_signals_status",
        "predictive_signals",
        ["status"],
    )
    op.create_index(
        "ix_predictive_signals_target",
        "predictive_signals",
        ["target_type", "target_id"],
    )
    op.create_index("ix_predictive_signals_type", "predictive_signals", ["signal_type"])

    op.create_table(
        "market_indices",
        sa.Column("market_index_id", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'retired')",
            name="ck_market_indices_status",
        ),
        sa.PrimaryKeyConstraint("market_index_id"),
        sa.UniqueConstraint("key", name="uq_market_indices_key"),
    )
    op.create_index("ix_market_indices_created_at", "market_indices", ["created_at"])
    op.create_index("ix_market_indices_key", "market_indices", ["key"])
    op.create_index("ix_market_indices_status", "market_indices", ["status"])

    op.create_table(
        "signal_inputs",
        sa.Column("signal_input_id", sa.String(length=64), nullable=False),
        sa.Column("predictive_signal_id", sa.String(length=64), nullable=False),
        sa.Column("source_snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("historical_observation_id", sa.String(length=64), nullable=True),
        sa.Column("input_type", sa.String(length=64), nullable=False),
        sa.Column("input_weight", sa.Float(), nullable=True),
        sa.Column("contribution_strength", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["historical_observation_id"],
            ["historical_observations.historical_observation_id"],
        ),
        sa.ForeignKeyConstraint(
            ["predictive_signal_id"],
            ["predictive_signals.predictive_signal_id"],
        ),
        sa.PrimaryKeyConstraint("signal_input_id"),
    )
    op.create_index("ix_signal_inputs_created_at", "signal_inputs", ["created_at"])
    op.create_index(
        "ix_signal_inputs_observation",
        "signal_inputs",
        ["historical_observation_id"],
    )
    op.create_index("ix_signal_inputs_signal", "signal_inputs", ["predictive_signal_id"])
    op.create_index("ix_signal_inputs_snapshot", "signal_inputs", ["source_snapshot_id"])
    op.create_index("ix_signal_inputs_type", "signal_inputs", ["input_type"])

    op.create_table(
        "market_index_versions",
        sa.Column("market_index_version_id", sa.String(length=64), nullable=False),
        sa.Column("index_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("formula_description", sa.String(length=2048), nullable=False),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("internal_weight_config", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'retired')",
            name="ck_market_index_versions_status",
        ),
        sa.ForeignKeyConstraint(["index_id"], ["market_indices.market_index_id"]),
        sa.PrimaryKeyConstraint("market_index_version_id"),
        sa.UniqueConstraint("index_id", "version", name="uq_market_index_versions_index"),
    )
    op.create_index(
        "ix_market_index_versions_created_at",
        "market_index_versions",
        ["created_at"],
    )
    op.create_index(
        "ix_market_index_versions_effective_date",
        "market_index_versions",
        ["effective_date"],
    )
    op.create_index(
        "ix_market_index_versions_index",
        "market_index_versions",
        ["index_id"],
    )
    op.create_index(
        "ix_market_index_versions_status",
        "market_index_versions",
        ["status"],
    )

    op.create_table(
        "market_index_scores",
        sa.Column("market_index_score_id", sa.String(length=64), nullable=False),
        sa.Column("index_id", sa.String(length=64), nullable=False),
        sa.Column("index_version_id", sa.String(length=64), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("freshness_state", sa.String(length=32), nullable=True),
        sa.Column("evidence_summary", sa.JSON(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["index_id"], ["market_indices.market_index_id"]),
        sa.ForeignKeyConstraint(
            ["index_version_id"],
            ["market_index_versions.market_index_version_id"],
        ),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("market_index_score_id"),
    )
    op.create_index(
        "ix_market_index_scores_calculated_at",
        "market_index_scores",
        ["calculated_at"],
    )
    op.create_index(
        "ix_market_index_scores_created_at",
        "market_index_scores",
        ["created_at"],
    )
    op.create_index(
        "ix_market_index_scores_index_region",
        "market_index_scores",
        ["index_id", "region_id"],
    )
    op.create_index(
        "ix_market_index_scores_region",
        "market_index_scores",
        ["region_id"],
    )
    op.create_index(
        "ix_market_index_scores_version",
        "market_index_scores",
        ["index_version_id"],
    )

    op.create_table(
        "market_index_inputs",
        sa.Column("market_index_input_id", sa.String(length=64), nullable=False),
        sa.Column("index_score_id", sa.String(length=64), nullable=False),
        sa.Column("input_name", sa.String(length=64), nullable=False),
        sa.Column("input_value", sa.Float(), nullable=True),
        sa.Column("input_weight", sa.Float(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["index_score_id"],
            ["market_index_scores.market_index_score_id"],
        ),
        sa.PrimaryKeyConstraint("market_index_input_id"),
    )
    op.create_index(
        "ix_market_index_inputs_created_at",
        "market_index_inputs",
        ["created_at"],
    )
    op.create_index("ix_market_index_inputs_name", "market_index_inputs", ["input_name"])
    op.create_index(
        "ix_market_index_inputs_score",
        "market_index_inputs",
        ["index_score_id"],
    )
    op.create_index(
        "ix_market_index_inputs_source",
        "market_index_inputs",
        ["source_type", "source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_index_inputs_source", table_name="market_index_inputs")
    op.drop_index("ix_market_index_inputs_score", table_name="market_index_inputs")
    op.drop_index("ix_market_index_inputs_name", table_name="market_index_inputs")
    op.drop_index("ix_market_index_inputs_created_at", table_name="market_index_inputs")
    op.drop_table("market_index_inputs")

    op.drop_index("ix_market_index_scores_version", table_name="market_index_scores")
    op.drop_index("ix_market_index_scores_region", table_name="market_index_scores")
    op.drop_index("ix_market_index_scores_index_region", table_name="market_index_scores")
    op.drop_index("ix_market_index_scores_created_at", table_name="market_index_scores")
    op.drop_index("ix_market_index_scores_calculated_at", table_name="market_index_scores")
    op.drop_table("market_index_scores")

    op.drop_index("ix_market_index_versions_status", table_name="market_index_versions")
    op.drop_index("ix_market_index_versions_index", table_name="market_index_versions")
    op.drop_index(
        "ix_market_index_versions_effective_date",
        table_name="market_index_versions",
    )
    op.drop_index("ix_market_index_versions_created_at", table_name="market_index_versions")
    op.drop_table("market_index_versions")

    op.drop_index("ix_signal_inputs_type", table_name="signal_inputs")
    op.drop_index("ix_signal_inputs_snapshot", table_name="signal_inputs")
    op.drop_index("ix_signal_inputs_signal", table_name="signal_inputs")
    op.drop_index("ix_signal_inputs_observation", table_name="signal_inputs")
    op.drop_index("ix_signal_inputs_created_at", table_name="signal_inputs")
    op.drop_table("signal_inputs")

    op.drop_index("ix_market_indices_status", table_name="market_indices")
    op.drop_index("ix_market_indices_key", table_name="market_indices")
    op.drop_index("ix_market_indices_created_at", table_name="market_indices")
    op.drop_table("market_indices")

    op.drop_index("ix_predictive_signals_type", table_name="predictive_signals")
    op.drop_index("ix_predictive_signals_target", table_name="predictive_signals")
    op.drop_index("ix_predictive_signals_status", table_name="predictive_signals")
    op.drop_index("ix_predictive_signals_region", table_name="predictive_signals")
    op.drop_index("ix_predictive_signals_created_at", table_name="predictive_signals")
    op.drop_table("predictive_signals")


def _predictive_signal_type_check() -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "signal_type IN ("
        "'emerging_market', "
        "'declining_market', "
        "'seasonal_hiring_window', "
        "'company_expansion_signal', "
        "'entry_level_access_trend'"
        ")",
        name="ck_predictive_signals_type",
    )
