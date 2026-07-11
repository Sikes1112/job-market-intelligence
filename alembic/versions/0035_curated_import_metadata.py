"""Add Layer 31B curated import metadata columns.

Revision ID: 0035_curated_import_metadata
Revises: 0034_exception_cases
Create Date: 2026-07-09
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0035_curated_import_metadata"
down_revision = "0034_exception_cases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "source_refs",
        sa.Column("freshness_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "source_observations",
        sa.Column("freshness_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "fact_source_links",
        sa.Column("freshness_status", sa.String(length=32), nullable=True),
    )

    op.add_column(
        "company_region_hiring",
        sa.Column(
            "active_posting_count_now_status",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "company_region_hiring",
        sa.Column("posting_count_30d_status", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "company_region_hiring",
        sa.Column("posting_count_90d_status", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "company_region_hiring",
        sa.Column("hiring_program_count_status", sa.String(length=64), nullable=True),
    )

    op.add_column(
        "company_region_entry_level",
        sa.Column("internship_count_status", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "company_region_entry_level",
        sa.Column("coop_count_status", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "company_region_entry_level",
        sa.Column(
            "entry_level_full_time_count_status",
            sa.String(length=64),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("company_region_entry_level", "entry_level_full_time_count_status")
    op.drop_column("company_region_entry_level", "coop_count_status")
    op.drop_column("company_region_entry_level", "internship_count_status")

    op.drop_column("company_region_hiring", "hiring_program_count_status")
    op.drop_column("company_region_hiring", "posting_count_90d_status")
    op.drop_column("company_region_hiring", "posting_count_30d_status")
    op.drop_column("company_region_hiring", "active_posting_count_now_status")

    op.drop_column("fact_source_links", "freshness_status")
    op.drop_column("source_observations", "freshness_status")
    op.drop_column("source_refs", "freshness_status")
