"""Region output builder.

Pure assembly. Does **not** import any service or scoring formula. Reads
canonical truth via the supplied iterables and returns:

* a :class:`RegionOutput` payload matching ``API_SURFACES.md`` §4
* a build-time :class:`BuildOutcome` (``fresh`` / ``partial`` / ``stale``)
* a deterministic ``source_version_bundle``
* the aggregated ``freshness_expires_at``

The service layer wraps this with :class:`OutputMetadata` lifecycle
handling.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import NamedTuple

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.market_coverage import build_region_coverage_metadata
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.orchestration.jobs.errors import JobWarning, WarningSeverity
from backend.outputs.metadata import (
    aggregate_freshness_expires_at,
    region_source_version_bundle,
)
from backend.outputs.payloads import (
    CompanyEntry,
    EntryLevelSummary,
    HiringCompanyEntry,
    Mag7Summary,
    MajorTechSummary,
    OutputPayloadMetadata,
    RegionOutput,
    RegionOutputBody,
    RegionScoresPayload,
    RegionSummary,
)
from backend.outputs.types import BuildOutcome
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore
from backend.shared.value_semantics import aggregate_counts

_TOP_LIST_LIMIT = 25


class RegionBuildResult(NamedTuple):
    payload: RegionOutput
    outcome: BuildOutcome
    source_version_bundle: dict
    freshness_expires_at: datetime | None
    warnings: tuple[JobWarning, ...]


def build_region_output(
    *,
    region: Region,
    region_market_score: RegionMarketScore | None,
    present_companies: Iterable[Company],
    presence_rows: Iterable[CompanyRegionPresence],
    hiring_rows: Iterable[CompanyRegionHiring],
    entry_level_rows: Iterable[CompanyRegionEntryLevel],
    now: datetime | None = None,
) -> RegionBuildResult:
    if now is None:
        now = datetime.now(UTC)

    companies = list(present_companies)
    presence_list = list(presence_rows)
    hiring_list = list(hiring_rows)
    entry_level_list = list(entry_level_rows)

    warnings: list[JobWarning] = []

    # --- summary aggregates ---------------------------------------------
    eligible_count = sum(1 for c in companies if c.eligibility_status == "eligible")
    major_tech_count = sum(1 for c in companies if c.is_major_tech)
    mag7_count = sum(1 for c in companies if c.is_mag7)
    currently_hiring_count = sum(1 for h in hiring_list if h.currently_hiring_flag)

    summary = RegionSummary(
        eligible_company_count=eligible_count,
        major_tech_count=major_tech_count,
        mag7_count=mag7_count,
        present_company_count=len(companies),
        currently_hiring_company_count=currently_hiring_count,
    )

    # --- scores section -------------------------------------------------
    if region_market_score is None:
        scores: RegionScoresPayload | None = None
        warnings.append(
            JobWarning(
                warning_code="region_score_missing",
                severity=WarningSeverity.MEDIUM,
                scope_type="region",
                scope_ref=region.region_id,
                message=(
                    f"no region_market_scores row for region {region.region_id!r}; "
                    "scores section omitted"
                ),
            )
        )
    else:
        scores = RegionScoresPayload(
            structural_ecosystem_score=region_market_score.structural_ecosystem_score,
            live_market_score=region_market_score.live_market_score,
            objective_opportunity_score=region_market_score.objective_opportunity_score,
            raw_total_score=region_market_score.raw_total_score,
            general_density_score=region_market_score.general_density_score,
            tech_market_density_score=region_market_score.tech_market_density_score,
            early_career_accessibility_score=region_market_score.early_career_accessibility_score,
            score_ruleset_version=region_market_score.score_ruleset_version,
        )

    # --- top company lists ---------------------------------------------
    top_present = sorted(
        companies,
        key=lambda c: (
            -(c.eligibility_score or 0.0),
            -int(c.is_mag7),
            -int(c.is_major_tech),
            -(c.prestige_score or 0.0),
            c.company_id,
        ),
    )[:_TOP_LIST_LIMIT]
    top_companies_present = [
        CompanyEntry(
            company_id=c.company_id,
            company_name=c.company_name,
            sector_primary=c.sector_primary,
            eligibility_status=c.eligibility_status,
            is_major_tech=c.is_major_tech,
            is_mag7=c.is_mag7,
            prestige_score=c.prestige_score,
        )
        for c in top_present
    ]

    company_by_id = {c.company_id: c for c in companies}
    top_hiring = sorted(
        hiring_list,
        key=lambda h: (
            -(h.active_posting_count_now or 0),
            -int(h.currently_hiring_flag),
            h.company_id,
        ),
    )[:_TOP_LIST_LIMIT]
    top_companies_hiring = [
        HiringCompanyEntry(
            company_id=h.company_id,
            company_name=(
                company_by_id[h.company_id].company_name
                if h.company_id in company_by_id
                else h.company_id
            ),
            currently_hiring_flag=h.currently_hiring_flag,
            active_posting_count_now=h.active_posting_count_now,
            posting_count_30d=h.posting_count_30d,
            posting_count_90d=h.posting_count_90d,
        )
        for h in top_hiring
    ]

    # --- entry-level summary --------------------------------------------
    internship_semantics = aggregate_counts(
        [e.internship_count for e in entry_level_list]
    )
    coop_semantics = aggregate_counts([e.coop_count for e in entry_level_list])
    ft_semantics = aggregate_counts(
        [e.entry_level_full_time_count for e in entry_level_list]
    )
    if not (
        internship_semantics.has_current_observed_value
        and coop_semantics.has_current_observed_value
        and ft_semantics.has_current_observed_value
    ):
        warnings.append(
            JobWarning(
                warning_code="entry_level_counts_not_fully_observed",
                severity=WarningSeverity.MEDIUM,
                scope_type="region",
                scope_ref=region.region_id,
                message=(
                    "one or more entry-level count totals are unknown, "
                    "not collected, or stale; totals are not reported as zero"
                ),
            )
        )
    formal_count = sum(
        1 for e in entry_level_list if e.formal_early_career_program_flag
    )
    nonzero_scores = [
        e.entry_level_access_score
        for e in entry_level_list
        if e.entry_level_access_score is not None and e.entry_level_access_score > 0
    ]
    avg_score = (
        sum(nonzero_scores) / len(nonzero_scores) if nonzero_scores else None
    )
    entry_level_summary = EntryLevelSummary(
        internship_count_total=internship_semantics.value,
        coop_count_total=coop_semantics.value,
        entry_level_full_time_count_total=ft_semantics.value,
        formal_early_career_program_count=formal_count,
        average_entry_level_access_score=avg_score,
        pairs_with_entry_level_access=len(nonzero_scores),
    )

    # --- major-tech / Mag 7 summaries ----------------------------------
    major_tech_ids = sorted(c.company_id for c in companies if c.is_major_tech)
    mag7_ids = sorted(c.company_id for c in companies if c.is_mag7)
    major_tech_summary = MajorTechSummary(
        count=len(major_tech_ids), company_ids=major_tech_ids[:_TOP_LIST_LIMIT]
    )
    mag7_summary = Mag7Summary(
        count=len(mag7_ids), company_ids=mag7_ids[:_TOP_LIST_LIMIT]
    )

    # --- partial / stale classification --------------------------------
    if not companies:
        warnings.append(
            JobWarning(
                warning_code="no_present_companies_for_region",
                severity=WarningSeverity.MEDIUM,
                scope_type="region",
                scope_ref=region.region_id,
                message=f"no present companies for region {region.region_id!r}",
            )
        )

    freshness_inputs = [h.freshness_expires_at for h in hiring_list] + [
        e.freshness_expires_at for e in entry_level_list
    ]
    freshness_expires_at = aggregate_freshness_expires_at(*freshness_inputs)

    # Stale if the aggregated freshness window has already closed.
    is_stale = (
        freshness_expires_at is not None and freshness_expires_at <= now
    )
    if is_stale:
        warnings.append(
            JobWarning(
                warning_code="stale_input_rows",
                severity=WarningSeverity.MEDIUM,
                scope_type="region",
                scope_ref=region.region_id,
                message=(
                    f"one or more upstream rows for region {region.region_id!r} "
                    "have expired freshness windows"
                ),
            )
        )

    is_partial = (
        region_market_score is None
        or not companies
        or not internship_semantics.has_current_observed_value
        or not coop_semantics.has_current_observed_value
        or not ft_semantics.has_current_observed_value
    )

    if is_stale:
        outcome = BuildOutcome.STALE
    elif is_partial:
        outcome = BuildOutcome.PARTIAL
    else:
        outcome = BuildOutcome.FRESH

    coverage = build_region_coverage_metadata(
        present_company_count=len(companies),
        presence_record_count=len(presence_list),
        hiring_record_count=len(hiring_list),
        entry_level_record_count=len(entry_level_list),
        has_region_score=region_market_score is not None,
        freshness_expires_at_known=freshness_expires_at is not None,
        freshness_is_stale=is_stale,
        source_evidence_loaded=False,
    )

    source_versions = region_source_version_bundle(
        region=region,
        region_market_score=region_market_score,
        present_companies=companies,
        presence_rows=presence_list,
        hiring_rows=hiring_list,
        entry_level_rows=entry_level_list,
    )

    body = RegionOutputBody(
        region_id=region.region_id,
        display_name=region.display_name,
        region_type=region.region_type,
        parent_region_id=region.parent_region_id,
        labor_market_group=region.labor_market_group,
        coverage=coverage,
        sector_coverage={},
        summary=summary,
        scores=scores,
        top_companies_present=top_companies_present,
        top_companies_hiring=top_companies_hiring,
        entry_level_summary=entry_level_summary,
        major_tech_summary=major_tech_summary,
        mag7_summary=mag7_summary,
    )
    payload = RegionOutput(
        region=body,
        metadata=OutputPayloadMetadata(
            state=outcome.value,
            freshness_expires_at=freshness_expires_at,
            source_versions=source_versions,
            warnings=list(warnings),
        ),
    )
    return RegionBuildResult(
        payload=payload,
        outcome=outcome,
        source_version_bundle=source_versions,
        freshness_expires_at=freshness_expires_at,
        warnings=tuple(warnings),
    )
