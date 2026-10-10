"""Add beta-critical concurrency boundaries and funnel events.

Revision ID: 0046_beta_production_hardening
Revises: 0045_explore_comparisons
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0046_beta_production_hardening"
down_revision = "0045_explore_comparisons"
branch_labels = None
depends_on = None

_NEW_EVENT_TYPES = (
    "authenticated_visit",
    "market_inspected",
    "comparison_selection_ready",
    "my_search_viewed",
)
_ALL_EVENT_TYPES = (
    *_NEW_EVENT_TYPES,
    "explore_context_evaluated",
    "explore_fit_generated",
    "explore_fit_abstained",
    "explore_context_unsupported",
    "comparison_generated",
    "comparison_saved",
    "prioritize_initiated",
    "prioritize_completed",
    "comparison_recommendation_overridden",
    "comparison_recommendation_viewed",
    "comparison_abstained_viewed",
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


def _constraint_sql(values: tuple[str, ...]) -> str:
    return "event_type IN (" + ", ".join(f"'{value}'" for value in values) + ")"


def upgrade() -> None:
    with op.batch_alter_table("career_applications") as batch_op:
        batch_op.add_column(sa.Column("current_opportunity_id", sa.String(64), nullable=True))
        batch_op.create_foreign_key(
            "fk_career_applications_current_opportunity",
            "current_opportunities",
            ["current_opportunity_id"],
            ["current_opportunity_id"],
        )

    connection = op.get_bind()
    applications = sa.table(
        "career_applications",
        sa.column("application_id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("decision_id", sa.String),
        sa.column("metadata_json", sa.JSON),
        sa.column("current_opportunity_id", sa.String),
    )
    seen: dict[tuple[str, str | None, str], str] = {}
    backfill: list[tuple[str, str]] = []
    for row in connection.execute(
        sa.select(
            applications.c.application_id,
            applications.c.user_id,
            applications.c.decision_id,
            applications.c.metadata_json,
        )
    ).mappings():
        metadata = row["metadata_json"] if isinstance(row["metadata_json"], dict) else {}
        opportunity_id = metadata.get("current_opportunity_id")
        if not isinstance(opportunity_id, str) or not opportunity_id:
            continue
        identity = (row["user_id"], row["decision_id"], opportunity_id)
        if identity in seen:
            raise RuntimeError(
                "0046 requires duplicate tracked opportunities to be resolved before migration: "
                f"{seen[identity]} and {row['application_id']}"
            )
        seen[identity] = row["application_id"]
        backfill.append((row["application_id"], opportunity_id))
    for application_id, opportunity_id in backfill:
        connection.execute(
            applications.update()
            .where(applications.c.application_id == application_id)
            .values(current_opportunity_id=opportunity_id)
        )

    with op.batch_alter_table("career_applications") as batch_op:
        batch_op.create_unique_constraint(
            "uq_career_applications_pursuit_opportunity",
            ["user_id", "decision_id", "current_opportunity_id"],
        )

    op.create_index(
        "uq_career_action_plans_active_decision",
        "career_action_plans",
        ["decision_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )

    with op.batch_alter_table("product_analytics_events") as batch_op:
        batch_op.drop_constraint("ck_product_events_type", type_="check")
        batch_op.create_check_constraint(
            "ck_product_events_type", _constraint_sql(_ALL_EVENT_TYPES)
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
        raise RuntimeError("0046 downgrade requires new beta funnel events to be archived first")

    previous_event_types = tuple(
        value for value in _ALL_EVENT_TYPES if value not in _NEW_EVENT_TYPES
    )
    with op.batch_alter_table("product_analytics_events") as batch_op:
        batch_op.drop_constraint("ck_product_events_type", type_="check")
        batch_op.create_check_constraint(
            "ck_product_events_type", _constraint_sql(previous_event_types)
        )

    op.drop_index("uq_career_action_plans_active_decision", table_name="career_action_plans")
    with op.batch_alter_table("career_applications") as batch_op:
        batch_op.drop_constraint("uq_career_applications_pursuit_opportunity", type_="unique")
        batch_op.drop_constraint("fk_career_applications_current_opportunity", type_="foreignkey")
        batch_op.drop_column("current_opportunity_id")
