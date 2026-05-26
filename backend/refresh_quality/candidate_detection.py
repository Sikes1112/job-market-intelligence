"""Refresh candidate detection over already-loaded fact metadata.

Detection is deliberately read-only. A candidate says "this existing fact may
need refresh"; it does not assert new truth, create observations, fetch source
data, update canonical rows, or change scores.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.shared.freshness import FreshnessStatus, evaluate_freshness

from .models import (
    QualitySeverity,
    RefreshCandidate,
    RefreshCandidateReason,
    RefreshFactSnapshot,
    SourceRefreshTargetType,
    stable_refresh_candidate_key,
)

HIRING_COUNT_FACT_TYPES = frozenset(
    {"hiring_count", "hiring_counts", "company_region_hiring"}
)
INTERNSHIP_FACT_TYPES = frozenset(
    {"internship_data", "internships_coops", "company_internship_data"}
)
PRESENCE_FACT_TYPES = frozenset(
    {"company_region_presence", "presence", "region_presence"}
)
ENTRY_LEVEL_FACT_TYPES = frozenset(
    {"entry_level_signal", "entry_level_signals", "early_career_programs"}
)
COVERAGE_FACT_TYPES = frozenset(
    {"coverage", "market_coverage", "source_coverage", "region_coverage"}
)

LOW_CONFIDENCE_VALUES = frozenset(
    {"low", "unknown", "low_confidence", "unknown_confidence"}
)

DEFAULT_HIRING_MAX_AGE_DAYS = 14
DEFAULT_INTERNSHIP_MAX_AGE_DAYS = 120
DEFAULT_PRESENCE_MAX_AGE_DAYS = 180
DEFAULT_ENTRY_LEVEL_MAX_AGE_DAYS = 90
DEFAULT_COVERAGE_GAP_SCORE_THRESHOLD = 40.0

_SEVERITY_BY_REASON: dict[RefreshCandidateReason, QualitySeverity] = {
    RefreshCandidateReason.STALE_HIRING_COUNT: QualitySeverity.MEDIUM,
    RefreshCandidateReason.EXPIRED_INTERNSHIP_DATA: QualitySeverity.HIGH,
    RefreshCandidateReason.OLD_COMPANY_REGION_PRESENCE_DATA: QualitySeverity.MEDIUM,
    RefreshCandidateReason.LOW_CONFIDENCE_SOURCE_FACT: QualitySeverity.MEDIUM,
    RefreshCandidateReason.MISSING_SOURCE_FACT: QualitySeverity.HIGH,
    RefreshCandidateReason.STALE_ENTRY_LEVEL_SIGNAL: QualitySeverity.HIGH,
    RefreshCandidateReason.COVERAGE_GAP: QualitySeverity.HIGH,
}

_TARGET_BY_REASON: dict[RefreshCandidateReason, SourceRefreshTargetType] = {
    RefreshCandidateReason.STALE_HIRING_COUNT: (
        SourceRefreshTargetType.COMPANY_CAREERS_PAGE
    ),
    RefreshCandidateReason.EXPIRED_INTERNSHIP_DATA: (
        SourceRefreshTargetType.COMPANY_INTERNSHIP_PAGE
    ),
    RefreshCandidateReason.OLD_COMPANY_REGION_PRESENCE_DATA: (
        SourceRefreshTargetType.COMPANY_PAGE
    ),
    RefreshCandidateReason.LOW_CONFIDENCE_SOURCE_FACT: (
        SourceRefreshTargetType.MANUAL_RESEARCH_REQUIRED
    ),
    RefreshCandidateReason.MISSING_SOURCE_FACT: (
        SourceRefreshTargetType.MANUAL_RESEARCH_REQUIRED
    ),
    RefreshCandidateReason.STALE_ENTRY_LEVEL_SIGNAL: (
        SourceRefreshTargetType.COMPANY_INTERNSHIP_PAGE
    ),
    RefreshCandidateReason.COVERAGE_GAP: (
        SourceRefreshTargetType.MANUAL_RESEARCH_REQUIRED
    ),
}


def detect_refresh_candidates(
    facts: Iterable[RefreshFactSnapshot],
    *,
    now: datetime | None = None,
    hiring_max_age_days: int = DEFAULT_HIRING_MAX_AGE_DAYS,
    internship_max_age_days: int = DEFAULT_INTERNSHIP_MAX_AGE_DAYS,
    presence_max_age_days: int = DEFAULT_PRESENCE_MAX_AGE_DAYS,
    entry_level_max_age_days: int = DEFAULT_ENTRY_LEVEL_MAX_AGE_DAYS,
    coverage_gap_score_threshold: float = DEFAULT_COVERAGE_GAP_SCORE_THRESHOLD,
) -> list[RefreshCandidate]:
    """Return deterministic refresh candidates for supplied fact snapshots."""

    checked_at = _checked_at(now)
    candidates: list[RefreshCandidate] = []
    for fact in facts:
        normalized_type = _normalize_fact_type(fact.fact_type)

        if normalized_type in HIRING_COUNT_FACT_TYPES and (
            _is_stale_by_expiry(fact, now=checked_at)
            or _is_older_than(
                fact.last_updated_at,
                max_age_days=hiring_max_age_days,
                now=checked_at,
            )
        ):
            candidates.append(
                _candidate(
                    fact,
                    RefreshCandidateReason.STALE_HIRING_COUNT,
                    explanation=(
                        "Hiring-count metadata is stale for its refresh window."
                    ),
                )
            )

        if normalized_type in INTERNSHIP_FACT_TYPES and (
            _is_stale_by_expiry(fact, now=checked_at)
            or _is_older_than(
                fact.last_updated_at,
                max_age_days=internship_max_age_days,
                now=checked_at,
            )
        ):
            candidates.append(
                _candidate(
                    fact,
                    RefreshCandidateReason.EXPIRED_INTERNSHIP_DATA,
                    explanation=(
                        "Internship or co-op data is expired for the seasonal "
                        "refresh window."
                    ),
                )
            )

        if normalized_type in PRESENCE_FACT_TYPES and _is_older_than(
            fact.last_updated_at,
            max_age_days=presence_max_age_days,
            now=checked_at,
        ):
            candidates.append(
                _candidate(
                    fact,
                    RefreshCandidateReason.OLD_COMPANY_REGION_PRESENCE_DATA,
                    explanation=(
                        "Company-region presence metadata is older than the "
                        "presence refresh window."
                    ),
                )
            )

        if _is_low_confidence(fact.confidence):
            candidates.append(
                _candidate(
                    fact,
                    RefreshCandidateReason.LOW_CONFIDENCE_SOURCE_FACT,
                    explanation=(
                        "Existing source-backed fact has low or unknown confidence."
                    ),
                )
            )

        if fact.required and not fact.source_refs and not _has_source_context(fact):
            candidates.append(
                _candidate(
                    fact,
                    RefreshCandidateReason.MISSING_SOURCE_FACT,
                    explanation="Required fact has no source or evidence context.",
                )
            )

        if normalized_type in ENTRY_LEVEL_FACT_TYPES and (
            _is_stale_by_expiry(fact, now=checked_at)
            or _is_older_than(
                fact.last_updated_at,
                max_age_days=entry_level_max_age_days,
                now=checked_at,
            )
        ):
            candidates.append(
                _candidate(
                    fact,
                    RefreshCandidateReason.STALE_ENTRY_LEVEL_SIGNAL,
                    explanation=(
                        "Entry-level signal is stale for the early-career "
                        "refresh window."
                    ),
                )
            )

        if normalized_type in COVERAGE_FACT_TYPES and _has_coverage_gap(
            fact,
            threshold=coverage_gap_score_threshold,
        ):
            candidates.append(
                _candidate(
                    fact,
                    RefreshCandidateReason.COVERAGE_GAP,
                    explanation=(
                        "Coverage metadata is below the configured quality "
                        "threshold or marks an explicit gap."
                    ),
                )
            )

    return sorted(candidates, key=lambda candidate: candidate.candidate_key)


def hiring_count_snapshot_from_record(record: Any) -> RefreshFactSnapshot:
    """Build a refresh-quality snapshot from a hiring row-like object."""

    return RefreshFactSnapshot(
        entity_type="company_region",
        entity_id=_company_region_entity_id(record),
        fact_type="hiring_count",
        fact_id=getattr(record, "hiring_id", None),
        current_value=getattr(record, "active_posting_count_now", None),
        last_updated_at=_optional_datetime_attr(record, "updated_at"),
        freshness_expires_at=_optional_datetime_attr(record, "freshness_expires_at"),
        confidence=getattr(record, "hiring_confidence", None),
        source_refs=source_refs_from_payload(getattr(record, "source_refs", None)),
        recommended_source_type=SourceRefreshTargetType.COMPANY_CAREERS_PAGE,
    )


def internship_snapshot_from_record(record: Any) -> RefreshFactSnapshot:
    """Build a snapshot for internship/co-op data from an entry-level row."""

    return RefreshFactSnapshot(
        entity_type="company_region",
        entity_id=_company_region_entity_id(record),
        fact_type="internship_data",
        fact_id=getattr(record, "entry_level_id", None),
        current_value={
            "internship_count": getattr(record, "internship_count", None),
            "coop_count": getattr(record, "coop_count", None),
        },
        last_updated_at=_optional_datetime_attr(record, "updated_at"),
        freshness_expires_at=_optional_datetime_attr(record, "freshness_expires_at"),
        confidence=getattr(record, "entry_level_confidence", None),
        source_refs=source_refs_from_payload(getattr(record, "source_refs", None)),
        recommended_source_type=SourceRefreshTargetType.COMPANY_INTERNSHIP_PAGE,
    )


def entry_level_signal_snapshot_from_record(record: Any) -> RefreshFactSnapshot:
    """Build a snapshot for general entry-level signal freshness."""

    return RefreshFactSnapshot(
        entity_type="company_region",
        entity_id=_company_region_entity_id(record),
        fact_type="entry_level_signal",
        fact_id=getattr(record, "entry_level_id", None),
        current_value=getattr(record, "entry_level_access_score", None),
        last_updated_at=_optional_datetime_attr(record, "updated_at"),
        freshness_expires_at=_optional_datetime_attr(record, "freshness_expires_at"),
        confidence=getattr(record, "entry_level_confidence", None),
        source_refs=source_refs_from_payload(getattr(record, "source_refs", None)),
        recommended_source_type=SourceRefreshTargetType.COMPANY_INTERNSHIP_PAGE,
    )


def presence_snapshot_from_record(record: Any) -> RefreshFactSnapshot:
    """Build a refresh-quality snapshot from a presence row-like object."""

    return RefreshFactSnapshot(
        entity_type="company_region",
        entity_id=_company_region_entity_id(record),
        fact_type="company_region_presence",
        fact_id=getattr(record, "presence_id", None),
        current_value=getattr(record, "presence_status", None),
        last_updated_at=_optional_datetime_attr(record, "updated_at"),
        confidence=getattr(record, "presence_confidence", None),
        source_refs=source_refs_from_payload(getattr(record, "source_refs", None)),
        recommended_source_type=SourceRefreshTargetType.COMPANY_PAGE,
    )


def source_refs_from_payload(payload: Any) -> tuple[str, ...]:
    """Extract source reference strings from existing opaque JSON payloads."""

    refs: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value.strip():
            refs.append(value.strip())

    if payload is None:
        return ()
    if isinstance(payload, str):
        add(payload)
    elif isinstance(payload, dict):
        for key in (
            "source_id",
            "source_ref",
            "ref",
            "fact_source_link_id",
            "observation_id",
        ):
            add(payload.get(key))
        for key in (
            "source_ids",
            "source_refs",
            "refs",
            "fact_source_link_ids",
            "observation_ids",
        ):
            nested = payload.get(key)
            if isinstance(nested, (list, tuple, set)):
                for item in nested:
                    add(item)
    elif isinstance(payload, (list, tuple, set)):
        for item in payload:
            if isinstance(item, dict):
                refs.extend(source_refs_from_payload(item))
            else:
                add(item)

    return tuple(dict.fromkeys(refs))


def _candidate(
    fact: RefreshFactSnapshot,
    reason: RefreshCandidateReason,
    *,
    explanation: str,
) -> RefreshCandidate:
    evidence_context = dict(fact.evidence_context)
    if fact.source_refs:
        evidence_context.setdefault("source_refs", list(fact.source_refs))
    if fact.freshness_expires_at is not None:
        evidence_context.setdefault(
            "freshness_expires_at",
            fact.freshness_expires_at.isoformat(),
        )
    if fact.coverage_score is not None:
        evidence_context.setdefault("coverage_score", fact.coverage_score)

    return RefreshCandidate(
        candidate_key=stable_refresh_candidate_key(
            entity_type=fact.entity_type,
            entity_id=fact.entity_id,
            fact_type=fact.fact_type,
            fact_id=fact.fact_id,
            reason=reason,
        ),
        entity_type=fact.entity_type,
        entity_id=fact.entity_id,
        fact_type=fact.fact_type,
        fact_id=fact.fact_id,
        reason=reason,
        severity=_SEVERITY_BY_REASON[reason],
        explanation=explanation,
        evidence_context=evidence_context,
        current_value=fact.current_value,
        last_updated_at=fact.last_updated_at,
        confidence=fact.confidence,
        recommended_source_type=fact.recommended_source_type
        or _TARGET_BY_REASON[reason],
    )


def _checked_at(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now


def _is_stale_by_expiry(fact: RefreshFactSnapshot, *, now: datetime) -> bool:
    if fact.freshness_expires_at is None:
        return False
    return evaluate_freshness(fact.freshness_expires_at, now=now) is FreshnessStatus.STALE


def _is_older_than(
    last_updated_at: datetime | None,
    *,
    max_age_days: int,
    now: datetime,
) -> bool:
    if last_updated_at is None:
        return False
    return now - last_updated_at > timedelta(days=max_age_days)


def _is_low_confidence(confidence: str | None) -> bool:
    return (confidence or "").strip().lower() in LOW_CONFIDENCE_VALUES


def _has_source_context(fact: RefreshFactSnapshot) -> bool:
    context = fact.evidence_context
    if not context:
        return False
    for key in ("source_refs", "source_ids", "evidence_refs", "observation_ids"):
        value = context.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (list, tuple, set)) and any(str(item).strip() for item in value):
            return True
    return False


def _has_coverage_gap(
    fact: RefreshFactSnapshot,
    *,
    threshold: float,
) -> bool:
    if fact.coverage_score is not None and fact.coverage_score < threshold:
        return True
    value = fact.evidence_context.get("coverage_gap")
    return value is True


def _normalize_fact_type(fact_type: str) -> str:
    return fact_type.strip().lower().replace("-", "_").replace(" ", "_")


def _company_region_entity_id(record: Any) -> str:
    company_id = getattr(record, "company_id", None)
    region_id = getattr(record, "region_id", None)
    if not company_id or not region_id:
        raise ValueError("record must expose company_id and region_id")
    return f"{company_id}::{region_id}"


def _optional_datetime_attr(record: Any, attr: str) -> datetime | None:
    value = getattr(record, attr, None)
    return value if isinstance(value, datetime) else None


__all__ = [
    "COVERAGE_FACT_TYPES",
    "DEFAULT_COVERAGE_GAP_SCORE_THRESHOLD",
    "DEFAULT_ENTRY_LEVEL_MAX_AGE_DAYS",
    "DEFAULT_HIRING_MAX_AGE_DAYS",
    "DEFAULT_INTERNSHIP_MAX_AGE_DAYS",
    "DEFAULT_PRESENCE_MAX_AGE_DAYS",
    "ENTRY_LEVEL_FACT_TYPES",
    "HIRING_COUNT_FACT_TYPES",
    "INTERNSHIP_FACT_TYPES",
    "LOW_CONFIDENCE_VALUES",
    "PRESENCE_FACT_TYPES",
    "detect_refresh_candidates",
    "entry_level_signal_snapshot_from_record",
    "hiring_count_snapshot_from_record",
    "internship_snapshot_from_record",
    "presence_snapshot_from_record",
    "source_refs_from_payload",
]
