"""Add audit finding review lifecycle.

Revision ID: 0009_audit_finding_lifecycle
Revises: 0008_admin_roles_event_log
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0009_audit_finding_lifecycle"
down_revision = "0008_admin_roles_event_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_finding_reviews",
        sa.Column("finding_id", sa.String(length=255), nullable=False),
        sa.Column("review_state", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("scope_type", sa.String(length=64), nullable=True),
        sa.Column("scope_ref", sa.String(length=255), nullable=True),
        sa.Column("message", sa.String(length=2048), nullable=True),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("recommendation", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_transitioned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_transition_actor", sa.String(length=128), nullable=True),
        sa.Column("last_transition_role", sa.String(length=32), nullable=True),
        sa.Column("last_transition_reason", sa.String(length=2048), nullable=True),
        sa.CheckConstraint(
            "review_state IN ('open', 'acknowledged', 'resolved', 'dismissed', 'escalated')",
            name="ck_audit_finding_reviews_state",
        ),
        sa.PrimaryKeyConstraint("finding_id"),
    )
    op.create_index(
        "ix_audit_finding_reviews_category",
        "audit_finding_reviews",
        ["category"],
    )
    op.create_index(
        "ix_audit_finding_reviews_scope",
        "audit_finding_reviews",
        ["scope_type", "scope_ref"],
    )
    op.create_index(
        "ix_audit_finding_reviews_state",
        "audit_finding_reviews",
        ["review_state"],
    )
    op.create_index(
        "ix_audit_finding_reviews_updated_at",
        "audit_finding_reviews",
        ["updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audit_finding_reviews_updated_at",
        table_name="audit_finding_reviews",
    )
    op.drop_index(
        "ix_audit_finding_reviews_state",
        table_name="audit_finding_reviews",
    )
    op.drop_index(
        "ix_audit_finding_reviews_scope",
        table_name="audit_finding_reviews",
    )
    op.drop_index(
        "ix_audit_finding_reviews_category",
        table_name="audit_finding_reviews",
    )
    op.drop_table("audit_finding_reviews")

