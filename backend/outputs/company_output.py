"""Company output builder.

Pure assembly. No service imports, no scoring recomputation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import NamedTuple

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.market_coverage import (
    CoverageMetadataPayload,
    placeholder_coverage_metadata,
    priority_market_by_id,
    unknown_sector_coverage_metadata,
)
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.orchestration.jobs.errors import JobWarning, WarningSeverity
from backend.outputs.metadata import (
    aggregate_freshness_expires_at,
    company_source_version_bundle,
)
from backend.outputs.payloads import (
    CompanyOutput,
    CompanyOutputBody,
    CompanyRegionEntryLevelEntry,
    CompanyRegionHiringEntry,
    CompanyRegionPresenceEntry,
    OutputPayloadMetadata,
)
from backend.outputs.types import BuildOutcome
from backend.presence.models import CompanyRegionPresence


class CompanyBuildResult(NamedTuple):
    payload: CompanyOutput
    outcome: BuildOutcome
    source_version_bundle: dict
    freshness_expires_at: datetime | None
    warnings: tuple[JobWarning, ...]


def build_company_output(
    *,
    company: Company,
    presence_rows: Iterable[CompanyRegionPresence],
    hiring_rows: Iterable[CompanyRegionHiring],
    entry_level_rows: Iterable[CompanyRegionEntryLevel],
    regions: Iterable[Region],
    coverage_by_region: Mapping[str, CoverageMetadataPayload] | None = None,
    now: datetime | None = None,
) -> CompanyBuildResult:
    if now is None:
        now = datetime.now(UTC)

    presence_list = list(presence_rows)
    hiring_list = list(hiring_rows)
    entry_level_list = list(entry_level_rows)
    region_list = list(regions)

    region_by_id = {r.region_id: r for r in region_list}
    coverage_by_region = dict(coverage_by_region or {})
    warnings: list[JobWarning] = []

    # --- presence section: only present pairs --------------------------
    present_pairs = sorted(
        (p for p in presence_list if p.presence_status == "present"),
        key=lambda p: p.region_id,
    )
    regions_present = [
        CompanyRegionPresenceEntry(
            region_id=p.region_id,
            region_display_name=(
                region_by_id[p.region_id].display_name
                if p.region_id in region_by_id
                else p.region_id
            ),
            priority_market=priority_market_by_id(p.region_id),
            presence_status=p.presence_status,
            presence_basis=p.presence_basis,
            presence_confidence=p.presence_confidence,
            coverage=_coverage_for_region(coverage_by_region, p.region_id),
            sector_coverage=unknown_sector_coverage_metadata(),
        )
        for p in present_pairs
    ]

    # --- hiring section ------------------------------------------------
    hiring_sorted = sorted(hiring_list, key=lambda h: h.region_id)
    regions_hiring = [
        CompanyRegionHiringEntry(
            region_id=h.region_id,
            region_display_name=(
                region_by_id[h.region_id].display_name
                if h.region_id in region_by_id
                else h.region_id
            ),
            priority_market=priority_market_by_id(h.region_id),
            currently_hiring_flag=h.currently_hiring_flag,
            active_posting_count_now=h.active_posting_count_now,
            posting_count_30d=h.posting_count_30d,
            posting_count_90d=h.posting_count_90d,
            coverage=_coverage_for_region(coverage_by_region, h.region_id),
            sector_coverage=unknown_sector_coverage_metadata(),
        )
        for h in hiring_sorted
    ]

    # --- entry-level section -------------------------------------------
    entry_sorted = sorted(entry_level_list, key=lambda e: e.region_id)
    entry_level_regions = [
        CompanyRegionEntryLevelEntry(
            region_id=e.region_id,
            region_display_name=(
                region_by_id[e.region_id].display_name
                if e.region_id in region_by_id
                else e.region_id
            ),
            priority_market=priority_market_by_id(e.region_id),
            internship_count=e.internship_count,
            coop_count=e.coop_count,
            entry_level_full_time_count=e.entry_level_full_time_count,
            formal_early_career_program_flag=e.formal_early_career_program_flag,
            entry_level_access_score=e.entry_level_access_score,
            entry_level_confidence=e.entry_level_confidence,
            coverage=_coverage_for_region(coverage_by_region, e.region_id),
            sector_coverage=unknown_sector_coverage_metadata(),
        )
        for e in entry_sorted
    ]

    # --- partial / stale classification --------------------------------
    if not present_pairs:
        warnings.append(
            JobWarning(
                warning_code="no_presence_for_company",
                severity=WarningSeverity.MEDIUM,
                scope_type="company",
                scope_ref=company.company_id,
                message=(
                    f"company {company.company_id!r} has no present-status "
                    "presence record in any region"
                ),
            )
        )

    freshness_inputs = [h.freshness_expires_at for h in hiring_list] + [
        e.freshness_expires_at for e in entry_level_list
    ]
    freshness_expires_at = aggregate_freshness_expires_at(*freshness_inputs)

    is_stale = (
        freshness_expires_at is not None and freshness_expires_at <= now
    )
    if is_stale:
        warnings.append(
            JobWarning(
                warning_code="stale_input_rows",
                severity=WarningSeverity.MEDIUM,
                scope_type="company",
                scope_ref=company.company_id,
                message=(
                    f"one or more upstream rows for company {company.company_id!r} "
                    "have expired freshness windows"
                ),
            )
        )

    is_partial = not present_pairs

    if is_stale:
        outcome = BuildOutcome.STALE
    elif is_partial:
        outcome = BuildOutcome.PARTIAL
    else:
        outcome = BuildOutcome.FRESH

    source_versions = company_source_version_bundle(
        company=company,
        regions=region_list,
        presence_rows=presence_list,
        hiring_rows=hiring_list,
        entry_level_rows=entry_level_list,
    )

    body = CompanyOutputBody(
        company_id=company.company_id,
        company_name=company.company_name,
        normalized_company_name=company.normalized_company_name,
        sector_primary=company.sector_primary,
        sector_secondary=company.sector_secondary,
        eligibility_status=company.eligibility_status,
        eligibility_override_flag=company.eligibility_override_flag,
        classification_confidence=company.classification_confidence,
        is_major_tech=company.is_major_tech,
        is_mag7=company.is_mag7,
        prestige_score=company.prestige_score,
        regions_present=regions_present,
        regions_hiring=regions_hiring,
        entry_level_regions=entry_level_regions,
    )
    payload = CompanyOutput(
        company=body,
        metadata=OutputPayloadMetadata(
            state=outcome.value,
            freshness_expires_at=freshness_expires_at,
            source_versions=source_versions,
            warnings=list(warnings),
        ),
    )
    return CompanyBuildResult(
        payload=payload,
        outcome=outcome,
        source_version_bundle=source_versions,
        freshness_expires_at=freshness_expires_at,
        warnings=tuple(warnings),
    )


def _coverage_for_region(
    coverage_by_region: Mapping[str, CoverageMetadataPayload],
    region_id: str,
) -> CoverageMetadataPayload:
    return coverage_by_region.get(
        region_id,
        placeholder_coverage_metadata(
            note=(
                "Region coverage metadata was not assembled for this company "
                "output surface."
            )
        ),
    )
