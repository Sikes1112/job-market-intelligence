"""Add Layer 23A opportunity infrastructure.

Revision ID: 0025_opportunity_infrastructure
Revises: 0024_platform_api_access_control
Create Date: 2026-06-24
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0025_opportunity_infrastructure"
down_revision = "0024_platform_api_access_control"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employer_programs",
        sa.Column("employer_program_id", sa.String(length=64), nullable=False),
        sa.Column("employer_id", sa.String(length=64), nullable=True),
        sa.Column("employer_name", sa.String(length=255), nullable=False),
        sa.Column("program_name", sa.String(length=255), nullable=False),
        sa.Column("program_type", sa.String(length=64), nullable=False),
        sa.Column("program_url", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "program_type IN ("
            "'apprenticeship', "
            "'co-op', "
            "'employer_program', "
            "'fellowship', "
            "'internship', "
            "'new_grad_role', "
            "'rotational_program', "
            "'unknown'"
            ")",
            name="ck_employer_programs_type",
        ),
        sa.ForeignKeyConstraint(["employer_id"], ["companies.company_id"]),
        sa.PrimaryKeyConstraint("employer_program_id"),
    )
    op.create_index(
        "ix_employer_programs_created_at",
        "employer_programs",
        ["created_at"],
    )
    op.create_index(
        "ix_employer_programs_employer",
        "employer_programs",
        ["employer_id"],
    )
    op.create_index(
        "ix_employer_programs_employer_name",
        "employer_programs",
        ["employer_name"],
    )
    op.create_index("ix_employer_programs_type", "employer_programs", ["program_type"])

    op.create_table(
        "opportunities",
        sa.Column("opportunity_id", sa.String(length=64), nullable=False),
        sa.Column("employer_program_id", sa.String(length=64), nullable=False),
        sa.Column("employer_id", sa.String(length=64), nullable=True),
        sa.Column("employer_name", sa.String(length=255), nullable=False),
        sa.Column("program_name", sa.String(length=255), nullable=False),
        sa.Column("program_type", sa.String(length=64), nullable=False),
        sa.Column("location_mode", sa.String(length=32), nullable=False),
        sa.Column("seniority_level", sa.String(length=32), nullable=False),
        sa.Column("eligibility_summary", sa.Text(), nullable=True),
        sa.Column("application_url", sa.String(length=2048), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("application_open_date", sa.Date(), nullable=True),
        sa.Column("application_deadline", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("compensation_min", sa.Float(), nullable=True),
        sa.Column("compensation_max", sa.Float(), nullable=True),
        sa.Column("compensation_disclosed", sa.Boolean(), nullable=False),
        sa.Column("trust_label", sa.String(length=32), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "program_type IN ("
            "'apprenticeship', "
            "'co-op', "
            "'employer_program', "
            "'fellowship', "
            "'internship', "
            "'new_grad_role', "
            "'rotational_program', "
            "'unknown'"
            ")",
            name="ck_opportunities_program_type",
        ),
        sa.CheckConstraint(
            "location_mode IN ('hybrid', 'mixed', 'onsite', 'remote', 'unknown')",
            name="ck_opportunities_location_mode",
        ),
        sa.CheckConstraint(
            "seniority_level IN ("
            "'apprentice', "
            "'co-op', "
            "'early-career', "
            "'internship', "
            "'new-grad', "
            "'unknown'"
            ")",
            name="ck_opportunities_seniority_level",
        ),
        sa.CheckConstraint(
            "source_type IN ("
            "'career_center', "
            "'employer_official', "
            "'internal_review', "
            "'manual_research', "
            "'partner_submitted', "
            "'public_dataset', "
            "'unknown'"
            ")",
            name="ck_opportunities_source_type",
        ),
        sa.CheckConstraint(
            "trust_label IN ("
            "'expired', "
            "'partner_submitted', "
            "'rejected', "
            "'source_checked', "
            "'unverified', "
            "'verified'"
            ")",
            name="ck_opportunities_trust_label",
        ),
        sa.CheckConstraint(
            "review_status IN ("
            "'approved', "
            "'expired', "
            "'needs_correction', "
            "'pending_review', "
            "'rejected', "
            "'source_checked'"
            ")",
            name="ck_opportunities_review_status",
        ),
        sa.CheckConstraint(
            "compensation_min IS NULL OR compensation_min >= 0.0",
            name="ck_opportunities_compensation_min_nonnegative",
        ),
        sa.CheckConstraint(
            "compensation_max IS NULL OR compensation_max >= 0.0",
            name="ck_opportunities_compensation_max_nonnegative",
        ),
        sa.CheckConstraint(
            "compensation_min IS NULL OR compensation_max IS NULL "
            "OR compensation_max >= compensation_min",
            name="ck_opportunities_compensation_bounds",
        ),
        sa.ForeignKeyConstraint(["employer_id"], ["companies.company_id"]),
        sa.ForeignKeyConstraint(
            ["employer_program_id"],
            ["employer_programs.employer_program_id"],
        ),
        sa.PrimaryKeyConstraint("opportunity_id"),
    )
    op.create_index(
        "ix_opportunities_application_deadline",
        "opportunities",
        ["application_deadline"],
    )
    op.create_index("ix_opportunities_created_at", "opportunities", ["created_at"])
    op.create_index("ix_opportunities_employer", "opportunities", ["employer_id"])
    op.create_index(
        "ix_opportunities_employer_name",
        "opportunities",
        ["employer_name"],
    )
    op.create_index("ix_opportunities_expires_at", "opportunities", ["expires_at"])
    op.create_index(
        "ix_opportunities_location_mode",
        "opportunities",
        ["location_mode"],
    )
    op.create_index("ix_opportunities_program", "opportunities", ["employer_program_id"])
    op.create_index("ix_opportunities_program_type", "opportunities", ["program_type"])
    op.create_index(
        "ix_opportunities_review_status",
        "opportunities",
        ["review_status"],
    )
    op.create_index(
        "ix_opportunities_seniority_level",
        "opportunities",
        ["seniority_level"],
    )
    op.create_index("ix_opportunities_trust_label", "opportunities", ["trust_label"])

    op.create_table(
        "opportunity_sources",
        sa.Column("opportunity_source_id", sa.String(length=64), nullable=False),
        sa.Column("opportunity_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_type IN ("
            "'career_center', "
            "'employer_official', "
            "'internal_review', "
            "'manual_research', "
            "'partner_submitted', "
            "'public_dataset', "
            "'unknown'"
            ")",
            name="ck_opportunity_sources_type",
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.opportunity_id"]),
        sa.PrimaryKeyConstraint("opportunity_source_id"),
    )
    op.create_index(
        "ix_opportunity_sources_created_at",
        "opportunity_sources",
        ["created_at"],
    )
    op.create_index(
        "ix_opportunity_sources_opportunity",
        "opportunity_sources",
        ["opportunity_id"],
    )
    op.create_index("ix_opportunity_sources_type", "opportunity_sources", ["source_type"])

    op.create_table(
        "opportunity_region_bindings",
        sa.Column("opportunity_region_binding_id", sa.String(length=64), nullable=False),
        sa.Column("opportunity_id", sa.String(length=64), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=True),
        sa.Column("region_label", sa.String(length=128), nullable=False),
        sa.Column("metro_area", sa.String(length=128), nullable=True),
        sa.Column("binding_confidence", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "binding_confidence IN ('high', 'low', 'medium', 'unknown')",
            name="ck_opportunity_region_bindings_confidence",
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.opportunity_id"]),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("opportunity_region_binding_id"),
    )
    op.create_index(
        "ix_opportunity_region_bindings_created_at",
        "opportunity_region_bindings",
        ["created_at"],
    )
    op.create_index(
        "ix_opportunity_region_bindings_label",
        "opportunity_region_bindings",
        ["region_label"],
    )
    op.create_index(
        "ix_opportunity_region_bindings_opportunity",
        "opportunity_region_bindings",
        ["opportunity_id"],
    )
    op.create_index(
        "ix_opportunity_region_bindings_region",
        "opportunity_region_bindings",
        ["region_id"],
    )

    op.create_table(
        "opportunity_role_family_bindings",
        sa.Column(
            "opportunity_role_family_binding_id",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("opportunity_id", sa.String(length=64), nullable=False),
        sa.Column("role_family", sa.String(length=64), nullable=False),
        sa.Column("role_family_label", sa.String(length=128), nullable=True),
        sa.Column("binding_confidence", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "binding_confidence IN ('high', 'low', 'medium', 'unknown')",
            name="ck_opportunity_role_family_bindings_confidence",
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.opportunity_id"]),
        sa.PrimaryKeyConstraint("opportunity_role_family_binding_id"),
    )
    op.create_index(
        "ix_opportunity_role_family_bindings_created_at",
        "opportunity_role_family_bindings",
        ["created_at"],
    )
    op.create_index(
        "ix_opportunity_role_family_bindings_opportunity",
        "opportunity_role_family_bindings",
        ["opportunity_id"],
    )
    op.create_index(
        "ix_opportunity_role_family_bindings_role",
        "opportunity_role_family_bindings",
        ["role_family"],
    )

    op.create_table(
        "employer_influence_metadata",
        sa.Column("employer_influence_metadata_id", sa.String(length=64), nullable=False),
        sa.Column("opportunity_id", sa.String(length=64), nullable=False),
        sa.Column("partner_submitted", sa.Boolean(), nullable=False),
        sa.Column("paid_partner", sa.Boolean(), nullable=False),
        sa.Column("ranking_influence_allowed", sa.Boolean(), nullable=False),
        sa.Column("submitted_by_partner_id", sa.String(length=64), nullable=True),
        sa.Column("paid_partner_label", sa.String(length=128), nullable=True),
        sa.Column("internal_review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ranking_influence_allowed = false",
            name="ck_employer_influence_metadata_no_ranking_influence",
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.opportunity_id"]),
        sa.PrimaryKeyConstraint("employer_influence_metadata_id"),
        sa.UniqueConstraint(
            "opportunity_id",
            name="uq_employer_influence_metadata_opportunity",
        ),
    )
    op.create_index(
        "ix_employer_influence_metadata_created_at",
        "employer_influence_metadata",
        ["created_at"],
    )
    op.create_index(
        "ix_employer_influence_metadata_opportunity",
        "employer_influence_metadata",
        ["opportunity_id"],
    )
    op.create_index(
        "ix_employer_influence_metadata_paid",
        "employer_influence_metadata",
        ["paid_partner"],
    )
    op.create_index(
        "ix_employer_influence_metadata_partner",
        "employer_influence_metadata",
        ["partner_submitted"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_employer_influence_metadata_partner",
        table_name="employer_influence_metadata",
    )
    op.drop_index(
        "ix_employer_influence_metadata_paid",
        table_name="employer_influence_metadata",
    )
    op.drop_index(
        "ix_employer_influence_metadata_opportunity",
        table_name="employer_influence_metadata",
    )
    op.drop_index(
        "ix_employer_influence_metadata_created_at",
        table_name="employer_influence_metadata",
    )
    op.drop_table("employer_influence_metadata")

    op.drop_index(
        "ix_opportunity_role_family_bindings_role",
        table_name="opportunity_role_family_bindings",
    )
    op.drop_index(
        "ix_opportunity_role_family_bindings_opportunity",
        table_name="opportunity_role_family_bindings",
    )
    op.drop_index(
        "ix_opportunity_role_family_bindings_created_at",
        table_name="opportunity_role_family_bindings",
    )
    op.drop_table("opportunity_role_family_bindings")

    op.drop_index(
        "ix_opportunity_region_bindings_region",
        table_name="opportunity_region_bindings",
    )
    op.drop_index(
        "ix_opportunity_region_bindings_opportunity",
        table_name="opportunity_region_bindings",
    )
    op.drop_index(
        "ix_opportunity_region_bindings_label",
        table_name="opportunity_region_bindings",
    )
    op.drop_index(
        "ix_opportunity_region_bindings_created_at",
        table_name="opportunity_region_bindings",
    )
    op.drop_table("opportunity_region_bindings")

    op.drop_index("ix_opportunity_sources_type", table_name="opportunity_sources")
    op.drop_index(
        "ix_opportunity_sources_opportunity",
        table_name="opportunity_sources",
    )
    op.drop_index(
        "ix_opportunity_sources_created_at",
        table_name="opportunity_sources",
    )
    op.drop_table("opportunity_sources")

    op.drop_index("ix_opportunities_trust_label", table_name="opportunities")
    op.drop_index("ix_opportunities_seniority_level", table_name="opportunities")
    op.drop_index("ix_opportunities_review_status", table_name="opportunities")
    op.drop_index("ix_opportunities_program_type", table_name="opportunities")
    op.drop_index("ix_opportunities_program", table_name="opportunities")
    op.drop_index("ix_opportunities_location_mode", table_name="opportunities")
    op.drop_index("ix_opportunities_expires_at", table_name="opportunities")
    op.drop_index("ix_opportunities_employer_name", table_name="opportunities")
    op.drop_index("ix_opportunities_employer", table_name="opportunities")
    op.drop_index("ix_opportunities_created_at", table_name="opportunities")
    op.drop_index(
        "ix_opportunities_application_deadline",
        table_name="opportunities",
    )
    op.drop_table("opportunities")

    op.drop_index("ix_employer_programs_type", table_name="employer_programs")
    op.drop_index(
        "ix_employer_programs_employer_name",
        table_name="employer_programs",
    )
    op.drop_index("ix_employer_programs_employer", table_name="employer_programs")
    op.drop_index("ix_employer_programs_created_at", table_name="employer_programs")
    op.drop_table("employer_programs")
