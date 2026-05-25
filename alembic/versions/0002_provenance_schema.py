"""Add provenance schema.

Revision ID: 0002_provenance_schema
Revises: 0001_initial_schema
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_provenance_schema"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_refs",
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("url_or_provider", sa.String(length=1024), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_or_terms_category", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("data_origin", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.String(length=2048), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index("ix_source_refs_data_origin", "source_refs", ["data_origin"])
    op.create_index(
        "ix_source_refs_license",
        "source_refs",
        ["license_or_terms_category"],
    )
    op.create_index("ix_source_refs_source_type", "source_refs", ["source_type"])

    op.create_table(
        "source_observations",
        sa.Column("observation_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("url_or_provider", sa.String(length=1024), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("license_or_terms_category", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("data_origin", sa.String(length=64), nullable=False),
        sa.Column("observation_status", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.String(length=2048), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["source_refs.source_id"]),
        sa.PrimaryKeyConstraint("observation_id"),
    )
    op.create_index(
        "ix_source_observations_collected_at",
        "source_observations",
        ["collected_at"],
    )
    op.create_index(
        "ix_source_observations_data_origin",
        "source_observations",
        ["data_origin"],
    )
    op.create_index(
        "ix_source_observations_observed_at",
        "source_observations",
        ["observed_at"],
    )
    op.create_index(
        "ix_source_observations_source_id",
        "source_observations",
        ["source_id"],
    )
    op.create_index(
        "ix_source_observations_source_type",
        "source_observations",
        ["source_type"],
    )

    op.create_table(
        "fact_source_links",
        sa.Column("link_id", sa.String(length=128), nullable=False),
        sa.Column("observation_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("fact_type", sa.String(length=64), nullable=False),
        sa.Column("fact_id", sa.String(length=128), nullable=False),
        sa.Column("fact_field", sa.String(length=128), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("url_or_provider", sa.String(length=1024), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("license_or_terms_category", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("data_origin", sa.String(length=64), nullable=False),
        sa.Column("observation_status", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.String(length=2048), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["observation_id"], ["source_observations.observation_id"]),
        sa.ForeignKeyConstraint(["source_id"], ["source_refs.source_id"]),
        sa.PrimaryKeyConstraint("link_id"),
        sa.UniqueConstraint(
            "fact_type",
            "fact_id",
            "fact_field",
            "observation_id",
            name="uq_fact_source_link_fact_observation",
        ),
    )
    op.create_index(
        "ix_fact_source_links_data_origin",
        "fact_source_links",
        ["data_origin"],
    )
    op.create_index(
        "ix_fact_source_links_fact",
        "fact_source_links",
        ["fact_type", "fact_id"],
    )
    op.create_index(
        "ix_fact_source_links_observation_id",
        "fact_source_links",
        ["observation_id"],
    )
    op.create_index(
        "ix_fact_source_links_source_id",
        "fact_source_links",
        ["source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_fact_source_links_source_id", table_name="fact_source_links")
    op.drop_index(
        "ix_fact_source_links_observation_id",
        table_name="fact_source_links",
    )
    op.drop_index("ix_fact_source_links_fact", table_name="fact_source_links")
    op.drop_index(
        "ix_fact_source_links_data_origin",
        table_name="fact_source_links",
    )
    op.drop_table("fact_source_links")

    op.drop_index(
        "ix_source_observations_source_type",
        table_name="source_observations",
    )
    op.drop_index(
        "ix_source_observations_source_id",
        table_name="source_observations",
    )
    op.drop_index(
        "ix_source_observations_observed_at",
        table_name="source_observations",
    )
    op.drop_index(
        "ix_source_observations_data_origin",
        table_name="source_observations",
    )
    op.drop_index(
        "ix_source_observations_collected_at",
        table_name="source_observations",
    )
    op.drop_table("source_observations")

    op.drop_index("ix_source_refs_source_type", table_name="source_refs")
    op.drop_index("ix_source_refs_license", table_name="source_refs")
    op.drop_index("ix_source_refs_data_origin", table_name="source_refs")
    op.drop_table("source_refs")
