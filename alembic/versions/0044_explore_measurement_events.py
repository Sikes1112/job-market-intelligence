"""Add high-value Explore evaluation event types.

Revision ID: 0044_explore_measurement_events
Revises: 0043_active_geography_canonicalization
Create Date: 2026-10-08
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0044_explore_measurement_events"
down_revision = "0043_active_geography_canonicalization"
branch_labels = None
depends_on = None

_LEGACY_EVENT_TYPES = (
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
_EXPLORE_EVENT_TYPES = (
    "explore_context_evaluated",
    "explore_fit_generated",
    "explore_fit_abstained",
    "explore_context_unsupported",
)


def _constraint_sql(values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"event_type IN ({rendered})"


def upgrade() -> None:
    with op.batch_alter_table("product_analytics_events") as batch_op:
        batch_op.drop_constraint("ck_product_events_type", type_="check")
        batch_op.create_check_constraint(
            "ck_product_events_type",
            _constraint_sql((*_EXPLORE_EVENT_TYPES, *_LEGACY_EVENT_TYPES)),
        )


def downgrade() -> None:
    connection = op.get_bind()
    explore_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM product_analytics_events WHERE event_type IN :event_types"
        ).bindparams(sa.bindparam("event_types", expanding=True)),
        {"event_types": _EXPLORE_EVENT_TYPES},
    ).scalar_one()
    if explore_count:
        raise RuntimeError("0044 downgrade requires Explore analytics events to be archived first")
    with op.batch_alter_table("product_analytics_events") as batch_op:
        batch_op.drop_constraint("ck_product_events_type", type_="check")
        batch_op.create_check_constraint(
            "ck_product_events_type",
            _constraint_sql(_LEGACY_EVENT_TYPES),
        )
