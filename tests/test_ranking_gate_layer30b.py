from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.data_standards.ranking_gate import ranking_eligible_fact_ids
from backend.trust.models import RiskRoutingDecision

NOW = datetime(2026, 7, 3, 12, tzinfo=UTC)


def test_new_unassessed_canonical_facts_are_denied_in_strict_mode(
    session: Session,
) -> None:
    assert ranking_eligible_fact_ids(
        session,
        "company",
        ["company_new"],
        allow_legacy_unassessed=False,
    ) == set()
    assert ranking_eligible_fact_ids(
        session,
        "company",
        ["company_legacy"],
        allow_legacy_unassessed=True,
    ) == {"company_legacy"}


def test_layer_30b_explicit_decisions_control_ranking_gate(session: Session) -> None:
    session.add_all(
        [
            _decision("company_allowed", allowed=True),
            _decision("company_denied", allowed=False),
        ]
    )
    session.flush()

    assert ranking_eligible_fact_ids(
        session,
        "company",
        ["company_allowed", "company_denied", "company_missing"],
        allow_legacy_unassessed=False,
    ) == {"company_allowed"}


def _decision(subject_id: str, *, allowed: bool) -> RiskRoutingDecision:
    return RiskRoutingDecision(
        risk_routing_decision_id=f"risk_{subject_id}",
        subject_type="company_fact",
        subject_id=subject_id,
        trust_tier="verified" if allowed else "low_confidence",
        risk_level="low" if allowed else "medium",
        routing_outcome=(
            "auto_accept_non_ranking" if allowed else "visible_with_warning"
        ),
        routing_reasons_json=[],
        ranking_influence_decision="allowed" if allowed else "denied",
        ranking_influence_allowed=allowed,
        ranking_influence_reason="test decision",
        ranking_influence_reason_codes_json=[
            "verified_fresh_no_conflict" if allowed else "low_confidence"
        ],
        evidence_requirements_met_json=[],
        evidence_requirements_missing_json=[],
        evidence_requirements_failed_json=[],
        warnings_json=[],
        decision_source="deterministic_layer_30b",
        decision_version="30B.1",
        decided_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
