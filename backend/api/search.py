"""Read-only Layer 5 search contracts and helpers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.metadata import (
    ApiDataBasis,
    ApiFreshnessStatus,
    FreshnessSourceSummary,
    build_freshness_source_summary,
)
from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink
from backend.scoring.models import RegionMarketScore
from backend.shared.provenance import FactBindingType


class RegionSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str
    name: str
    region_name: str
    region_type: str
    parent_region_id: str | None = None
    labor_market_group: str | None = None
    opportunity_score: float | None = None
    freshness: FreshnessSourceSummary
    has_real_data: bool = False


class RegionSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    regions: list[RegionSearchResult] = Field(default_factory=list)
    count: int


class CompanySearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: str
    name: str
    sector: str | None = None
    industry: str | None = None
    role_families: list[str] = Field(default_factory=list)
    matched_region_ids: list[str] = Field(default_factory=list)
    current_hiring: bool = False
    has_entry_level_access: bool = False
    presence_status: str | None = None
    freshness: FreshnessSourceSummary
    has_real_data: bool = False


class CompanySearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    companies: list[CompanySearchResult] = Field(default_factory=list)
    count: int


class CompanyRegionGeographyResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str
    region_name: str
    presence_status: str | None = None
    current_hiring: bool = False
    has_entry_level_access: bool = False
    freshness: FreshnessSourceSummary
    has_real_data: bool = False


class CompanyGeographyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: str
    company_name: str
    regions: list[CompanyRegionGeographyResult] = Field(default_factory=list)
    count: int


class SourceDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    source_type: str
    source_name: str
    url: str | None = None
    collected_at: datetime | None = None
    freshness_status: ApiFreshnessStatus
    data_basis: ApiDataBasis


class SourceExplanationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_type: Literal["company", "region"]
    subject_id: str
    freshness: FreshnessSourceSummary
    sources: list[SourceDetail] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def search_regions(
    session: Session,
    *,
    query: str | None = None,
    region_type: str | None = None,
    has_real_data: bool | None = None,
    freshness_status: ApiFreshnessStatus | None = None,
    min_opportunity_score: float | None = None,
) -> RegionSearchResponse:
    regions = _list_regions(session)
    scores_by_region = {
        score.region_id: score
        for score in session.execute(
            select(RegionMarketScore).order_by(RegionMarketScore.region_id)
        ).scalars()
    }
    presence_by_region = _group_by_region(_list_presence(session))
    hiring_by_region = _group_by_region(_list_hiring(session))
    entry_by_region = _group_by_region(_list_entry_level(session))
    links = _ProvenanceIndex(_list_fact_source_links(session))

    items: list[RegionSearchResult] = []
    for region in regions:
        if query and not _matches_text(
            query,
            region.region_id,
            region.region_name,
            region.display_name,
            region.labor_market_group,
        ):
            continue
        if region_type is not None and region.region_type != region_type:
            continue

        score = scores_by_region.get(region.region_id)
        opportunity_score = (
            score.objective_opportunity_score if score is not None else None
        )
        if (
            min_opportunity_score is not None
            and (
                opportunity_score is None
                or opportunity_score < min_opportunity_score
            )
        ):
            continue

        presence_rows = presence_by_region.get(region.region_id, ())
        hiring_rows = hiring_by_region.get(region.region_id, ())
        entry_rows = entry_by_region.get(region.region_id, ())
        evidence = _region_evidence_links(
            links,
            region=region,
            score=score,
            presence_rows=presence_rows,
            hiring_rows=hiring_rows,
            entry_level_rows=entry_rows,
        )
        freshness = build_freshness_source_summary(
            evidence,
            freshness_expires_at=_aggregate_freshness_expires_at(
                *(row.freshness_expires_at for row in hiring_rows),
                *(row.freshness_expires_at for row in entry_rows),
            ),
        )
        has_real = _has_real_data(freshness)
        if has_real_data is not None and has_real is not has_real_data:
            continue
        if (
            freshness_status is not None
            and freshness.freshness_status is not freshness_status
        ):
            continue

        items.append(
            RegionSearchResult(
                region_id=region.region_id,
                name=region.display_name,
                region_name=region.region_name,
                region_type=region.region_type,
                parent_region_id=region.parent_region_id,
                labor_market_group=region.labor_market_group,
                opportunity_score=opportunity_score,
                freshness=freshness,
                has_real_data=has_real,
            )
        )

    return RegionSearchResponse(regions=items, count=len(items))


def search_companies(
    session: Session,
    *,
    query: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    role_family: str | None = None,
    region_id: str | None = None,
    current_hiring: bool | None = None,
    has_entry_level_access: bool | None = None,
    presence_status: str | None = None,
) -> CompanySearchResponse:
    companies = _list_companies(session)
    presence_by_company = _group_by_company(_list_presence(session))
    hiring_by_company = _group_by_company(_list_hiring(session))
    entry_by_company = _group_by_company(_list_entry_level(session))
    links = _ProvenanceIndex(_list_fact_source_links(session))

    items: list[CompanySearchResult] = []
    for company in companies:
        if query and not _matches_text(
            query,
            company.company_id,
            company.company_name,
            company.normalized_company_name,
            company.sector_primary,
            company.sector_secondary,
        ):
            continue
        if sector is not None and not _matches_exact(sector, company.sector_primary):
            continue
        if industry is not None and not _matches_exact(industry, company.sector_secondary):
            continue

        presence_rows = _filter_region(
            presence_by_company.get(company.company_id, ()),
            region_id=region_id,
        )
        hiring_rows = _filter_region(
            hiring_by_company.get(company.company_id, ()),
            region_id=region_id,
        )
        entry_rows = _filter_region(
            entry_by_company.get(company.company_id, ()),
            region_id=region_id,
        )
        if region_id is not None and not (presence_rows or hiring_rows or entry_rows):
            continue
        if (
            presence_status is not None
            and not any(row.presence_status == presence_status for row in presence_rows)
        ):
            continue
        if role_family is not None and not _has_role_family(hiring_rows, role_family):
            continue

        company_current_hiring = any(row.currently_hiring_flag for row in hiring_rows)
        if (
            current_hiring is not None
            and company_current_hiring is not current_hiring
        ):
            continue
        company_has_entry_level = any(_entry_level_access_present(row) for row in entry_rows)
        if (
            has_entry_level_access is not None
            and company_has_entry_level is not has_entry_level_access
        ):
            continue

        evidence = _company_evidence_links(
            links,
            company=company,
            presence_rows=presence_rows,
            hiring_rows=hiring_rows,
            entry_level_rows=entry_rows,
        )
        freshness = build_freshness_source_summary(
            evidence,
            freshness_expires_at=_aggregate_freshness_expires_at(
                *(row.freshness_expires_at for row in hiring_rows),
                *(row.freshness_expires_at for row in entry_rows),
            ),
        )
        items.append(
            CompanySearchResult(
                company_id=company.company_id,
                name=company.company_name,
                sector=company.sector_primary,
                industry=company.sector_secondary,
                role_families=_role_families(hiring_rows),
                matched_region_ids=_matched_region_ids(
                    presence_rows,
                    hiring_rows,
                    entry_rows,
                ),
                current_hiring=company_current_hiring,
                has_entry_level_access=company_has_entry_level,
                presence_status=_presence_status(presence_rows),
                freshness=freshness,
                has_real_data=_has_real_data(freshness),
            )
        )

    return CompanySearchResponse(companies=items, count=len(items))


def company_geography(
    session: Session,
    *,
    company_id: str,
) -> CompanyGeographyResponse | None:
    company = session.get(Company, company_id)
    if company is None:
        return None

    regions_by_id = {region.region_id: region for region in _list_regions(session)}
    presence_rows = tuple(
        row for row in _list_presence(session) if row.company_id == company.company_id
    )
    hiring_rows = tuple(
        row for row in _list_hiring(session) if row.company_id == company.company_id
    )
    entry_rows = tuple(
        row for row in _list_entry_level(session) if row.company_id == company.company_id
    )
    links = _ProvenanceIndex(_list_fact_source_links(session))

    items: list[CompanyRegionGeographyResult] = []
    for region_id in _matched_region_ids(presence_rows, hiring_rows, entry_rows):
        region = regions_by_id.get(region_id)
        if region is None:
            continue

        region_presence_rows = _filter_region(presence_rows, region_id=region_id)
        region_hiring_rows = _filter_region(hiring_rows, region_id=region_id)
        region_entry_rows = _filter_region(entry_rows, region_id=region_id)
        evidence = _company_region_evidence_links(
            links,
            presence_rows=region_presence_rows,
            hiring_rows=region_hiring_rows,
            entry_level_rows=region_entry_rows,
        )
        freshness = build_freshness_source_summary(
            evidence,
            freshness_expires_at=_aggregate_freshness_expires_at(
                *(row.freshness_expires_at for row in region_hiring_rows),
                *(row.freshness_expires_at for row in region_entry_rows),
            ),
        )
        items.append(
            CompanyRegionGeographyResult(
                region_id=region.region_id,
                region_name=region.display_name,
                presence_status=_presence_status(region_presence_rows),
                current_hiring=any(row.currently_hiring_flag for row in region_hiring_rows),
                has_entry_level_access=any(
                    _entry_level_access_present(row) for row in region_entry_rows
                ),
                freshness=freshness,
                has_real_data=_has_real_data(freshness),
            )
        )

    return CompanyGeographyResponse(
        company_id=company.company_id,
        company_name=company.company_name,
        regions=items,
        count=len(items),
    )


def explain_region_sources(
    session: Session,
    *,
    region_id: str,
) -> SourceExplanationResponse | None:
    region = session.get(Region, region_id)
    if region is None:
        return None

    presence_rows = tuple(
        row for row in _list_presence(session) if row.region_id == region.region_id
    )
    hiring_rows = tuple(
        row for row in _list_hiring(session) if row.region_id == region.region_id
    )
    entry_rows = tuple(
        row for row in _list_entry_level(session) if row.region_id == region.region_id
    )
    links = _ProvenanceIndex(_list_fact_source_links(session))
    evidence = _region_evidence_links(
        links,
        region=region,
        score=_region_score(session, region.region_id),
        presence_rows=presence_rows,
        hiring_rows=hiring_rows,
        entry_level_rows=entry_rows,
    )
    freshness = build_freshness_source_summary(
        evidence,
        freshness_expires_at=_aggregate_freshness_expires_at(
            *(row.freshness_expires_at for row in hiring_rows),
            *(row.freshness_expires_at for row in entry_rows),
        ),
    )
    return SourceExplanationResponse(
        subject_type="region",
        subject_id=region.region_id,
        freshness=freshness,
        sources=_source_details(evidence),
        warnings=_warnings(freshness),
    )


def explain_company_sources(
    session: Session,
    *,
    company_id: str,
) -> SourceExplanationResponse | None:
    company = session.get(Company, company_id)
    if company is None:
        return None

    presence_rows = tuple(
        row for row in _list_presence(session) if row.company_id == company.company_id
    )
    hiring_rows = tuple(
        row for row in _list_hiring(session) if row.company_id == company.company_id
    )
    entry_rows = tuple(
        row for row in _list_entry_level(session) if row.company_id == company.company_id
    )
    links = _ProvenanceIndex(_list_fact_source_links(session))
    evidence = _company_evidence_links(
        links,
        company=company,
        presence_rows=presence_rows,
        hiring_rows=hiring_rows,
        entry_level_rows=entry_rows,
    )
    freshness = build_freshness_source_summary(
        evidence,
        freshness_expires_at=_aggregate_freshness_expires_at(
            *(row.freshness_expires_at for row in hiring_rows),
            *(row.freshness_expires_at for row in entry_rows),
        ),
    )
    return SourceExplanationResponse(
        subject_type="company",
        subject_id=company.company_id,
        freshness=freshness,
        sources=_source_details(evidence),
        warnings=_warnings(freshness),
    )


class _ProvenanceIndex:
    def __init__(self, links: Iterable[FactSourceLink]) -> None:
        self._by_key: dict[tuple[str, str], list[FactSourceLink]] = defaultdict(list)
        self._by_link_id: dict[str, FactSourceLink] = {}
        for link in links:
            self._by_key[(link.fact_type, link.fact_id)].append(link)
            self._by_link_id[link.link_id] = link

    def for_fact(
        self, fact_type: FactBindingType, fact_id: str | None
    ) -> list[FactSourceLink]:
        if fact_id is None:
            return []
        return list(self._by_key.get((fact_type.value, fact_id), ()))

    def for_source_refs(self, source_refs: object) -> list[FactSourceLink]:
        return [
            self._by_link_id[link_id]
            for link_id in _fact_source_link_ids(source_refs)
            if link_id in self._by_link_id
        ]


def _list_regions(session: Session) -> list[Region]:
    return list(session.execute(select(Region).order_by(Region.region_id)).scalars())


def _list_companies(session: Session) -> list[Company]:
    return list(session.execute(select(Company).order_by(Company.company_id)).scalars())


def _list_presence(session: Session) -> list[CompanyRegionPresence]:
    return list(
        session.execute(
            select(CompanyRegionPresence).order_by(
                CompanyRegionPresence.company_id,
                CompanyRegionPresence.region_id,
            )
        ).scalars()
    )


def _list_hiring(session: Session) -> list[CompanyRegionHiring]:
    return list(
        session.execute(
            select(CompanyRegionHiring).order_by(
                CompanyRegionHiring.company_id,
                CompanyRegionHiring.region_id,
            )
        ).scalars()
    )


def _list_entry_level(session: Session) -> list[CompanyRegionEntryLevel]:
    return list(
        session.execute(
            select(CompanyRegionEntryLevel).order_by(
                CompanyRegionEntryLevel.company_id,
                CompanyRegionEntryLevel.region_id,
            )
        ).scalars()
    )


def _list_fact_source_links(session: Session) -> list[FactSourceLink]:
    return list(
        session.execute(
            select(FactSourceLink).order_by(
                FactSourceLink.fact_type,
                FactSourceLink.fact_id,
                FactSourceLink.link_id,
            )
        ).scalars()
    )


def _region_score(session: Session, region_id: str) -> RegionMarketScore | None:
    return session.execute(
        select(RegionMarketScore)
        .where(RegionMarketScore.region_id == region_id)
        .order_by(RegionMarketScore.region_score_id)
    ).scalars().first()


def _region_evidence_links(
    links: _ProvenanceIndex,
    *,
    region: Region,
    score: RegionMarketScore | None,
    presence_rows: Iterable[CompanyRegionPresence],
    hiring_rows: Iterable[CompanyRegionHiring],
    entry_level_rows: Iterable[CompanyRegionEntryLevel],
) -> list[FactSourceLink]:
    evidence: list[FactSourceLink] = []
    evidence.extend(links.for_fact(FactBindingType.REGION, region.region_id))
    if score is not None:
        evidence.extend(links.for_fact(FactBindingType.SCORE_INPUT, score.region_score_id))
    for row in presence_rows:
        evidence.extend(_row_links(links, FactBindingType.COMPANY_REGION_PRESENCE, row))
    for row in hiring_rows:
        evidence.extend(_row_links(links, FactBindingType.COMPANY_REGION_HIRING, row))
    for row in entry_level_rows:
        evidence.extend(_row_links(links, FactBindingType.COMPANY_REGION_ENTRY_LEVEL, row))
    return _dedupe_links(evidence)


def _company_region_evidence_links(
    links: _ProvenanceIndex,
    *,
    presence_rows: Iterable[CompanyRegionPresence],
    hiring_rows: Iterable[CompanyRegionHiring],
    entry_level_rows: Iterable[CompanyRegionEntryLevel],
) -> list[FactSourceLink]:
    evidence: list[FactSourceLink] = []
    for row in presence_rows:
        evidence.extend(_row_links(links, FactBindingType.COMPANY_REGION_PRESENCE, row))
    for row in hiring_rows:
        evidence.extend(_row_links(links, FactBindingType.COMPANY_REGION_HIRING, row))
    for row in entry_level_rows:
        evidence.extend(_row_links(links, FactBindingType.COMPANY_REGION_ENTRY_LEVEL, row))
    return _dedupe_links(evidence)


def _company_evidence_links(
    links: _ProvenanceIndex,
    *,
    company: Company,
    presence_rows: Iterable[CompanyRegionPresence],
    hiring_rows: Iterable[CompanyRegionHiring],
    entry_level_rows: Iterable[CompanyRegionEntryLevel],
) -> list[FactSourceLink]:
    evidence: list[FactSourceLink] = []
    evidence.extend(links.for_fact(FactBindingType.COMPANY, company.company_id))
    for row in presence_rows:
        evidence.extend(_row_links(links, FactBindingType.COMPANY_REGION_PRESENCE, row))
    for row in hiring_rows:
        evidence.extend(_row_links(links, FactBindingType.COMPANY_REGION_HIRING, row))
    for row in entry_level_rows:
        evidence.extend(_row_links(links, FactBindingType.COMPANY_REGION_ENTRY_LEVEL, row))
    return _dedupe_links(evidence)


def _row_links(
    links: _ProvenanceIndex,
    fact_type: FactBindingType,
    row: object,
) -> list[FactSourceLink]:
    return [
        *links.for_fact(fact_type, _row_fact_id(row, fact_type)),
        *links.for_source_refs(getattr(row, "source_refs", None)),
    ]


def _row_fact_id(row: object, fact_type: FactBindingType) -> str | None:
    if fact_type is FactBindingType.COMPANY_REGION_PRESENCE:
        return getattr(row, "presence_id", None)
    if fact_type is FactBindingType.COMPANY_REGION_HIRING:
        return getattr(row, "hiring_id", None)
    if fact_type is FactBindingType.COMPANY_REGION_ENTRY_LEVEL:
        return getattr(row, "entry_level_id", None)
    return None


def _fact_source_link_ids(source_refs: object) -> tuple[str, ...]:
    if isinstance(source_refs, Mapping):
        value = source_refs.get("fact_source_link_id")
        return (value,) if isinstance(value, str) and value else ()
    if isinstance(source_refs, list):
        ids: list[str] = []
        for item in source_refs:
            if isinstance(item, Mapping):
                value = item.get("fact_source_link_id")
                if isinstance(value, str) and value:
                    ids.append(value)
        return tuple(ids)
    return ()


def _dedupe_links(links: Iterable[FactSourceLink]) -> list[FactSourceLink]:
    deduped: dict[str, FactSourceLink] = {}
    for link in links:
        deduped[link.link_id] = link
    return [deduped[link_id] for link_id in sorted(deduped)]


def _source_details(links: Iterable[FactSourceLink]) -> list[SourceDetail]:
    selected: dict[str, FactSourceLink] = {}
    for link in links:
        current = selected.get(link.source_id)
        if current is None or _source_detail_sort_key(link) > _source_detail_sort_key(
            current
        ):
            selected[link.source_id] = link

    return [
        _source_detail(selected[source_id])
        for source_id in sorted(selected)
    ]


def _source_detail(link: FactSourceLink) -> SourceDetail:
    summary = build_freshness_source_summary([link])
    return SourceDetail(
        source_id=link.source_id,
        source_type=link.source_type,
        source_name=link.source_name,
        url=link.url_or_provider,
        collected_at=_ensure_aware(link.collected_at),
        freshness_status=summary.freshness_status,
        data_basis=summary.data_basis,
    )


def _source_detail_sort_key(link: FactSourceLink) -> tuple[datetime, str]:
    return (_ensure_aware(link.collected_at), link.link_id)


def _warnings(summary: FreshnessSourceSummary) -> list[str]:
    return [summary.low_confidence_warning] if summary.low_confidence_warning else []


def _group_by_region(rows: Iterable[Any]) -> dict[str, tuple[Any, ...]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[row.region_id].append(row)
    return {key: tuple(value) for key, value in grouped.items()}


def _group_by_company(rows: Iterable[Any]) -> dict[str, tuple[Any, ...]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[row.company_id].append(row)
    return {key: tuple(value) for key, value in grouped.items()}


def _filter_region(rows: Iterable[Any], *, region_id: str | None) -> tuple[Any, ...]:
    if region_id is None:
        return tuple(rows)
    return tuple(row for row in rows if row.region_id == region_id)


def _matches_text(query: str, *values: str | None) -> bool:
    needle = query.casefold().strip()
    if not needle:
        return False
    return any(needle in value.casefold() for value in values if value)


def _matches_exact(query: str, value: str | None) -> bool:
    return value is not None and query.casefold().strip() == value.casefold()


def _has_role_family(
    hiring_rows: Iterable[CompanyRegionHiring], role_family: str
) -> bool:
    needle = role_family.casefold().strip()
    return any(
        key.casefold() == needle and count > 0
        for row in hiring_rows
        for key, count in _role_family_items(row.role_family_summary)
    )


def _role_families(hiring_rows: Iterable[CompanyRegionHiring]) -> list[str]:
    families = {
        key
        for row in hiring_rows
        for key, count in _role_family_items(row.role_family_summary)
        if count > 0
    }
    return sorted(families)


def _role_family_items(value: object) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, Mapping):
        return ()
    items: list[tuple[str, int]] = []
    for key, count in value.items():
        if isinstance(key, str) and isinstance(count, int) and not isinstance(count, bool):
            items.append((key, count))
    return tuple(items)


def _entry_level_access_present(row: CompanyRegionEntryLevel) -> bool:
    return bool(
        (row.entry_level_access_score is not None and row.entry_level_access_score > 0)
        or (row.internship_count is not None and row.internship_count > 0)
        or (row.coop_count is not None and row.coop_count > 0)
        or (
            row.entry_level_full_time_count is not None
            and row.entry_level_full_time_count > 0
        )
        or row.formal_early_career_program_flag
    )


def _matched_region_ids(*row_groups: Iterable[Any]) -> list[str]:
    return sorted({row.region_id for rows in row_groups for row in rows})


def _presence_status(rows: Iterable[CompanyRegionPresence]) -> str | None:
    statuses = {row.presence_status for row in rows}
    if not statuses:
        return None
    if len(statuses) == 1:
        return next(iter(statuses))
    return "mixed"


def _aggregate_freshness_expires_at(*values: datetime | None) -> datetime | None:
    non_null = [_ensure_aware(value) for value in values if value is not None]
    return min(non_null) if non_null else None


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _has_real_data(summary: FreshnessSourceSummary) -> bool:
    return summary.data_basis in {ApiDataBasis.REAL_IMPORTED, ApiDataBasis.MIXED}
