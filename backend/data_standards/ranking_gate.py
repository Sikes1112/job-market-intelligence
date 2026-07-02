"""Ranking eligibility helpers for partner-origin canonical facts."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.data_standards.models import DataStandardCanonicalMergeRecord


def ranking_eligible_fact_ids(
    session: Session,
    fact_type: str,
    fact_ids: list[str] | tuple[str, ...] | set[str],
) -> set[str]:
    """Return fact IDs allowed to influence scoring/ranking.

    Canonical facts with no Layer 28 merge record are existing platform-owned
    facts and remain eligible. Layer 28 partner-origin facts require an explicit
    true ranking flag; current Layer 28 merge records constrain that flag false.
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
    blocked = {
        canonical_target_id
        for canonical_target_id, ranking_influence_allowed in rows
        if not ranking_influence_allowed
    }
    return ids - blocked
