"""Add Layer 37 deep decision intelligence.

Revision ID: 0038_deep_decision_intelligence
Revises: 0037_complete_decision_outcome_backend
Create Date: 2026-09-02
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0038_deep_decision_intelligence"
down_revision = "0037_complete_decision_outcome_backend"
branch_labels = None
depends_on = None

FACTOR_CATEGORY_SQL = (
    "'benefit', 'cost', 'risk', 'time', 'confidence', 'uncertainty', "
    "'user_importance', 'evidence_strength', 'reversibility'"
)
FACTOR_DIRECTION_SQL = "'positive', 'negative', 'neutral', 'mixed', 'unknown'"
FACTOR_EVIDENCE_KIND_SQL = "'direct', 'derived', 'inferred', 'proxy', 'unavailable', 'conflicting'"
FACTOR_CONFIDENCE_SQL = "'high', 'medium', 'low', 'unknown'"
FACTOR_FRESHNESS_SQL = "'fresh', 'stale', 'partial', 'unknown'"
ADVISORY_SEVERITY_SQL = "'info', 'watch', 'warning', 'blocking'"
ADVISORY_SUPPORT_SQL = "'supported', 'weakly_supported', 'unresolved'"
EVOLUTION_CHANGE_SQL = (
    "'none', 'user_changed', 'goal_changed', 'career_identity_changed', "
    "'market_changed', 'evidence_changed', 'outcome_changed', "
    "'confidence_changed', 'stale_prior', 'superseded'"
)
STRATEGIC_REVIEW_STATUS_SQL = "'generated', 'archived'"


def upgrade() -> None:
    op.create_table(
        "decision_factors",
        sa.Column("factor_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("option_id", sa.String(length=64), nullable=True),
        sa.Column("recommendation_id", sa.String(length=64), nullable=True),
        sa.Column("context_snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("factor_key", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("normalized_value", sa.JSON(), nullable=True),
        sa.Column("raw_value", sa.JSON(), nullable=True),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("uncertainty", sa.String(length=64), nullable=False),
        sa.Column("evidence_strength", sa.String(length=64), nullable=False),
        sa.Column("evidence_kind", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("caveats", sa.JSON(), nullable=False),
        sa.Column("freshness_status", sa.String(length=32), nullable=False),
        sa.Column("freshness_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"category IN ({FACTOR_CATEGORY_SQL})",
            name="ck_decision_factors_category",
        ),
        sa.CheckConstraint(
            f"direction IN ({FACTOR_DIRECTION_SQL})",
            name="ck_decision_factors_direction",
        ),
        sa.CheckConstraint(
            f"evidence_kind IN ({FACTOR_EVIDENCE_KIND_SQL})",
            name="ck_decision_factors_evidence_kind",
        ),
        sa.CheckConstraint(
            f"confidence IN ({FACTOR_CONFIDENCE_SQL})",
            name="ck_decision_factors_confidence",
        ),
        sa.CheckConstraint(
            f"freshness_status IN ({FACTOR_FRESHNESS_SQL})",
            name="ck_decision_factors_freshness",
        ),
        sa.CheckConstraint(
            "importance IS NULL OR importance BETWEEN 1 AND 5",
            name="ck_decision_factors_importance",
        ),
        sa.ForeignKeyConstraint(
            ["context_snapshot_id"], ["decision_context_snapshots.context_snapshot_id"]
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(["option_id"], ["decision_options.option_id"]),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["decision_recommendations.recommendation_id"]
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("factor_id"),
    )
    op.create_index(
        "ix_decision_factors_decision_domain",
        "decision_factors",
        ["decision_id", "domain"],
        unique=False,
    )
    op.create_index("ix_decision_factors_option", "decision_factors", ["option_id"], unique=False)
    op.create_index(
        "ix_decision_factors_recommendation",
        "decision_factors",
        ["recommendation_id"],
        unique=False,
    )
    op.create_index(
        "ix_decision_factors_user_generated",
        "decision_factors",
        ["user_id", "generated_at"],
        unique=False,
    )

    op.create_table(
        "longitudinal_context_snapshots",
        sa.Column("longitudinal_context_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("context_payload", sa.JSON(), nullable=False),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "record_count >= 0",
            name="ck_longitudinal_context_record_count",
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("longitudinal_context_id"),
    )
    op.create_index(
        "ix_longitudinal_context_decision",
        "longitudinal_context_snapshots",
        ["decision_id"],
        unique=False,
    )
    op.create_index(
        "ix_longitudinal_context_user_generated",
        "longitudinal_context_snapshots",
        ["user_id", "generated_at"],
        unique=False,
    )

    op.create_table(
        "decision_recommendation_evolutions",
        sa.Column("evolution_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("previous_recommendation_id", sa.String(length=64), nullable=True),
        sa.Column("current_recommendation_id", sa.String(length=64), nullable=True),
        sa.Column("change_type", sa.String(length=64), nullable=False),
        sa.Column("meaningful_changes", sa.JSON(), nullable=False),
        sa.Column("confidence_before", sa.String(length=32), nullable=True),
        sa.Column("confidence_after", sa.String(length=32), nullable=True),
        sa.Column("evidence_basis", sa.JSON(), nullable=False),
        sa.Column("uncertainty", sa.String(length=64), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"change_type IN ({EVOLUTION_CHANGE_SQL})",
            name="ck_recommendation_evolutions_change",
        ),
        sa.CheckConstraint(
            f"confidence_before IS NULL OR confidence_before IN ({FACTOR_CONFIDENCE_SQL})",
            name="ck_recommendation_evolutions_conf_before",
        ),
        sa.CheckConstraint(
            f"confidence_after IS NULL OR confidence_after IN ({FACTOR_CONFIDENCE_SQL})",
            name="ck_recommendation_evolutions_conf_after",
        ),
        sa.ForeignKeyConstraint(
            ["current_recommendation_id"], ["decision_recommendations.recommendation_id"]
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(
            ["previous_recommendation_id"], ["decision_recommendations.recommendation_id"]
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("evolution_id"),
    )
    op.create_index(
        "ix_recommendation_evolutions_decision",
        "decision_recommendation_evolutions",
        ["decision_id", "generated_at"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_evolutions_user",
        "decision_recommendation_evolutions",
        ["user_id", "generated_at"],
        unique=False,
    )

    op.create_table(
        "decision_advisory_findings",
        sa.Column("advisory_finding_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=True),
        sa.Column("finding_type", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("support_status", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("uncertainty", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("affected_goal", sa.String(length=255), nullable=True),
        sa.Column("supporting_evidence", sa.JSON(), nullable=False),
        sa.Column("counter_evidence", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"severity IN ({ADVISORY_SEVERITY_SQL})",
            name="ck_advisory_findings_severity",
        ),
        sa.CheckConstraint(
            f"support_status IN ({ADVISORY_SUPPORT_SQL})",
            name="ck_advisory_findings_support",
        ),
        sa.CheckConstraint(
            f"confidence IN ({FACTOR_CONFIDENCE_SQL})",
            name="ck_advisory_findings_confidence",
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("advisory_finding_id"),
    )
    op.create_index(
        "ix_advisory_findings_decision",
        "decision_advisory_findings",
        ["decision_id", "generated_at"],
        unique=False,
    )
    op.create_index(
        "ix_advisory_findings_type",
        "decision_advisory_findings",
        ["finding_type"],
        unique=False,
    )
    op.create_index(
        "ix_advisory_findings_user_status",
        "decision_advisory_findings",
        ["user_id", "support_status"],
        unique=False,
    )

    op.create_table(
        "strategic_career_reviews",
        sa.Column("strategic_review_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=True),
        sa.Column("longitudinal_context_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("goals", sa.JSON(), nullable=False),
        sa.Column("strategy_performance", sa.JSON(), nullable=False),
        sa.Column("application_summary", sa.JSON(), nullable=False),
        sa.Column("outcome_summary", sa.JSON(), nullable=False),
        sa.Column("identity_changes", sa.JSON(), nullable=False),
        sa.Column("market_changes", sa.JSON(), nullable=False),
        sa.Column("recommendation_changes", sa.JSON(), nullable=False),
        sa.Column("active_risks", sa.JSON(), nullable=False),
        sa.Column("blind_spots", sa.JSON(), nullable=False),
        sa.Column("suggested_next_actions", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("uncertainty", sa.String(length=64), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"status IN ({STRATEGIC_REVIEW_STATUS_SQL})",
            name="ck_strategic_reviews_status",
        ),
        sa.CheckConstraint(
            f"confidence IN ({FACTOR_CONFIDENCE_SQL})",
            name="ck_strategic_reviews_confidence",
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(
            ["longitudinal_context_id"],
            ["longitudinal_context_snapshots.longitudinal_context_id"],
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("strategic_review_id"),
    )
    op.create_index(
        "ix_strategic_reviews_context",
        "strategic_career_reviews",
        ["longitudinal_context_id"],
        unique=False,
    )
    op.create_index(
        "ix_strategic_reviews_decision",
        "strategic_career_reviews",
        ["decision_id", "generated_at"],
        unique=False,
    )
    op.create_index(
        "ix_strategic_reviews_user_generated",
        "strategic_career_reviews",
        ["user_id", "generated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_strategic_reviews_user_generated", table_name="strategic_career_reviews")
    op.drop_index("ix_strategic_reviews_decision", table_name="strategic_career_reviews")
    op.drop_index("ix_strategic_reviews_context", table_name="strategic_career_reviews")
    op.drop_table("strategic_career_reviews")

    op.drop_index("ix_advisory_findings_user_status", table_name="decision_advisory_findings")
    op.drop_index("ix_advisory_findings_type", table_name="decision_advisory_findings")
    op.drop_index("ix_advisory_findings_decision", table_name="decision_advisory_findings")
    op.drop_table("decision_advisory_findings")

    op.drop_index(
        "ix_recommendation_evolutions_user", table_name="decision_recommendation_evolutions"
    )
    op.drop_index(
        "ix_recommendation_evolutions_decision", table_name="decision_recommendation_evolutions"
    )
    op.drop_table("decision_recommendation_evolutions")

    op.drop_index(
        "ix_longitudinal_context_user_generated", table_name="longitudinal_context_snapshots"
    )
    op.drop_index("ix_longitudinal_context_decision", table_name="longitudinal_context_snapshots")
    op.drop_table("longitudinal_context_snapshots")

    op.drop_index("ix_decision_factors_user_generated", table_name="decision_factors")
    op.drop_index("ix_decision_factors_recommendation", table_name="decision_factors")
    op.drop_index("ix_decision_factors_option", table_name="decision_factors")
    op.drop_index("ix_decision_factors_decision_domain", table_name="decision_factors")
    op.drop_table("decision_factors")
