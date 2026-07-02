"""Add Layer 17 partner import governance records.

Revision ID: 0018_partner_import_governance
Revises: 0017_ecosystem_integrations_foundation
Create Date: 2026-06-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0018_partner_import_governance"
down_revision = "0017_ecosystem_integrations_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "partner_import_batches",
        sa.Column("partner_import_batch_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_user_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("import_format", sa.String(length=16), nullable=False),
        sa.Column("source_attribution", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("raw_payload_text", sa.Text(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("accepted_record_count", sa.Integer(), nullable=False),
        sa.Column("quarantined_record_count", sa.Integer(), nullable=False),
        sa.Column("rejected_record_count", sa.Integer(), nullable=False),
        sa.Column("validation_result_json", sa.JSON(), nullable=False),
        sa.Column("receipt_json", sa.JSON(), nullable=False),
        sa.Column("governance_warnings_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_type IN ("
            "'local_employer_list', "
            "'internship_partner_list', "
            "'regional_workforce_data', "
            "'aggregated_career_center_outcome_data'"
            ")",
            name="ck_partner_import_batches_source_type",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'uploaded', "
            "'validated', "
            "'needs_review', "
            "'accepted', "
            "'partially_accepted', "
            "'rejected', "
            "'archived', "
            "'quarantined'"
            ")",
            name="ck_partner_import_batches_status",
        ),
        sa.CheckConstraint(
            "import_format IN ('csv', 'json')",
            name="ck_partner_import_batches_format",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"]),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("partner_import_batch_id"),
    )
    op.create_index(
        "ix_partner_import_batches_created_at",
        "partner_import_batches",
        ["created_at"],
    )
    op.create_index(
        "ix_partner_import_batches_org",
        "partner_import_batches",
        ["organization_id"],
    )
    op.create_index(
        "ix_partner_import_batches_source_type",
        "partner_import_batches",
        ["source_type"],
    )
    op.create_index(
        "ix_partner_import_batches_status",
        "partner_import_batches",
        ["status"],
    )
    op.create_index(
        "ix_partner_import_batches_uploader",
        "partner_import_batches",
        ["uploaded_by_user_id"],
    )

    op.create_table(
        "partner_import_records",
        sa.Column("partner_import_record_id", sa.String(length=64), nullable=False),
        sa.Column("partner_import_batch_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("record_index", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=96), nullable=False),
        sa.Column("record_status", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("source_attribution", sa.String(length=512), nullable=False),
        sa.Column("employer_name", sa.String(length=255), nullable=True),
        sa.Column("normalized_employer_name", sa.String(length=255), nullable=True),
        sa.Column("region_label", sa.String(length=255), nullable=True),
        sa.Column("normalized_region_id", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("freshness_status", sa.String(length=64), nullable=False),
        sa.Column("partner_payload_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("validation_warnings_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_type IN ("
            "'local_employer_list', "
            "'internship_partner_list', "
            "'regional_workforce_data', "
            "'aggregated_career_center_outcome_data'"
            ")",
            name="ck_partner_import_records_source_type",
        ),
        sa.CheckConstraint(
            "record_status IN ("
            "'accepted', "
            "'needs_review', "
            "'rejected', "
            "'quarantined', "
            "'archived'"
            ")",
            name="ck_partner_import_records_status",
        ),
        sa.CheckConstraint(
            "decision IN ('accept', 'needs_review', 'reject', 'quarantine')",
            name="ck_partner_import_records_decision",
        ),
        sa.CheckConstraint(
            "confidence IN ('high', 'medium', 'low', 'unknown', 'unverified', 'blocked')",
            name="ck_partner_import_records_confidence",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"]),
        sa.ForeignKeyConstraint(
            ["partner_import_batch_id"],
            ["partner_import_batches.partner_import_batch_id"],
        ),
        sa.PrimaryKeyConstraint("partner_import_record_id"),
    )
    op.create_index(
        "ix_partner_import_records_batch",
        "partner_import_records",
        ["partner_import_batch_id"],
    )
    op.create_index(
        "ix_partner_import_records_employer",
        "partner_import_records",
        ["normalized_employer_name"],
    )
    op.create_index(
        "ix_partner_import_records_org",
        "partner_import_records",
        ["organization_id"],
    )
    op.create_index(
        "ix_partner_import_records_region",
        "partner_import_records",
        ["normalized_region_id"],
    )
    op.create_index(
        "ix_partner_import_records_status",
        "partner_import_records",
        ["record_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_partner_import_records_status", table_name="partner_import_records")
    op.drop_index("ix_partner_import_records_region", table_name="partner_import_records")
    op.drop_index("ix_partner_import_records_org", table_name="partner_import_records")
    op.drop_index("ix_partner_import_records_employer", table_name="partner_import_records")
    op.drop_index("ix_partner_import_records_batch", table_name="partner_import_records")
    op.drop_table("partner_import_records")

    op.drop_index("ix_partner_import_batches_uploader", table_name="partner_import_batches")
    op.drop_index("ix_partner_import_batches_status", table_name="partner_import_batches")
    op.drop_index("ix_partner_import_batches_source_type", table_name="partner_import_batches")
    op.drop_index("ix_partner_import_batches_org", table_name="partner_import_batches")
    op.drop_index("ix_partner_import_batches_created_at", table_name="partner_import_batches")
    op.drop_table("partner_import_batches")
