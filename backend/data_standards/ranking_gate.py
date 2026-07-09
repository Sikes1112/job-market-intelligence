"""Ranking eligibility helpers for canonical facts."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.data_standards.models import DataStandardCanonicalMergeRecord
from backend.trust.models import RiskRoutingDecision
from backend.trust.schemas import TrustAssessmentSubjectType

_FACT_SUBJECT_TYPES: dict[str, TrustAssessmentSubjectType] = {
    "company": TrustAssessmentSubjectType.COMPANY_FACT,
    "region": TrustAssessmentSubjectType.REGION_FACT,
    "company_region_presence": TrustAssessmentSubjectType.DATA_STANDARD_FACT,
    "company_region_hiring": TrustAssessmentSubjectType.DATA_STANDARD_FACT,
    "company_region_entry_level": TrustAssessmentSubjectType.DATA_STANDARD_FACT,
}


def ranking_eligible_fact_ids(
    session: Session,
    fact_type: str,
    fact_ids: list[str] | tuple[str, ...] | set[str],
    *,
    allow_legacy_unassessed: bool = True,
) -> set[str]:
    """Return fact IDs allowed to influence scoring/ranking.

    Layer 30B decisions are the ranking authority when present. Existing
    platform-owned canonical facts with no Layer 28/30 record can remain
    eligible only through the explicit ``allow_legacy_unassessed`` compatibility
    flag. New submitted/imported/manual canonical writes should call this helper
    with that flag disabled or persist an explicit Layer 30B allow decision.
    """

    ids = {fact_id for fact_id in fact_ids if fact_id}
    if not ids:
        return set()
    rows = session.execute(
        select(
            DataStandardCanonicalMergeRecord.canonical_target_id,
            DataStandardCanonicalMergeRecord.ranking_influence_allowed,
        )
        .where(DataStandardCanonicalMergeRecord.canonical_target_type == fact_type)
        .where(DataStandardCanonicalMergeRecord.canonical_target_id.in_(ids))
        .where(DataStandardCanonicalMergeRecord.merge_status == "merged")
    ).all()
    merge_state = {
        canonical_target_id: ranking_influence_allowed
        for canonical_target_id, ranking_influence_allowed in rows
    }
    denied_by_merge = {
        canonical_target_id
        for canonical_target_id, ranking_influence_allowed in rows
        if not ranking_influence_allowed
    }
    decisions = _latest_routing_decisions(session, fact_type=fact_type, fact_ids=ids)
    allowed: set[str] = set()
    for fact_id in ids:
        decision = decisions.get(fact_id)
        if decision is True:
            allowed.add(fact_id)
            continue
        if decision is False:
            continue
        if fact_id in denied_by_merge:
            continue
        if fact_id in merge_state:
            if merge_state[fact_id]:
                allowed.add(fact_id)
            continue
        if allow_legacy_unassessed:
            allowed.add(fact_id)
    return allowed


def _latest_routing_decisions(
    session: Session,
    *,
    fact_type: str,
    fact_ids: set[str],
) -> dict[str, bool]:
    subject_type = _FACT_SUBJECT_TYPES.get(fact_type)
    if subject_type is None:
        return {}
    rows = session.execute(
        select(
            RiskRoutingDecision.subject_id,
            RiskRoutingDecision.ranking_influence_allowed,
            RiskRoutingDecision.decided_at,
            RiskRoutingDecision.risk_routing_decision_id,
        )
        .where(RiskRoutingDecision.subject_type == subject_type.value)
        .where(RiskRoutingDecision.subject_id.in_(fact_ids))
        .order_by(
            RiskRoutingDecision.subject_id,
            RiskRoutingDecision.decided_at.desc(),
            RiskRoutingDecision.risk_routing_decision_id.desc(),
        )
    ).all()
    decisions: dict[str, bool] = {}
    for subject_id, ranking_influence_allowed, _decided_at, _decision_id in rows:
        decisions.setdefault(subject_id, bool(ranking_influence_allowed))
    return decisions
