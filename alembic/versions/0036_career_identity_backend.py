"""Add Layer 35A career identity backend tables.

Revision ID: 0036_career_identity_backend
Revises: 0035_curated_import_metadata
Create Date: 2026-08-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0036_career_identity_backend"
down_revision = "0035_curated_import_metadata"
branch_labels = None
depends_on = None

CAREER_IDENTITY_FACT_TYPE_SQL = (
    "'education', "
    "'experience', "
    "'skill', "
    "'project', "
    "'credential', "
    "'career_goal', "
    "'role_preference', "
    "'industry_preference', "
    "'geographic_constraint', "
    "'compensation_constraint', "
    "'timing_preference', "
    "'work_arrangement_preference'"
)


def upgrade() -> None:
    op.create_table(
        "career_identities",
        sa.Column("career_identity_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("completeness_state", sa.String(length=32), nullable=False),
        sa.Column("sufficiency_state", sa.String(length=32), nullable=False),
        sa.Column("completeness_snapshot", sa.JSON(), nullable=True),
        sa.Column("ingestion_consent_granted", sa.Boolean(), nullable=False),
        sa.Column("inference_consent_granted", sa.Boolean(), nullable=False),
        sa.Column(
            "downstream_personalization_consent_granted",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column("retain_import_metadata", sa.Boolean(), nullable=False),
        sa.Column("privacy_visibility", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("current_version >= 1", name="ck_career_identities_version"),
        sa.CheckConstraint(
            "completeness_state IN ('empty', 'minimal', 'partial', 'complete')",
            name="ck_career_identities_completeness_state",
        ),
        sa.CheckConstraint(
            "sufficiency_state IN ('insufficient', 'sufficient')",
            name="ck_career_identities_sufficiency_state",
        ),
        sa.CheckConstraint(
            "privacy_visibility = 'private'",
            name="ck_career_identities_private_visibility",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("career_identity_id"),
        sa.UniqueConstraint("user_id", name="uq_career_identities_user_id"),
    )
    op.create_index(
        "ix_career_identities_user_id",
        "career_identities",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "career_identity_imports",
        sa.Column("career_identity_import_id", sa.String(length=64), nullable=False),
        sa.Column("career_identity_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_label", sa.String(length=255), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("artifact_metadata", sa.JSON(), nullable=True),
        sa.Column("import_status", sa.String(length=32), nullable=False),
        sa.Column("diagnostics", sa.JSON(), nullable=False),
        sa.Column("imported_fact_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "import_status IN ('completed', 'failed')",
            name="ck_career_identity_imports_status",
        ),
        sa.ForeignKeyConstraint(
            ["career_identity_id"],
            ["career_identities.career_identity_id"],
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("career_identity_import_id"),
        sa.UniqueConstraint(
            "career_identity_id",
            "content_hash",
            name="uq_career_identity_imports_identity_hash",
        ),
    )
    op.create_index(
        "ix_career_identity_imports_hash",
        "career_identity_imports",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        "ix_career_identity_imports_identity",
        "career_identity_imports",
        ["career_identity_id"],
        unique=False,
    )
    op.create_index(
        "ix_career_identity_imports_user_id",
        "career_identity_imports",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "career_identity_facts",
        sa.Column("career_identity_fact_id", sa.String(length=64), nullable=False),
        sa.Column("career_identity_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("fact_type", sa.String(length=64), nullable=False),
        sa.Column("normalized_key", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("source_import_id", sa.String(length=64), nullable=True),
        sa.Column("source_label", sa.String(length=255), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"fact_type IN ({CAREER_IDENTITY_FACT_TYPE_SQL})",
            name="ck_career_identity_facts_type",
        ),
        sa.CheckConstraint(
            "state IN ('explicit', 'imported', 'inferred', 'confirmed')",
            name="ck_career_identity_facts_state",
        ),
        sa.CheckConstraint(
            "normalized_key <> ''",
            name="ck_career_identity_facts_normalized_key",
        ),
        sa.ForeignKeyConstraint(
            ["career_identity_id"],
            ["career_identities.career_identity_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_import_id"],
            ["career_identity_imports.career_identity_import_id"],
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("career_identity_fact_id"),
        sa.UniqueConstraint(
            "career_identity_id",
            "fact_type",
            "normalized_key",
            name="uq_career_identity_facts_identity_type_key",
        ),
    )
    op.create_index(
        "ix_career_identity_facts_identity",
        "career_identity_facts",
        ["career_identity_id"],
        unique=False,
    )
    op.create_index(
        "ix_career_identity_facts_type",
        "career_identity_facts",
        ["fact_type"],
        unique=False,
    )
    op.create_index(
        "ix_career_identity_facts_user_id",
        "career_identity_facts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_career_identity_facts_user_type",
        "career_identity_facts",
        ["user_id", "fact_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_career_identity_facts_user_type", table_name="career_identity_facts")
    op.drop_index("ix_career_identity_facts_user_id", table_name="career_identity_facts")
    op.drop_index("ix_career_identity_facts_type", table_name="career_identity_facts")
    op.drop_index("ix_career_identity_facts_identity", table_name="career_identity_facts")
    op.drop_table("career_identity_facts")

    op.drop_index("ix_career_identity_imports_user_id", table_name="career_identity_imports")
    op.drop_index("ix_career_identity_imports_identity", table_name="career_identity_imports")
    op.drop_index("ix_career_identity_imports_hash", table_name="career_identity_imports")
    op.drop_table("career_identity_imports")

    op.drop_index("ix_career_identities_user_id", table_name="career_identities")
    op.drop_table("career_identities")
