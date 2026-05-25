"""Add raw ingestion intake schema.

Revision ID: 0003_ingestion_raw_intake
Revises: 0002_provenance_schema
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_ingestion_raw_intake"
down_revision = "0002_provenance_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_ingestion_records",
        sa.Column("raw_record_id", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("url_or_provider", sa.String(length=1024), nullable=False),
        sa.Column("external_entity_id", sa.String(length=128), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=True),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingestion_status", sa.String(length=64), nullable=False),
        sa.Column("normalization_status", sa.String(length=64), nullable=False),
        sa.Column("intended_fact_type", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("observation_id", sa.String(length=64), nullable=True),
        sa.Column("parsing_notes", sa.String(length=2048), nullable=True),
        sa.Column("parsing_errors", sa.JSON(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["observation_id"], ["source_observations.observation_id"]),
        sa.ForeignKeyConstraint(["source_id"], ["source_refs.source_id"]),
        sa.PrimaryKeyConstraint("raw_record_id"),
    )
    op.create_index(
        "ix_raw_ingestion_external_entity",
        "raw_ingestion_records",
        ["external_entity_id"],
    )
    op.create_index(
        "ix_raw_ingestion_intended_fact_type",
        "raw_ingestion_records",
        ["intended_fact_type"],
    )
    op.create_index(
        "ix_raw_ingestion_normalization_status",
        "raw_ingestion_records",
        ["normalization_status"],
    )
    op.create_index(
        "ix_raw_ingestion_observation_id",
        "raw_ingestion_records",
        ["observation_id"],
    )
    op.create_index(
        "ix_raw_ingestion_payload_checksum",
        "raw_ingestion_records",
        ["payload_checksum"],
    )
    op.create_index(
        "ix_raw_ingestion_provider",
        "raw_ingestion_records",
        ["provider_id"],
    )
    op.create_index(
        "ix_raw_ingestion_source_id",
        "raw_ingestion_records",
        ["source_id"],
    )
    op.create_index(
        "ix_raw_ingestion_source_type",
        "raw_ingestion_records",
        ["source_type"],
    )
    op.create_index(
        "ix_raw_ingestion_status",
        "raw_ingestion_records",
        ["ingestion_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_raw_ingestion_status", table_name="raw_ingestion_records")
    op.drop_index("ix_raw_ingestion_source_type", table_name="raw_ingestion_records")
    op.drop_index("ix_raw_ingestion_source_id", table_name="raw_ingestion_records")
    op.drop_index("ix_raw_ingestion_provider", table_name="raw_ingestion_records")
    op.drop_index(
        "ix_raw_ingestion_payload_checksum",
        table_name="raw_ingestion_records",
    )
    op.drop_index(
        "ix_raw_ingestion_observation_id",
        table_name="raw_ingestion_records",
    )
    op.drop_index(
        "ix_raw_ingestion_normalization_status",
        table_name="raw_ingestion_records",
    )
    op.drop_index(
        "ix_raw_ingestion_intended_fact_type",
        table_name="raw_ingestion_records",
    )
    op.drop_index(
        "ix_raw_ingestion_external_entity",
        table_name="raw_ingestion_records",
    )
    op.drop_table("raw_ingestion_records")
