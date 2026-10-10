"""Add immutable Explore comparisons and Decision provenance.

Revision ID: 0045_explore_comparisons
Revises: 0044_explore_measurement_events
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0045_explore_comparisons"
down_revision = "0044_explore_measurement_events"
branch_labels = None
depends_on = None

_NEW_EVENT_TYPES = (
    "comparison_generated",
    "comparison_saved",
    "prioritize_initiated",
    "prioritize_completed",
    "comparison_recommendation_overridden",
    "comparison_recommendation_viewed",
    "comparison_abstained_viewed",
)
_EXISTING_EVENT_TYPES = (
    "explore_context_evaluated",
    "explore_fit_generated",
    "explore_fit_abstained",
    "explore_context_unsupported",
    "recommendation_generated",
    "decision_considered",
    "decision_saved",
    "recommendation_changed_decision",
    "user_acted",
    "action_succeeded",
    "outcome_recorded",
    "reflection_recorded",
    "strategy_changed",
    "onboarding_started",
    "onboarding_completed",
    "career_identity_sufficient",
    "decision_created",
    "recommendation_viewed",
    "recommendation_feedback_submitted",
    "action_created",
    "application_recorded",
    "outcome_updated",
    "user_returned",
    "coverage_limitation_viewed",
    "trust_explanation_viewed",
    "commercial_offer_exposed",
    "commercial_offer_interest_recorded",
    "commercial_conversion_recorded",
    "support_case_created",
    "support_case_status_changed",
)
_RECOMMENDATION_STATES = (
    "clear_recommendation",
    "near_tie",
    "exact_tie",
    "insufficient_evidence",
    "blocking_contradiction",
    "unsupported_member",
    "outside_constraints",
)


def _constraint_sql(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    op.create_table(
        "explore_comparison_snapshots",
        sa.Column("comparison_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("snapshot_schema_version", sa.Integer(), nullable=False),
        sa.Column("comparison_identity", sa.String(length=80), nullable=False),
        sa.Column("selected_region_ids", sa.JSON(), nullable=False),
        sa.Column("selected_public_slugs", sa.JSON(), nullable=False),
        sa.Column("context_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("effective_context_summary", sa.JSON(), nullable=False),
        sa.Column("recommendation_state", sa.String(length=40), nullable=False),
        sa.Column("winner_region_ids", sa.JSON(), nullable=False),
        sa.Column("tie_region_ids", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("evidence_authority_version", sa.String(length=80), nullable=False),
        sa.Column("evidence_bundle", sa.String(length=80), nullable=False),
        sa.Column("calibration_version", sa.String(length=64), nullable=False),
        sa.Column("snapshot_payload", sa.JSON(), nullable=False),
        sa.Column("recommendation_summary", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "snapshot_schema_version >= 1", name="ck_explore_comparison_schema_version"
        ),
        sa.CheckConstraint(
            _constraint_sql("recommendation_state", _RECOMMENDATION_STATES),
            name="ck_explore_comparison_recommendation_state",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("comparison_id"),
        sa.UniqueConstraint(
            "user_id", "comparison_identity", name="uq_explore_comparison_user_identity"
        ),
    )
    op.create_index(
        "ix_explore_comparison_context",
        "explore_comparison_snapshots",
        ["context_fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_explore_comparison_user_generated",
        "explore_comparison_snapshots",
        ["user_id", "generated_at"],
        unique=False,
    )
    op.create_index(
        "ix_explore_comparison_user_saved",
        "explore_comparison_snapshots",
        ["user_id", "saved_at"],
        unique=False,
    )

    op.create_table(
        "explore_decision_provenance",
        sa.Column("provenance_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("comparison_id", sa.String(length=64), nullable=False),
        sa.Column("context_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("market_set_fingerprint", sa.String(length=80), nullable=False),
        sa.Column("system_recommendation_state", sa.String(length=40), nullable=False),
        sa.Column("system_recommended_region_ids", sa.JSON(), nullable=False),
        sa.Column("user_selected_region_id", sa.String(length=64), nullable=False),
        sa.Column("choice_matches_recommendation", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparison_id"], ["explore_comparison_snapshots.comparison_id"]),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["user_selected_region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("provenance_id"),
        sa.UniqueConstraint("decision_id", name="uq_explore_decision_provenance_decision"),
    )
    op.create_index(
        "ix_explore_decision_provenance_comparison",
        "explore_decision_provenance",
        ["comparison_id"],
        unique=False,
    )
    op.create_index(
        "ix_explore_decision_provenance_equivalent",
        "explore_decision_provenance",
        ["user_id", "context_fingerprint", "market_set_fingerprint", "user_selected_region_id"],
        unique=False,
    )
    op.create_index(
        "ix_explore_decision_provenance_user",
        "explore_decision_provenance",
        ["user_id"],
        unique=False,
    )

    with op.batch_alter_table("product_analytics_events") as batch_op:
        batch_op.drop_constraint("ck_product_events_type", type_="check")
        batch_op.create_check_constraint(
            "ck_product_events_type",
            _constraint_sql("event_type", (*_NEW_EVENT_TYPES, *_EXISTING_EVENT_TYPES)),
        )


def downgrade() -> None:
    connection = op.get_bind()
    count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM product_analytics_events WHERE event_type IN :event_types"
        ).bindparams(sa.bindparam("event_types", expanding=True)),
        {"event_types": _NEW_EVENT_TYPES},
    ).scalar_one()
    if count:
        raise RuntimeError(
            "0045 downgrade requires comparison analytics events to be archived first"
        )
    with op.batch_alter_table("product_analytics_events") as batch_op:
        batch_op.drop_constraint("ck_product_events_type", type_="check")
        batch_op.create_check_constraint(
            "ck_product_events_type",
            _constraint_sql("event_type", _EXISTING_EVENT_TYPES),
        )
    op.drop_index("ix_explore_decision_provenance_user", table_name="explore_decision_provenance")
    op.drop_index(
        "ix_explore_decision_provenance_equivalent",
        table_name="explore_decision_provenance",
    )
    op.drop_index(
        "ix_explore_decision_provenance_comparison",
        table_name="explore_decision_provenance",
    )
    op.drop_table("explore_decision_provenance")
    op.drop_index("ix_explore_comparison_user_saved", table_name="explore_comparison_snapshots")
    op.drop_index("ix_explore_comparison_user_generated", table_name="explore_comparison_snapshots")
    op.drop_index("ix_explore_comparison_context", table_name="explore_comparison_snapshots")
    op.drop_table("explore_comparison_snapshots")
