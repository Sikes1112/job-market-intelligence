"""Reusable read-only operational snapshots for curated imported markets."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.data_standards.ranking_gate import ranking_eligible_fact_ids
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.imports.contracts import (
    REQUIRED_DATASET_FILES,
)
from backend.imports.provenance import IMPORT_STALENESS_DAYS, parse_import_date
from backend.imports.registry import (
    MARKET_REGISTRY_FILE,
    CuratedMarketRegistryEntry,
    MarketRegistryError,
    load_market_registry,
    resolve_market_registry_entry,
)
from backend.imports.schemas import (
    FactArea,
    OperationalSourceFreshnessStatus,
    PublicIssue,
)
from backend.imports.service import (
    _hiring_groups,
    _hiring_id,
    _load_dataset,
    _presence_id,
)
from backend.imports.validation import ImportValidationResult, validate_curated_market_dataset
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink, SourceRef
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus
from backend.shared.provenance import FactBindingType, ObservationStatus
from backend.trust.models import RiskRoutingDecision
from backend.trust.repository import routing_decision_from_row
from backend.trust.schemas import (
    RankingInfluenceReasonCode,
    TrustAssessmentSubjectType,
)

AGING_AFTER_DAYS = int(IMPORT_STALENESS_DAYS * 0.75)
EXPIRED_AFTER_DAYS = IMPORT_STALENESS_DAYS * 2

UNOBSERVED_STATUSES: frozenset[str] = frozenset(
    {
        ObservationStatus.UNKNOWN.value,
        ObservationStatus.NOT_COLLECTED.value,
        ObservationStatus.NOT_APPLICABLE.value,
    }
)
OBSERVED_ZERO_STATUS = ObservationStatus.ZERO_OBSERVED.value
LOW_CONFIDENCE_VALUES: frozenset[str] = frozenset(
    {Confidence.LOW.value, "low_confidence", "unknown"}
)

FACT_SUBJECT_TYPES: dict[str, TrustAssessmentSubjectType] = {
    FactBindingType.COMPANY.value: TrustAssessmentSubjectType.COMPANY_FACT,
    FactBindingType.REGION.value: TrustAssessmentSubjectType.REGION_FACT,
    FactBindingType.COMPANY_REGION_PRESENCE.value: (TrustAssessmentSubjectType.DATA_STANDARD_FACT),
    FactBindingType.COMPANY_REGION_HIRING.value: (TrustAssessmentSubjectType.DATA_STANDARD_FACT),
    FactBindingType.COMPANY_REGION_ENTRY_LEVEL.value: (
        TrustAssessmentSubjectType.DATA_STANDARD_FACT
    ),
}


class UnknownCuratedMarket(KeyError):
    """Raised when an operational report is requested for an unknown market."""


class CuratedMarketRegistryUnavailable(ValueError):
    """Raised when the curated market registry cannot be safely loaded."""


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    source_id: str
    source_label: str
    source_type: str
    observed_date: date | None
    collected_date: date | None
    age_days: int | None
    freshness_status: OperationalSourceFreshnessStatus
    stored_freshness_status: str | None
    confidence: str
    license_or_terms_category: str | None
    fact_refs: tuple[tuple[str, str], ...]

    @property
    def is_stale(self) -> bool:
        return self.freshness_status in {
            OperationalSourceFreshnessStatus.STALE,
            OperationalSourceFreshnessStatus.EXPIRED,
        }


@dataclass(frozen=True, slots=True)
class FactSnapshot:
    fact_type: str
    fact_id: str
    area: FactArea
    company_id: str | None
    region_id: str | None
    observation_status: str
    freshness_status: str
    confidence: str
    source_ids: tuple[str, ...]
    ranking_eligible: bool
    ranking_reason_codes: tuple[str, ...]
    trust_tier: str | None
    risk_level: str | None
    count_statuses: tuple[str, ...] = ()

    @property
    def source_count(self) -> int:
        return len(self.source_ids)

    @property
    def ranking_excluded(self) -> bool:
        return not self.ranking_eligible

    @property
    def stale(self) -> bool:
        return self.freshness_status == FreshnessStatus.STALE.value

    @property
    def low_confidence(self) -> bool:
        return self.confidence in LOW_CONFIDENCE_VALUES

    @property
    def unknown(self) -> bool:
        return self.observation_status in UNOBSERVED_STATUSES

    @property
    def observed_zero(self) -> bool:
        return self.observation_status == OBSERVED_ZERO_STATUS


@dataclass(frozen=True, slots=True)
class MarketOperationalSnapshot:
    market_key: str
    region_id: str
    display_name: str
    registry_entry: CuratedMarketRegistryEntry
    validation: ImportValidationResult
    validation_issues: tuple[PublicIssue, ...]
    missing_required_files: tuple[str, ...]
    region: Region | None
    companies: tuple[Company, ...]
    presence_facts: tuple[CompanyRegionPresence, ...]
    hiring_facts: tuple[CompanyRegionHiring, ...]
    entry_level_facts: tuple[CompanyRegionEntryLevel, ...]
    sources: tuple[SourceSnapshot, ...]
    facts: tuple[FactSnapshot, ...]
    source_rows: dict[str, dict[str, str]]
    proposed_fact_source_ids: dict[tuple[str, str], tuple[str, ...]]

    @property
    def canonical_imported(self) -> bool:
        return self.region is not None and bool(self.facts)

    @property
    def source_by_id(self) -> dict[str, SourceSnapshot]:
        return {source.source_id: source for source in self.sources}


def build_market_operational_snapshot(
    session: Session,
    market_key: str,
    *,
    registry_path: str | Path | None = None,
    as_of: date | datetime | None = None,
    stale_after_days: int = IMPORT_STALENESS_DAYS,
) -> MarketOperationalSnapshot:
    """Build a single read-only normalized snapshot for a registered market."""

    entry = _resolve_entry(market_key, registry_path)
    reference_date = _coerce_date(as_of)
    validation = validate_curated_market_dataset(
        entry.market_key,
        registry_path=registry_path,
        as_of=reference_date,
        stale_after_days=stale_after_days,
    )
    dataset = _safe_load_dataset(entry.dataset_path)
    source_rows = dict(sorted(dataset.source_refs.items())) if dataset is not None else {}
    proposed_fact_source_ids = _proposed_fact_source_ids(dataset) if dataset is not None else {}

    region = session.get(Region, entry.region_id)
    presence = _presence_rows(session, entry.region_id)
    hiring = _hiring_rows(session, entry.region_id)
    entry_level = _entry_level_rows(session, entry.region_id)
    company_ids = sorted(
        {
            *(row.company_id for row in presence),
            *(row.company_id for row in hiring),
            *(row.company_id for row in entry_level),
        }
    )
    companies = _company_rows(session, company_ids)
    fact_refs = _fact_refs(entry.region_id, companies, presence, hiring, entry_level)
    links_by_fact = _fact_links_by_fact(session, fact_refs, market_key=entry.market_key)
    ranking_eligible = _ranking_eligible_by_fact(session, fact_refs)
    routing = _latest_routing_decisions(session, fact_refs)
    source_rows_by_id = _source_rows_by_id(session, entry.market_key)
    source_link_refs = _source_fact_refs(links_by_fact)

    sources = _source_snapshots(
        source_rows_by_id=source_rows_by_id,
        source_file_rows=source_rows,
        fact_refs_by_source=source_link_refs,
        as_of=reference_date,
        stale_after_days=stale_after_days,
    )
    facts = _fact_snapshots(
        region=region,
        companies=companies,
        presence=presence,
        hiring=hiring,
        entry_level=entry_level,
        links_by_fact=links_by_fact,
        ranking_eligible=ranking_eligible,
        routing=routing,
    )
    return MarketOperationalSnapshot(
        market_key=entry.market_key,
        region_id=entry.region_id,
        display_name=entry.display_name,
        registry_entry=entry,
        validation=validation,
        validation_issues=_public_validation_issues(validation),
        missing_required_files=_missing_required_files(validation),
        region=region,
        companies=companies,
        presence_facts=presence,
        hiring_facts=hiring,
        entry_level_facts=entry_level,
        sources=sources,
        facts=facts,
        source_rows=source_rows,
        proposed_fact_source_ids=proposed_fact_source_ids,
    )


def build_all_market_operational_snapshots(
    session: Session,
    *,
    registry_path: str | Path | None = None,
    as_of: date | datetime | None = None,
    stale_after_days: int = IMPORT_STALENESS_DAYS,
) -> tuple[MarketOperationalSnapshot, ...]:
    try:
        registry = load_market_registry(registry_path)
    except MarketRegistryError as exc:
        raise CuratedMarketRegistryUnavailable("curated market registry is invalid") from exc
    entries = tuple(
        entry for _market_key, entry in sorted(registry.items()) if entry.import_status == "ready"
    )
    if not entries:
        return ()

    reference_date = _coerce_date(as_of)
    region_ids = tuple(sorted({entry.region_id for entry in entries}))
    regions_by_id = {
        row.region_id: row
        for row in session.execute(
            select(Region).where(Region.region_id.in_(region_ids)).order_by(Region.region_id)
        ).scalars()
    }
    presence_by_region = _rows_by_region(
        session.execute(
            select(CompanyRegionPresence)
            .where(CompanyRegionPresence.region_id.in_(region_ids))
            .order_by(
                CompanyRegionPresence.region_id,
                CompanyRegionPresence.company_id,
                CompanyRegionPresence.presence_id,
            )
        ).scalars()
    )
    hiring_by_region = _rows_by_region(
        session.execute(
            select(CompanyRegionHiring)
            .where(CompanyRegionHiring.region_id.in_(region_ids))
            .order_by(
                CompanyRegionHiring.region_id,
                CompanyRegionHiring.company_id,
                CompanyRegionHiring.hiring_id,
            )
        ).scalars()
    )
    entry_by_region = _rows_by_region(
        session.execute(
            select(CompanyRegionEntryLevel)
            .where(CompanyRegionEntryLevel.region_id.in_(region_ids))
            .order_by(
                CompanyRegionEntryLevel.region_id,
                CompanyRegionEntryLevel.company_id,
                CompanyRegionEntryLevel.entry_level_id,
            )
        ).scalars()
    )
    company_ids = sorted(
        {
            row.company_id
            for grouped in (presence_by_region, hiring_by_region, entry_by_region)
            for rows in grouped.values()
            for row in rows
        }
    )
    companies_by_id = {
        row.company_id: row
        for row in session.execute(
            select(Company)
            .where(Company.company_id.in_(company_ids))
            .order_by(Company.company_id)
        ).scalars()
    }

    components: dict[str, tuple[Any, ...]] = {}
    fact_refs_by_market: dict[str, tuple[tuple[str, str], ...]] = {}
    for entry in entries:
        presence = presence_by_region.get(entry.region_id, ())
        hiring = hiring_by_region.get(entry.region_id, ())
        entry_level = entry_by_region.get(entry.region_id, ())
        market_company_ids = sorted(
            {
                *(row.company_id for row in presence),
                *(row.company_id for row in hiring),
                *(row.company_id for row in entry_level),
            }
        )
        companies = tuple(
            companies_by_id[company_id]
            for company_id in market_company_ids
            if company_id in companies_by_id
        )
        components[entry.market_key] = (companies, presence, hiring, entry_level)
        fact_refs_by_market[entry.market_key] = _fact_refs(
            entry.region_id,
            companies,
            presence,
            hiring,
            entry_level,
        )

    all_fact_refs = tuple(
        sorted({fact_ref for refs in fact_refs_by_market.values() for fact_ref in refs})
    )
    all_links = _all_fact_links_by_fact(session, all_fact_refs)
    ranking_eligible = _ranking_eligible_by_fact(session, all_fact_refs)
    routing = _latest_routing_decisions(session, all_fact_refs)
    source_prefixes = tuple(f"src_{entry.market_key}_%" for entry in entries)
    source_rows = session.execute(
        select(SourceRef)
        .where(or_(*(SourceRef.source_id.like(prefix) for prefix in source_prefixes)))
        .order_by(SourceRef.source_id)
    ).scalars()
    all_sources_by_id = {row.source_id: row for row in source_rows}

    snapshots: list[MarketOperationalSnapshot] = []
    for entry in entries:
        validation = validate_curated_market_dataset(
            entry.market_key,
            registry_path=registry_path,
            as_of=reference_date,
            stale_after_days=stale_after_days,
        )
        dataset = _safe_load_dataset(entry.dataset_path)
        source_file_rows = (
            dict(sorted(dataset.source_refs.items())) if dataset is not None else {}
        )
        proposed_fact_source_ids = (
            _proposed_fact_source_ids(dataset) if dataset is not None else {}
        )
        companies, presence, hiring, entry_level = components[entry.market_key]
        prefix = f"src_{entry.market_key}_"
        market_links = {
            fact_ref: tuple(
                link for link in all_links.get(fact_ref, ()) if link.source_id.startswith(prefix)
            )
            for fact_ref in fact_refs_by_market[entry.market_key]
        }
        market_sources = {
            source_id: row
            for source_id, row in all_sources_by_id.items()
            if source_id.startswith(prefix)
        }
        source_link_refs = _source_fact_refs(market_links)
        sources = _source_snapshots(
            source_rows_by_id=market_sources,
            source_file_rows=source_file_rows,
            fact_refs_by_source=source_link_refs,
            as_of=reference_date,
            stale_after_days=stale_after_days,
        )
        facts = _fact_snapshots(
            region=regions_by_id.get(entry.region_id),
            companies=companies,
            presence=presence,
            hiring=hiring,
            entry_level=entry_level,
            links_by_fact=market_links,
            ranking_eligible=ranking_eligible,
            routing=routing,
        )
        snapshots.append(
            MarketOperationalSnapshot(
                market_key=entry.market_key,
                region_id=entry.region_id,
                display_name=entry.display_name,
                registry_entry=entry,
                validation=validation,
                validation_issues=_public_validation_issues(validation),
                missing_required_files=_missing_required_files(validation),
                region=regions_by_id.get(entry.region_id),
                companies=companies,
                presence_facts=presence,
                hiring_facts=hiring,
                entry_level_facts=entry_level,
                sources=sources,
                facts=facts,
                source_rows=source_file_rows,
                proposed_fact_source_ids=proposed_fact_source_ids,
            )
        )
    return tuple(snapshots)


def _rows_by_region(rows: Any) -> dict[str, tuple[Any, ...]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[row.region_id].append(row)
    return {region_id: tuple(values) for region_id, values in grouped.items()}


def _all_fact_links_by_fact(
    session: Session,
    fact_refs: tuple[tuple[str, str], ...],
) -> dict[tuple[str, str], tuple[FactSourceLink, ...]]:
    grouped: dict[str, set[str]] = {}
    for fact_type, fact_id in fact_refs:
        grouped.setdefault(fact_type, set()).add(fact_id)
    result: dict[tuple[str, str], list[FactSourceLink]] = defaultdict(list)
    for fact_type, fact_ids in sorted(grouped.items()):
        rows = session.execute(
            select(FactSourceLink)
            .where(FactSourceLink.fact_type == fact_type)
            .where(FactSourceLink.fact_id.in_(sorted(fact_ids)))
            .order_by(
                FactSourceLink.fact_type,
                FactSourceLink.fact_id,
                FactSourceLink.source_id,
                FactSourceLink.link_id,
            )
        ).scalars()
        for row in rows:
            result[(row.fact_type, row.fact_id)].append(row)
    return {key: tuple(values) for key, values in result.items()}


def _resolve_entry(
    market_key: str,
    registry_path: str | Path | None,
) -> CuratedMarketRegistryEntry:
    try:
        return resolve_market_registry_entry(market_key, registry_path)
    except KeyError as exc:
        raise UnknownCuratedMarket(market_key) from exc
    except MarketRegistryError as exc:
        fallback = _fallback_registry_entry(market_key, registry_path)
        if fallback is not None:
            return fallback
        raise CuratedMarketRegistryUnavailable("curated market registry is invalid") from exc


def _fallback_registry_entry(
    market_key: str,
    registry_path: str | Path | None,
) -> CuratedMarketRegistryEntry | None:
    """Read a single registry row when validation failed because files drifted.

    This fallback is intentionally narrow and read-only. It exists so diagnostics
    can report validation failures, such as a proposed region mismatch, instead
    of failing before a public-safe report can be produced.
    """

    if registry_path is None:
        return None
    path = Path(registry_path)
    if path.name != MARKET_REGISTRY_FILE or not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, list):
        return None
    for item in raw:
        if not isinstance(item, dict) or _text(item.get("market_key")) != market_key:
            continue
        dataset_path = Path(_text(item.get("dataset_path")))
        if not dataset_path.is_absolute():
            dataset_path = path.parent / dataset_path
        return CuratedMarketRegistryEntry(
            market_key=market_key,
            region_id=_text(item.get("region_id")),
            display_name=_text(item.get("display_name")) or market_key,
            dataset_path=dataset_path.resolve(),
            coverage_status=_text(item.get("coverage_status")) or "partial_curated",
            import_status=_text(item.get("import_status")) or "ready",
            last_curated_at=_text(item.get("last_curated_at")),
            peer_group=_text(item.get("peer_group")),
            notes=_text(item.get("notes")) or None,
            warnings=(),
        )
    return None


def _coerce_date(value: date | datetime | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    return value


def _safe_load_dataset(dataset_path: Path) -> Any | None:
    try:
        return _load_dataset(dataset_path)
    except (OSError, UnicodeError, ValueError, KeyError):
        return None


def _presence_rows(session: Session, region_id: str) -> tuple[CompanyRegionPresence, ...]:
    rows = session.execute(
        select(CompanyRegionPresence)
        .where(CompanyRegionPresence.region_id == region_id)
        .order_by(CompanyRegionPresence.company_id, CompanyRegionPresence.presence_id)
    ).scalars()
    return tuple(rows)


def _hiring_rows(session: Session, region_id: str) -> tuple[CompanyRegionHiring, ...]:
    rows = session.execute(
        select(CompanyRegionHiring)
        .where(CompanyRegionHiring.region_id == region_id)
        .order_by(CompanyRegionHiring.company_id, CompanyRegionHiring.hiring_id)
    ).scalars()
    return tuple(rows)


def _entry_level_rows(
    session: Session,
    region_id: str,
) -> tuple[CompanyRegionEntryLevel, ...]:
    rows = session.execute(
        select(CompanyRegionEntryLevel)
        .where(CompanyRegionEntryLevel.region_id == region_id)
        .order_by(CompanyRegionEntryLevel.company_id, CompanyRegionEntryLevel.entry_level_id)
    ).scalars()
    return tuple(rows)


def _company_rows(session: Session, company_ids: list[str]) -> tuple[Company, ...]:
    if not company_ids:
        return ()
    rows = session.execute(
        select(Company).where(Company.company_id.in_(company_ids)).order_by(Company.company_id)
    ).scalars()
    return tuple(rows)


def _source_rows_by_id(session: Session, market_key: str) -> dict[str, SourceRef]:
    rows = session.execute(
        select(SourceRef)
        .where(SourceRef.source_id.like(f"src_{market_key}_%"))
        .order_by(SourceRef.source_id)
    ).scalars()
    return {row.source_id: row for row in rows}


def _fact_refs(
    region_id: str,
    companies: tuple[Company, ...],
    presence: tuple[CompanyRegionPresence, ...],
    hiring: tuple[CompanyRegionHiring, ...],
    entry_level: tuple[CompanyRegionEntryLevel, ...],
) -> tuple[tuple[str, str], ...]:
    refs: list[tuple[str, str]] = []
    if region_id:
        refs.append((FactBindingType.REGION.value, region_id))
    refs.extend((FactBindingType.COMPANY.value, row.company_id) for row in companies)
    refs.extend(
        (FactBindingType.COMPANY_REGION_PRESENCE.value, row.presence_id) for row in presence
    )
    refs.extend((FactBindingType.COMPANY_REGION_HIRING.value, row.hiring_id) for row in hiring)
    refs.extend(
        (FactBindingType.COMPANY_REGION_ENTRY_LEVEL.value, row.entry_level_id)
        for row in entry_level
    )
    return tuple(sorted(set(refs)))


def _fact_links_by_fact(
    session: Session,
    fact_refs: tuple[tuple[str, str], ...],
    *,
    market_key: str,
) -> dict[tuple[str, str], tuple[FactSourceLink, ...]]:
    grouped: dict[str, set[str]] = {}
    for fact_type, fact_id in fact_refs:
        grouped.setdefault(fact_type, set()).add(fact_id)

    result: dict[tuple[str, str], tuple[FactSourceLink, ...]] = {}
    for fact_type, fact_ids in sorted(grouped.items()):
        rows = session.execute(
            select(FactSourceLink)
            .where(FactSourceLink.fact_type == fact_type)
            .where(FactSourceLink.fact_id.in_(sorted(fact_ids)))
            .where(FactSourceLink.source_id.like(f"src_{market_key}_%"))
            .order_by(
                FactSourceLink.fact_type,
                FactSourceLink.fact_id,
                FactSourceLink.source_id,
                FactSourceLink.link_id,
            )
        ).scalars()
        for row in rows:
            key = (row.fact_type, row.fact_id)
            result.setdefault(key, ())
            result[key] = (*result[key], row)
    return result


def _ranking_eligible_by_fact(
    session: Session,
    fact_refs: tuple[tuple[str, str], ...],
) -> dict[tuple[str, str], bool]:
    grouped: dict[str, set[str]] = {}
    for fact_type, fact_id in fact_refs:
        grouped.setdefault(fact_type, set()).add(fact_id)

    result: dict[tuple[str, str], bool] = {}
    for fact_type, fact_ids in sorted(grouped.items()):
        eligible = ranking_eligible_fact_ids(
            session,
            fact_type,
            tuple(sorted(fact_ids)),
            allow_legacy_unassessed=False,
        )
        for fact_id in fact_ids:
            result[(fact_type, fact_id)] = fact_id in eligible
    return result


def _latest_routing_decisions(
    session: Session,
    fact_refs: tuple[tuple[str, str], ...],
) -> dict[tuple[str, str], RiskRoutingDecision]:
    grouped: dict[str, set[str]] = {}
    subject_to_fact: dict[tuple[str, str], tuple[str, str]] = {}
    for fact_type, fact_id in fact_refs:
        subject_type = FACT_SUBJECT_TYPES.get(fact_type)
        if subject_type is None:
            continue
        grouped.setdefault(subject_type.value, set()).add(fact_id)
        subject_to_fact[(subject_type.value, fact_id)] = (fact_type, fact_id)

    latest: dict[tuple[str, str], RiskRoutingDecision] = {}
    for subject_type, subject_ids in sorted(grouped.items()):
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
            fact_key = subject_to_fact[(row.subject_type, row.subject_id)]
            latest.setdefault(fact_key, row)
    return latest


def _source_fact_refs(
    links_by_fact: dict[tuple[str, str], tuple[FactSourceLink, ...]],
) -> dict[str, tuple[tuple[str, str], ...]]:
    refs: dict[str, set[tuple[str, str]]] = {}
    for fact_key, links in links_by_fact.items():
        for link in links:
            refs.setdefault(link.source_id, set()).add(fact_key)
    return {source_id: tuple(sorted(fact_refs)) for source_id, fact_refs in sorted(refs.items())}


def _source_snapshots(
    *,
    source_rows_by_id: dict[str, SourceRef],
    source_file_rows: dict[str, dict[str, str]],
    fact_refs_by_source: dict[str, tuple[tuple[str, str], ...]],
    as_of: date,
    stale_after_days: int,
) -> tuple[SourceSnapshot, ...]:
    source_ids = sorted(set(source_rows_by_id) | set(source_file_rows))
    return tuple(
        _source_snapshot(
            source_id,
            row=source_rows_by_id.get(source_id),
            file_row=source_file_rows.get(source_id),
            fact_refs=fact_refs_by_source.get(source_id, ()),
            as_of=as_of,
            stale_after_days=stale_after_days,
        )
        for source_id in source_ids
    )


def _source_snapshot(
    source_id: str,
    *,
    row: SourceRef | None,
    file_row: dict[str, str] | None,
    fact_refs: tuple[tuple[str, str], ...],
    as_of: date,
    stale_after_days: int,
) -> SourceSnapshot:
    observed_date = _source_observed_date(row, file_row)
    collected_date = _source_collected_date(row, file_row)
    age_days = (as_of - observed_date).days if observed_date is not None else None
    stored_freshness = (
        row.freshness_status
        if row is not None
        else _optional_text(file_row.get("freshness_status"))
        if file_row
        else None
    )
    status = _operational_source_status(
        observed_date=observed_date,
        age_days=age_days,
        stored_freshness=stored_freshness,
        stale_after_days=stale_after_days,
    )
    return SourceSnapshot(
        source_id=source_id,
        source_label=(
            row.source_name
            if row is not None
            else _optional_text(file_row.get("source_name"))
            if file_row
            else source_id
        )
        or source_id,
        source_type=(
            row.source_type
            if row is not None
            else _optional_text(file_row.get("source_type"))
            if file_row
            else "unknown"
        )
        or "unknown",
        observed_date=observed_date,
        collected_date=collected_date,
        age_days=age_days,
        freshness_status=status,
        stored_freshness_status=stored_freshness,
        confidence=(
            row.confidence
            if row is not None
            else _optional_text(file_row.get("confidence"))
            if file_row
            else "unknown"
        )
        or "unknown",
        license_or_terms_category=(
            row.license_or_terms_category
            if row is not None
            else _optional_text(file_row.get("license_or_terms_category"))
            if file_row
            else None
        ),
        fact_refs=tuple(sorted(fact_refs)),
    )


def _operational_source_status(
    *,
    observed_date: date | None,
    age_days: int | None,
    stored_freshness: str | None,
    stale_after_days: int,
) -> OperationalSourceFreshnessStatus:
    if observed_date is None or stored_freshness == FreshnessStatus.UNKNOWN.value:
        return OperationalSourceFreshnessStatus.NEEDS_REVIEW
    if stored_freshness == FreshnessStatus.STALE.value:
        return OperationalSourceFreshnessStatus.STALE
    if age_days is None:
        return OperationalSourceFreshnessStatus.NEEDS_REVIEW
    if age_days > EXPIRED_AFTER_DAYS:
        return OperationalSourceFreshnessStatus.EXPIRED
    if age_days > stale_after_days:
        return OperationalSourceFreshnessStatus.STALE
    if age_days >= AGING_AFTER_DAYS:
        return OperationalSourceFreshnessStatus.AGING
    return OperationalSourceFreshnessStatus.CURRENT


def _fact_snapshots(
    *,
    region: Region | None,
    companies: tuple[Company, ...],
    presence: tuple[CompanyRegionPresence, ...],
    hiring: tuple[CompanyRegionHiring, ...],
    entry_level: tuple[CompanyRegionEntryLevel, ...],
    links_by_fact: dict[tuple[str, str], tuple[FactSourceLink, ...]],
    ranking_eligible: dict[tuple[str, str], bool],
    routing: dict[tuple[str, str], RiskRoutingDecision],
) -> tuple[FactSnapshot, ...]:
    facts: list[FactSnapshot] = []
    if region is not None:
        facts.append(
            _fact_snapshot(
                fact_type=FactBindingType.REGION.value,
                fact_id=region.region_id,
                area=FactArea.REGION,
                company_id=None,
                region_id=region.region_id,
                observation_status=ObservationStatus.POSITIVE_OBSERVED.value,
                count_statuses=(),
                links_by_fact=links_by_fact,
                ranking_eligible=ranking_eligible,
                routing=routing,
            )
        )
    for row in companies:
        facts.append(
            _fact_snapshot(
                fact_type=FactBindingType.COMPANY.value,
                fact_id=row.company_id,
                area=FactArea.COMPANY,
                company_id=row.company_id,
                region_id=None,
                observation_status=ObservationStatus.POSITIVE_OBSERVED.value,
                count_statuses=(),
                links_by_fact=links_by_fact,
                ranking_eligible=ranking_eligible,
                routing=routing,
            )
        )
    for row in presence:
        facts.append(
            _fact_snapshot(
                fact_type=FactBindingType.COMPANY_REGION_PRESENCE.value,
                fact_id=row.presence_id,
                area=FactArea.PRESENCE,
                company_id=row.company_id,
                region_id=row.region_id,
                observation_status=_presence_observation_status(row),
                count_statuses=(),
                links_by_fact=links_by_fact,
                ranking_eligible=ranking_eligible,
                routing=routing,
            )
        )
    for row in hiring:
        facts.append(
            _fact_snapshot(
                fact_type=FactBindingType.COMPANY_REGION_HIRING.value,
                fact_id=row.hiring_id,
                area=FactArea.HIRING,
                company_id=row.company_id,
                region_id=row.region_id,
                observation_status=(
                    row.active_posting_count_now_status or ObservationStatus.UNKNOWN.value
                ),
                count_statuses=(
                    row.active_posting_count_now_status or ObservationStatus.UNKNOWN.value,
                    row.posting_count_30d_status or ObservationStatus.NOT_COLLECTED.value,
                    row.posting_count_90d_status or ObservationStatus.NOT_COLLECTED.value,
                ),
                links_by_fact=links_by_fact,
                ranking_eligible=ranking_eligible,
                routing=routing,
                freshness_expires_at=row.freshness_expires_at,
            )
        )
    for row in entry_level:
        facts.append(
            _fact_snapshot(
                fact_type=FactBindingType.COMPANY_REGION_ENTRY_LEVEL.value,
                fact_id=row.entry_level_id,
                area=FactArea.ENTRY_LEVEL,
                company_id=row.company_id,
                region_id=row.region_id,
                observation_status=_entry_level_status(row),
                count_statuses=(
                    row.internship_count_status or ObservationStatus.UNKNOWN.value,
                    row.coop_count_status or ObservationStatus.UNKNOWN.value,
                    row.entry_level_full_time_count_status or ObservationStatus.UNKNOWN.value,
                ),
                links_by_fact=links_by_fact,
                ranking_eligible=ranking_eligible,
                routing=routing,
                freshness_expires_at=row.freshness_expires_at,
            )
        )
    return tuple(sorted(facts, key=lambda item: (item.area.value, item.fact_id)))


def _fact_snapshot(
    *,
    fact_type: str,
    fact_id: str,
    area: FactArea,
    company_id: str | None,
    region_id: str | None,
    observation_status: str,
    count_statuses: tuple[str, ...],
    links_by_fact: dict[tuple[str, str], tuple[FactSourceLink, ...]],
    ranking_eligible: dict[tuple[str, str], bool],
    routing: dict[tuple[str, str], RiskRoutingDecision],
    freshness_expires_at: datetime | None = None,
) -> FactSnapshot:
    key = (fact_type, fact_id)
    links = links_by_fact.get(key, ())
    decision = routing.get(key)
    reason_codes = (
        tuple(str(item) for item in decision.ranking_influence_reason_codes_json)
        if decision is not None
        else ()
    )
    source_ids = tuple(sorted({link.source_id for link in links}))
    freshness = _fact_freshness(links, freshness_expires_at=freshness_expires_at)
    return FactSnapshot(
        fact_type=fact_type,
        fact_id=fact_id,
        area=area,
        company_id=company_id,
        region_id=region_id,
        observation_status=observation_status,
        freshness_status=freshness,
        confidence=_aggregate_confidence(links),
        source_ids=source_ids,
        ranking_eligible=ranking_eligible.get(key, False),
        ranking_reason_codes=reason_codes,
        trust_tier=decision.trust_tier if decision is not None else None,
        risk_level=decision.risk_level if decision is not None else None,
        count_statuses=count_statuses,
    )


def _fact_freshness(
    links: tuple[FactSourceLink, ...],
    *,
    freshness_expires_at: datetime | None,
) -> str:
    statuses = {link.freshness_status for link in links if link.freshness_status}
    if FreshnessStatus.STALE.value in statuses:
        return FreshnessStatus.STALE.value
    if statuses == {FreshnessStatus.FRESH.value}:
        return FreshnessStatus.FRESH.value
    if freshness_expires_at is not None:
        return FreshnessStatus.UNKNOWN.value
    if statuses:
        return FreshnessStatus.UNKNOWN.value
    return FreshnessStatus.UNKNOWN.value


def _aggregate_confidence(links: tuple[FactSourceLink, ...]) -> str:
    if not links:
        return "unknown"
    values = {link.confidence for link in links if link.confidence}
    if Confidence.LOW.value in values:
        return Confidence.LOW.value
    if values == {Confidence.HIGH.value}:
        return Confidence.HIGH.value
    if Confidence.MEDIUM.value in values:
        return Confidence.MEDIUM.value
    return "unknown"


def _presence_observation_status(row: CompanyRegionPresence) -> str:
    if row.presence_status == "present":
        return ObservationStatus.POSITIVE_OBSERVED.value
    if row.presence_status == "not_present":
        return ObservationStatus.ZERO_OBSERVED.value
    return ObservationStatus.UNKNOWN.value


def _entry_level_status(row: CompanyRegionEntryLevel) -> str:
    statuses = (
        row.internship_count_status,
        row.coop_count_status,
        row.entry_level_full_time_count_status,
    )
    if any(status == ObservationStatus.UNKNOWN.value for status in statuses):
        return ObservationStatus.UNKNOWN.value
    if any(status == ObservationStatus.NOT_COLLECTED.value for status in statuses):
        return ObservationStatus.NOT_COLLECTED.value
    observed_values = (
        row.internship_count if row.internship_count_status == OBSERVED_ZERO_STATUS else None,
        row.coop_count if row.coop_count_status == OBSERVED_ZERO_STATUS else None,
        row.entry_level_full_time_count
        if row.entry_level_full_time_count_status == OBSERVED_ZERO_STATUS
        else None,
    )
    if any(value == 0 for value in observed_values):
        return ObservationStatus.ZERO_OBSERVED.value
    return ObservationStatus.POSITIVE_OBSERVED.value


def _proposed_fact_source_ids(dataset: Any) -> dict[tuple[str, str], tuple[str, ...]]:
    result: dict[tuple[str, str], tuple[str, ...]] = {}
    for region in dataset.regions:
        region_id = _text(region.get("region_id"))
        source_id = _text(region.get("source_ref"))
        if region_id and source_id:
            result[(FactBindingType.REGION.value, region_id)] = (source_id,)
    for company in dataset.companies:
        company_id = _text(company.get("company_id"))
        source_id = _text(company.get("source_ref"))
        if company_id and source_id:
            result[(FactBindingType.COMPANY.value, company_id)] = (source_id,)
    for row in dataset.presence:
        company_id = _text(row.get("company_id"))
        region_id = _text(row.get("region_id"))
        source_id = _text(row.get("source_ref"))
        if company_id and region_id and source_id:
            result[
                (
                    FactBindingType.COMPANY_REGION_PRESENCE.value,
                    _presence_id(company_id, region_id),
                )
            ] = (source_id,)
    for group in _hiring_groups(dataset.hiring):
        source_ids = tuple(sorted({_text(row.get("source_ref")) for row in group.rows if row}))
        result[
            (
                FactBindingType.COMPANY_REGION_HIRING.value,
                _hiring_id(group.company_id, group.region_id),
            )
        ] = tuple(source_id for source_id in source_ids if source_id)
    for row in dataset.entry_level:
        company_id = _text(row.get("company_id"))
        region_id = _text(row.get("region_id"))
        source_id = _text(row.get("source_ref"))
        if company_id and region_id and source_id:
            result[
                (
                    FactBindingType.COMPANY_REGION_ENTRY_LEVEL.value,
                    f"entry_{company_id}_{region_id}",
                )
            ] = (source_id,)
    return dict(sorted(result.items()))


def _public_validation_issues(
    validation: ImportValidationResult,
) -> tuple[PublicIssue, ...]:
    issues = [
        PublicIssue(
            code=issue.code,
            message=_safe_validation_message(issue.code),
            field=issue.field,
            file=issue.file,
            record_id=issue.record_id,
        )
        for issue in (*validation.errors, *validation.warnings)
    ]
    return tuple(
        sorted(
            issues,
            key=lambda item: (item.file or "", item.code, item.record_id or ""),
        )
    )


def _missing_required_files(validation: ImportValidationResult) -> tuple[str, ...]:
    files = [
        issue.file
        for issue in validation.errors
        if issue.code == "missing_required_file" and issue.file in REQUIRED_DATASET_FILES
    ]
    return tuple(sorted(files))


def _safe_validation_message(code: str) -> str:
    return {
        "missing_required_file": "A required curated import file is missing.",
        "missing_required_field": "A required curated import field is missing.",
        "stale_source_date": "A source observation is older than the supported import window.",
        "invalid_market_key": "The requested market is not registered.",
        "invalid_dataset_path": "A registered market dataset path is invalid.",
        "file_read_error": "A curated import file could not be read safely.",
    }.get(code, "Curated import validation reported an issue.")


def _source_observed_date(row: SourceRef | None, file_row: dict[str, str] | None) -> date | None:
    if row is not None and row.observed_at is not None:
        return row.observed_at.date()
    if file_row and _optional_text(file_row.get("observed_at")):
        try:
            return parse_import_date(file_row["observed_at"])
        except ValueError:
            return None
    return None


def _source_collected_date(row: SourceRef | None, file_row: dict[str, str] | None) -> date | None:
    if row is not None and row.collected_at is not None:
        return row.collected_at.date()
    if file_row and _optional_text(file_row.get("collected_at")):
        try:
            return parse_import_date(file_row["collected_at"])
        except ValueError:
            return None
    return None


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def routing_public_reason_codes(
    decision: RiskRoutingDecision | None,
) -> tuple[str, ...]:
    if decision is None:
        return (RankingInfluenceReasonCode.ASSESSMENT_MISSING.value,)
    try:
        result = routing_decision_from_row(decision)
    except ValueError:
        return (RankingInfluenceReasonCode.RANKING_DEFAULT_DENIED.value,)
    return tuple(code.value for code in result.ranking_influence_reason_codes)


def source_file_rows_for_market(
    market_key: str,
    *,
    registry_path: str | Path | None = None,
) -> dict[str, dict[str, str]]:
    entry = _resolve_entry(market_key, registry_path)
    dataset = _safe_load_dataset(entry.dataset_path)
    return dict(sorted(dataset.source_refs.items())) if dataset is not None else {}
