"""Add Layer 18C benchmark reports.

Revision ID: 0022_benchmark_reports
Revises: 0021_predictive_signals_market_indices
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0022_benchmark_reports"
down_revision = "0021_predictive_signals_market_indices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benchmark_reports",
        sa.Column("benchmark_report_id", sa.String(length=64), nullable=False),
        sa.Column("report_key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("report_period", sa.String(length=64), nullable=False),
        sa.Column("report_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.String(length=2048), nullable=False),
        sa.Column("methodology_summary", sa.String(length=2048), nullable=False),
        sa.Column("data_window_start", sa.Date(), nullable=False),
        sa.Column("data_window_end", sa.Date(), nullable=False),
        sa.Column("freshness_notes", sa.String(length=2048), nullable=True),
        sa.Column("confidence_notes", sa.String(length=2048), nullable=True),
        sa.Column("coverage_notes", sa.String(length=2048), nullable=True),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        _benchmark_report_key_check(),
        _benchmark_report_type_check(),
        sa.CheckConstraint(
            "status IN ('draft', 'review_ready', 'published', 'archived', 'superseded')",
            name="ck_benchmark_reports_status",
        ),
        sa.PrimaryKeyConstraint("benchmark_report_id"),
    )
    op.create_index(
        "ix_benchmark_reports_created_at",
        "benchmark_reports",
        ["created_at"],
    )
    op.create_index(
        "ix_benchmark_reports_key_status",
        "benchmark_reports",
        ["report_key", "status"],
    )
    op.create_index(
        "ix_benchmark_reports_period",
        "benchmark_reports",
        ["report_period"],
    )
    op.create_index(
        "ix_benchmark_reports_published_at",
        "benchmark_reports",
        ["published_at"],
    )

    op.create_table(
        "benchmark_report_sections",
        sa.Column("benchmark_report_section_id", sa.String(length=64), nullable=False),
        sa.Column("report_id", sa.String(length=64), nullable=False),
        sa.Column("section_key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.String(length=4096), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["benchmark_reports.benchmark_report_id"]),
        sa.PrimaryKeyConstraint("benchmark_report_section_id"),
        sa.UniqueConstraint("report_id", "section_key", name="uq_report_sections_key"),
    )
    op.create_index(
        "ix_report_sections_created_at",
        "benchmark_report_sections",
        ["created_at"],
    )
    op.create_index(
        "ix_report_sections_report_order",
        "benchmark_report_sections",
        ["report_id", "display_order"],
    )

    op.create_table(
        "benchmark_report_rankings",
        sa.Column("benchmark_report_ranking_id", sa.String(length=64), nullable=False),
        sa.Column("report_id", sa.String(length=64), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("index_score_id", sa.String(length=64), nullable=True),
        sa.Column("explanation", sa.String(length=2048), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("freshness_state", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["index_score_id"], ["market_index_scores.market_index_score_id"]),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.ForeignKeyConstraint(["report_id"], ["benchmark_reports.benchmark_report_id"]),
        sa.PrimaryKeyConstraint("benchmark_report_ranking_id"),
        sa.UniqueConstraint("report_id", "rank", name="uq_report_rankings_rank"),
    )
    op.create_index(
        "ix_report_rankings_created_at",
        "benchmark_report_rankings",
        ["created_at"],
    )
    op.create_index(
        "ix_report_rankings_index_score",
        "benchmark_report_rankings",
        ["index_score_id"],
    )
    op.create_index(
        "ix_report_rankings_region",
        "benchmark_report_rankings",
        ["region_id"],
    )
    op.create_index(
        "ix_report_rankings_report_rank",
        "benchmark_report_rankings",
        ["report_id", "rank"],
    )

    op.create_table(
        "benchmark_report_evidence",
        sa.Column("benchmark_report_evidence_id", sa.String(length=64), nullable=False),
        sa.Column("report_id", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("evidence_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["benchmark_reports.benchmark_report_id"]),
        sa.PrimaryKeyConstraint("benchmark_report_evidence_id"),
    )
    op.create_index(
        "ix_report_evidence_created_at",
        "benchmark_report_evidence",
        ["created_at"],
    )
    op.create_index(
        "ix_report_evidence_report",
        "benchmark_report_evidence",
        ["report_id"],
    )
    op.create_index(
        "ix_report_evidence_source",
        "benchmark_report_evidence",
        ["source_type", "source_id"],
    )
    op.create_index(
        "ix_report_evidence_target",
        "benchmark_report_evidence",
        ["target_type", "target_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_report_evidence_target", table_name="benchmark_report_evidence")
    op.drop_index("ix_report_evidence_source", table_name="benchmark_report_evidence")
    op.drop_index("ix_report_evidence_report", table_name="benchmark_report_evidence")
    op.drop_index("ix_report_evidence_created_at", table_name="benchmark_report_evidence")
    op.drop_table("benchmark_report_evidence")

    op.drop_index("ix_report_rankings_report_rank", table_name="benchmark_report_rankings")
    op.drop_index("ix_report_rankings_region", table_name="benchmark_report_rankings")
    op.drop_index("ix_report_rankings_index_score", table_name="benchmark_report_rankings")
    op.drop_index("ix_report_rankings_created_at", table_name="benchmark_report_rankings")
    op.drop_table("benchmark_report_rankings")

    op.drop_index("ix_report_sections_report_order", table_name="benchmark_report_sections")
    op.drop_index("ix_report_sections_created_at", table_name="benchmark_report_sections")
    op.drop_table("benchmark_report_sections")

    op.drop_index("ix_benchmark_reports_published_at", table_name="benchmark_reports")
    op.drop_index("ix_benchmark_reports_period", table_name="benchmark_reports")
    op.drop_index("ix_benchmark_reports_key_status", table_name="benchmark_reports")
    op.drop_index("ix_benchmark_reports_created_at", table_name="benchmark_reports")
    op.drop_table("benchmark_reports")


def _benchmark_report_key_check() -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "report_key IN ("
        "'best_cities_early_career_ai_roles', "
        "'top_emerging_tech_markets', "
        "'best_markets_product_careers', "
        "'best_regions_internship_access'"
        ")",
        name="ck_benchmark_reports_key",
    )


def _benchmark_report_type_check() -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "report_type IN ("
        "'early_career_ai_roles', "
        "'emerging_tech_markets', "
        "'product_careers', "
        "'internship_access'"
        ")",
        name="ck_benchmark_reports_type",
    )
