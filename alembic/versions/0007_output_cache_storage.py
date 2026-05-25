"""Add output cache storage fields.

Revision ID: 0007_output_cache
Revises: 0006_rec_snapshots
Create Date: 2026-05-24
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_output_cache"
down_revision = "0006_rec_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("output_metadata", sa.Column("cached_payload", sa.JSON(), nullable=True))
    op.add_column("output_metadata", sa.Column("source_version_refs", sa.JSON(), nullable=True))
    op.add_column(
        "output_metadata",
        sa.Column("source_bundle_ref", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "output_metadata",
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "output_metadata",
        sa.Column("rebuilt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "output_metadata",
        sa.Column("stale_reason", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "output_metadata",
        sa.Column("rebuild_job_key", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "output_metadata",
        sa.Column("latest_rebuild_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "output_metadata",
        sa.Column("latest_rebuild_failure_reason", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("output_metadata", "latest_rebuild_failure_reason")
    op.drop_column("output_metadata", "latest_rebuild_status")
    op.drop_column("output_metadata", "rebuild_job_key")
    op.drop_column("output_metadata", "stale_reason")
    op.drop_column("output_metadata", "rebuilt_at")
    op.drop_column("output_metadata", "invalidated_at")
    op.drop_column("output_metadata", "source_bundle_ref")
    op.drop_column("output_metadata", "source_version_refs")
    op.drop_column("output_metadata", "cached_payload")
