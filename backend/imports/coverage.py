"""Public-safe market coverage summaries for curated imports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region, RegionStateMembership
from backend.hiring.models import CompanyRegionHiring
from backend.imports.registry import load_market_registry, resolve_market_registry_entry
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink, SourceRef
from backend.shared.freshness import FreshnessStatus
from backend.shared.provenance import FactBindingType, ObservationStatus
from backend.trust.models import RiskRoutingDecision
from backend.trust.schemas import TrustAssessmentSubjectType

_COUNT_STATUS_FIELDS: tuple[str, ...] = (
    "active_posting_count_now_status",
    "internship_count_status",
    "coop_count_status",
    "entry_level_full_time_count_status",
)

_UNOBSERVED_STATUSES: frozenset[str] = frozenset(
    {
        ObservationStatus.UNKNOWN.value,
        ObservationStatus.NOT_COLLECTED.value,
        ObservationStatus.NOT_APPLICABLE.value,
    }
)

_ZERO_STATUS = ObservationStatus.ZERO_OBSERVED.value

_FACT_SUBJECT_TYPES: dict[str, TrustAssessmentSubjectType] = {
    FactBindingType.COMPANY.value: TrustAssessmentSubjectType.COMPANY_FACT,
    FactBindingType.REGION.value: TrustAssessmentSubjectType.REGION_FACT,
    FactBindingType.COMPANY_REGION_PRESENCE.value: (
        TrustAssessmentSubjectType.DATA_STANDARD_FACT
    ),
    FactBindingType.COMPANY_REGION_HIRING.value: (
        TrustAssessmentSubjectType.DATA_STANDARD_FACT
    ),
    FactBindingType.COMPANY_REGION_ENTRY_LEVEL.value: (
        TrustAssessmentSubjectType.DATA_STANDARD_FACT
    ),
}


@dataclass(frozen=True, slots=True)
class MarketCoverageSummary:
    market_key: str
    region_id: str
    public_slug: str | None
    display_name: str
    primary_city: str | None
    state_codes: tuple[str, ...]
    coverage_status: str
    import_status: str
    company_count: int
    presence_fact_count: int
    hiring_fact_count: int
    entry_level_fact_count: int
    source_count: int
    freshness_status: str
    ranking_eligible_fact_count: int
    ranking_excluded_fact_count: int
    unknown_count_dimensions: int
    observed_zero_count_dimensions: int
    count_status_breakdown: MappingProxyType[str, int]
    last_curated_at: str
    last_import_status: str
    last_refresh_status: str
    imported_data_label: str
    coverage_label: str
    freshness_label: str
    source_label: str
    trust_label: str
    risk_label: str
    ranking_label: str
    comparison_available: bool
    comparison_label: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "market_key": self.market_key,
            "region_id": self.region_id,
            "public_slug": self.public_slug,
            "display_name": self.display_name,
            "primary_city": self.primary_city,
            "state_codes": list(self.state_codes),
            "coverage_status": self.coverage_status,
            "import_status": self.import_status,
            "company_count": self.company_count,
            "presence_fact_count": self.presence_fact_count,
            "hiring_fact_count": self.hiring_fact_count,
            "entry_level_fact_count": self.entry_level_fact_count,
            "source_count": self.source_count,
            "freshness_status": self.freshness_status,
            "ranking_eligible_fact_count": self.ranking_eligible_fact_count,
            "ranking_excluded_fact_count": self.ranking_excluded_fact_count,
            "unknown_count_dimensions": self.unknown_count_dimensions,
            "observed_zero_count_dimensions": self.observed_zero_count_dimensions,
            "count_status_breakdown": dict(self.count_status_breakdown),
            "last_curated_at": self.last_curated_at,
            "last_import_status": self.last_import_status,
            "last_refresh_status": self.last_refresh_status,
            "imported_data_label": self.imported_data_label,
            "coverage_label": self.coverage_label,
            "freshness_label": self.freshness_label,
            "source_label": self.source_label,
            "trust_label": self.trust_label,
            "risk_label": self.risk_label,
            "ranking_label": self.ranking_label,
            "comparison_available": self.comparison_available,
            "comparison_label": self.comparison_label,
        }


def build_market_coverage_summary(
    session: Session,
    market_key: str,
    *,
    registry_path: str | Path | None = None,
) -> MarketCoverageSummary:
    entry = resolve_market_registry_entry(market_key, registry_path)
    region = session.get(Region, entry.region_id)
    presence_rows = _presence_rows(session, entry.region_id)
    hiring_rows = _hiring_rows(session, entry.region_id)
    entry_level_rows = _entry_level_rows(session, entry.region_id)
    company_ids = tuple(sorted({row.company_id for row in presence_rows}))
    fact_refs = _fact_refs(
        entry.region_id,
        company_ids,
        presence_rows,
        hiring_rows,
        entry_level_rows,
    )
    fact_links = _fact_links(session, fact_refs, market_key=market_key)
    source_rows = _source_rows(session, market_key)
    source_count = len({link.source_id for link in fact_links}) or len(source_rows)
    statuses = _count_status_breakdown(hiring_rows, entry_level_rows)
    decisions = _latest_routing_decisions(session, fact_refs)
    ranking_allowed = sum(1 for decision in decisions if decision.ranking_influence_allowed)
    ranking_denied = sum(1 for decision in decisions if not decision.ranking_influence_allowed)
    imported = (
        region is not None
        and bool(presence_rows)
        and bool(hiring_rows)
        and bool(entry_level_rows)
        and bool(source_rows)
    )

    return MarketCoverageSummary(
        market_key=entry.market_key,
        region_id=entry.region_id,
        public_slug=region.public_slug if region else None,
        display_name=entry.display_name,
        primary_city=region.primary_city if region else None,
        state_codes=(
            tuple(
                session.execute(
                    select(RegionStateMembership.state_code)
                    .where(RegionStateMembership.region_id == entry.region_id)
                    .order_by(RegionStateMembership.state_code)
                ).scalars()
            )
            if region
            else ()
        ),
        coverage_status=entry.coverage_status,
        import_status=entry.import_status,
        company_count=len(company_ids),
        presence_fact_count=len(presence_rows),
        hiring_fact_count=len(hiring_rows),
        entry_level_fact_count=len(entry_level_rows),
        source_count=source_count,
        freshness_status=_freshness_status(fact_links, source_rows),
        ranking_eligible_fact_count=ranking_allowed,
        ranking_excluded_fact_count=ranking_denied,
        unknown_count_dimensions=sum(
            count for status, count in statuses.items() if status in _UNOBSERVED_STATUSES
        ),
        observed_zero_count_dimensions=statuses.get(_ZERO_STATUS, 0),
        count_status_breakdown=MappingProxyType(statuses),
        last_curated_at=entry.last_curated_at,
        last_import_status="imported" if imported else "not_imported",
        last_refresh_status="refreshed" if decisions else "not_refreshed",
        imported_data_label=(
            "Real imported data" if imported else "Imported data not loaded"
        ),
        coverage_label=_coverage_label(entry.coverage_status),
        freshness_label=_freshness_label(_freshness_status(fact_links, source_rows)),
        source_label="Source-backed" if source_count else "Limited source coverage",
        trust_label="Source-backed" if source_count else "Not assessed",
        risk_label=_risk_label(ranking_allowed, ranking_denied),
        ranking_label=(
            "Some data ranking-excluded"
            if ranking_denied
            else "Ranking-safe"
            if ranking_allowed
            else "Ranking not assessed"
        ),
        comparison_available=imported and ranking_allowed > 0,
        comparison_label=(
            "Comparison available" if imported and ranking_allowed > 0 else "Comparison limited"
        ),
    )


def build_all_market_coverage_summaries(
    session: Session,
    *,
    registry_path: str | Path | None = None,
) -> MappingProxyType[str, MarketCoverageSummary]:
    registry = load_market_registry(registry_path)
    return MappingProxyType(
        {
            market_key: build_market_coverage_summary(
                session,
                market_key,
                registry_path=registry_path,
            )
            for market_key, entry in registry.items()
            if entry.import_status == "ready"
        }
    )


def _presence_rows(session: Session, region_id: str) -> tuple[CompanyRegionPresence, ...]:
    rows = session.execute(
        select(CompanyRegionPresence)
        .where(CompanyRegionPresence.region_id == region_id)
        .order_by(CompanyRegionPresence.company_id)
    ).scalars()
    return tuple(rows)


def _hiring_rows(session: Session, region_id: str) -> tuple[CompanyRegionHiring, ...]:
    rows = session.execute(
        select(CompanyRegionHiring)
        .where(CompanyRegionHiring.region_id == region_id)
        .order_by(CompanyRegionHiring.company_id)
    ).scalars()
    return tuple(rows)


def _entry_level_rows(
    session: Session,
    region_id: str,
) -> tuple[CompanyRegionEntryLevel, ...]:
    rows = session.execute(
        select(CompanyRegionEntryLevel)
        .where(CompanyRegionEntryLevel.region_id == region_id)
        .order_by(CompanyRegionEntryLevel.company_id)
    ).scalars()
    return tuple(rows)


def _source_rows(session: Session, market_key: str) -> tuple[SourceRef, ...]:
    rows = session.execute(
        select(SourceRef)
        .where(SourceRef.source_id.like(f"src_{market_key}_%"))
        .order_by(SourceRef.source_id)
    ).scalars()
    return tuple(rows)


def _fact_links(
    session: Session,
    fact_refs: tuple[tuple[str, str], ...],
    *,
    market_key: str,
) -> tuple[FactSourceLink, ...]:
    if not fact_refs:
        return ()
    rows: list[FactSourceLink] = []
    grouped: dict[str, set[str]] = {}
    for fact_type, fact_id in fact_refs:
        grouped.setdefault(fact_type, set()).add(fact_id)
    for fact_type, fact_ids in grouped.items():
        links = session.execute(
            select(FactSourceLink)
            .where(FactSourceLink.fact_type == fact_type)
            .where(FactSourceLink.fact_id.in_(sorted(fact_ids)))
            .where(FactSourceLink.source_id.like(f"src_{market_key}_%"))
            .order_by(
                FactSourceLink.fact_type,
                FactSourceLink.fact_id,
                FactSourceLink.source_id,
            )
        ).scalars()
        rows.extend(links)
    return tuple(rows)


def _fact_refs(
    region_id: str,
    company_ids: tuple[str, ...],
    presence_rows: tuple[CompanyRegionPresence, ...],
    hiring_rows: tuple[CompanyRegionHiring, ...],
    entry_level_rows: tuple[CompanyRegionEntryLevel, ...],
) -> tuple[tuple[str, str], ...]:
    refs: list[tuple[str, str]] = [(FactBindingType.REGION.value, region_id)]
    refs.extend((FactBindingType.COMPANY.value, company_id) for company_id in company_ids)
    refs.extend(
        (FactBindingType.COMPANY_REGION_PRESENCE.value, row.presence_id)
        for row in presence_rows
    )
    refs.extend(
        (FactBindingType.COMPANY_REGION_HIRING.value, row.hiring_id)
        for row in hiring_rows
    )
    refs.extend(
        (FactBindingType.COMPANY_REGION_ENTRY_LEVEL.value, row.entry_level_id)
        for row in entry_level_rows
    )
    return tuple(refs)


def _latest_routing_decisions(
    session: Session,
    fact_refs: tuple[tuple[str, str], ...],
) -> tuple[RiskRoutingDecision, ...]:
    grouped: dict[str, set[str]] = {}
    for fact_type, fact_id in fact_refs:
        subject_type = _FACT_SUBJECT_TYPES.get(fact_type)
        if subject_type is None:
            continue
        grouped.setdefault(subject_type.value, set()).add(fact_id)

    latest: dict[tuple[str, str], RiskRoutingDecision] = {}
    for subject_type, subject_ids in grouped.items():
        rows = session.execute(
            select(RiskRoutingDecision)
            .where(RiskRoutingDecision.subject_type == subject_type)
            .where(RiskRoutingDecision.subject_id.in_(sorted(subject_ids)))
            .order_by(
                RiskRoutingDecision.subject_type,
                RiskRoutingDecision.subject_id,
                RiskRoutingDecision.decided_at.desc(),
                RiskRoutingDecision.risk_routing_decision_id.desc(),
            )
        ).scalars()
        for row in rows:
            latest.setdefault((row.subject_type, row.subject_id), row)

    decisions: list[RiskRoutingDecision] = []
    for fact_type, fact_id in fact_refs:
        subject_type = _FACT_SUBJECT_TYPES.get(fact_type)
        if subject_type is None:
            continue
        decision = latest.get((subject_type.value, fact_id))
        if decision is not None:
            decisions.append(decision)
    return tuple(decisions)


def _count_status_breakdown(
    hiring_rows: tuple[CompanyRegionHiring, ...],
    entry_level_rows: tuple[CompanyRegionEntryLevel, ...],
) -> dict[str, int]:
    statuses: dict[str, int] = {}
    for row in hiring_rows:
        _add_status(statuses, row.active_posting_count_now_status)
    for row in entry_level_rows:
        _add_status(statuses, row.internship_count_status)
        _add_status(statuses, row.coop_count_status)
        _add_status(statuses, row.entry_level_full_time_count_status)
    return dict(sorted(statuses.items()))


def _add_status(statuses: dict[str, int], value: str | None) -> None:
    if not value:
        return
    if value not in _COUNT_STATUS_FIELDS and value not in ObservationStatus.values():
        return
    statuses[value] = statuses.get(value, 0) + 1


def _freshness_status(
    fact_links: tuple[FactSourceLink, ...],
    source_rows: tuple[SourceRef, ...],
) -> str:
    freshness_values = (
        [link.freshness_status for link in fact_links if link.freshness_status]
        if fact_links
        else [row.freshness_status for row in source_rows if row.freshness_status]
    )
    if not freshness_values:
        return FreshnessStatus.UNKNOWN.value
    values = set(freshness_values)
    if FreshnessStatus.STALE.value in values:
        return FreshnessStatus.STALE.value
    if values == {FreshnessStatus.FRESH.value}:
        return FreshnessStatus.FRESH.value
    return FreshnessStatus.UNKNOWN.value


def _coverage_label(coverage_status: str) -> str:
    if coverage_status == "partial_curated":
        return "Partial coverage"
    if coverage_status == "curated":
        return "Seed coverage"
    return "Coverage unknown"


def _freshness_label(freshness_status: str) -> str:
    if freshness_status == FreshnessStatus.FRESH.value:
        return "Current"
    if freshness_status == FreshnessStatus.STALE.value:
        return "Needs refresh"
    return "Freshness unknown"


def _risk_label(ranking_allowed: int, ranking_denied: int) -> str:
    if ranking_denied:
        return "Use with caution"
    if ranking_allowed:
        return "Low risk"
    return "Not assessed"
