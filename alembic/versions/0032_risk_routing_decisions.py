"""Add Layer 30B risk routing decision snapshots.

Revision ID: 0032_risk_routing_decisions
Revises: 0031_trust_assessments
Create Date: 2026-07-03
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0032_risk_routing_decisions"
down_revision = "0031_trust_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risk_routing_decisions",
        sa.Column("risk_routing_decision_id", sa.String(length=128), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("trust_assessment_id", sa.String(length=128), nullable=True),
        sa.Column("trust_tier", sa.String(length=64), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("routing_outcome", sa.String(length=64), nullable=False),
        sa.Column("routing_reasons_json", sa.JSON(), nullable=False),
        sa.Column("ranking_influence_decision", sa.String(length=32), nullable=False),
        sa.Column("ranking_influence_allowed", sa.Boolean(), nullable=False),
        sa.Column("ranking_influence_reason", sa.String(length=512), nullable=False),
        sa.Column("ranking_influence_reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("evidence_requirements_met_json", sa.JSON(), nullable=False),
        sa.Column("evidence_requirements_missing_json", sa.JSON(), nullable=False),
        sa.Column("evidence_requirements_failed_json", sa.JSON(), nullable=False),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("decision_source", sa.String(length=128), nullable=False),
        sa.Column("decision_version", sa.String(length=64), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("risk_routing_decision_id"),
        sa.UniqueConstraint(
            "subject_type",
            "subject_id",
            "decision_version",
            "decided_at",
            name="uq_risk_routing_decisions_subject_version_time",
        ),
    )
    op.create_index(
        "ix_risk_routing_decisions_subject",
        "risk_routing_decisions",
        ["subject_type", "subject_id"],
    )
    op.create_index(
        "ix_risk_routing_decisions_risk",
        "risk_routing_decisions",
        ["risk_level"],
    )
    op.create_index(
        "ix_risk_routing_decisions_outcome",
        "risk_routing_decisions",
        ["routing_outcome"],
    )
    op.create_index(
        "ix_risk_routing_decisions_ranking_allowed",
        "risk_routing_decisions",
        ["ranking_influence_allowed"],
    )
    op.create_index(
        "ix_risk_routing_decisions_decided_at",
        "risk_routing_decisions",
        ["decided_at"],
    )
    op.create_index(
        "ix_risk_routing_decisions_created_at",
        "risk_routing_decisions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_risk_routing_decisions_created_at",
        table_name="risk_routing_decisions",
    )
    op.drop_index(
        "ix_risk_routing_decisions_decided_at",
        table_name="risk_routing_decisions",
    )
    op.drop_index(
        "ix_risk_routing_decisions_ranking_allowed",
        table_name="risk_routing_decisions",
    )
    op.drop_index(
        "ix_risk_routing_decisions_outcome",
        table_name="risk_routing_decisions",
    )
    op.drop_index(
        "ix_risk_routing_decisions_risk",
        table_name="risk_routing_decisions",
    )
    op.drop_index(
        "ix_risk_routing_decisions_subject",
        table_name="risk_routing_decisions",
    )
    op.drop_table("risk_routing_decisions")
