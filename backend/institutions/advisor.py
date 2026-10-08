"""Guidance-oriented institutional advisor tools.

Advisor tools compare existing market read models. They do not inspect
student-level activity, generate institutional reports, or create a second
recommendation engine.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.search import company_geography, search_companies, search_regions
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.market_coverage import CoverageMetadataPayload
from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolver
from backend.hiring.models import CompanyRegionHiring


class AdvisorComparisonType(StrEnum):
    REGIONS = "regions"
    INDUSTRIES = "industries"
    COMPANIES = "companies"
    CAREER_STAGES = "career_stages"
    APPLICATION_TIMING = "application_timing"


class AdvisorRegionComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    regions: list[str] = Field(min_length=1, max_length=8)
    role_context: str | None = Field(default=None, max_length=128)
    industry_context: str | None = Field(default=None, max_length=128)
    career_stage: str | None = Field(default=None, max_length=64)

    @field_validator("regions")
    @classmethod
    def _regions_nonblank(cls, value: list[str]) -> list[str]:
        return _clean_list(value)

    @field_validator("role_context", "industry_context", "career_stage")
    @classmethod
    def _optional_string(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class AdvisorIndustryComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    industries: list[str] = Field(min_length=1, max_length=8)
    region_context: list[str] = Field(default_factory=list, max_length=8)
    career_stage: str | None = Field(default=None, max_length=64)

    @field_validator("industries")
    @classmethod
    def _industries_nonblank(cls, value: list[str]) -> list[str]:
        return _clean_list(value)

    @field_validator("region_context")
    @classmethod
    def _optional_lists_clean(cls, value: list[str]) -> list[str]:
        return _clean_optional_list(value)

    @field_validator("career_stage")
    @classmethod
    def _optional_string(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class AdvisorCompanyComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    companies: list[str] = Field(min_length=1, max_length=8)
    region_context: list[str] = Field(default_factory=list, max_length=8)
    industry_context: str | None = Field(default=None, max_length=128)
    career_stage: str | None = Field(default=None, max_length=64)

    @field_validator("companies")
    @classmethod
    def _companies_nonblank(cls, value: list[str]) -> list[str]:
        return _clean_list(value)

    @field_validator("region_context")
    @classmethod
    def _optional_lists_clean(cls, value: list[str]) -> list[str]:
        return _clean_optional_list(value)

    @field_validator("industry_context", "career_stage")
    @classmethod
    def _optional_string(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class AdvisorCareerStageComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    career_stages: list[str] = Field(min_length=1, max_length=8)
    region_context: list[str] = Field(default_factory=list, max_length=8)
    industry_context: str | None = Field(default=None, max_length=128)
    company_context: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("career_stages")
    @classmethod
    def _career_stages_nonblank(cls, value: list[str]) -> list[str]:
        return _clean_list(value)

    @field_validator("region_context", "company_context")
    @classmethod
    def _optional_lists_clean(cls, value: list[str]) -> list[str]:
        return _clean_optional_list(value)

    @field_validator("industry_context")
    @classmethod
    def _optional_string(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class AdvisorApplicationTimingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_regions: list[str] = Field(default_factory=list, max_length=8)
    target_industries: list[str] = Field(default_factory=list, max_length=8)
    target_companies: list[str] = Field(default_factory=list, max_length=8)
    career_stage: str | None = Field(default=None, max_length=64)
    application_window: str | None = Field(default=None, max_length=128)

    @field_validator("target_regions", "target_industries", "target_companies")
    @classmethod
    def _optional_lists_clean(cls, value: list[str]) -> list[str]:
        return _clean_optional_list(value)

    @field_validator("career_stage", "application_window")
    @classmethod
    def _optional_string(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @model_validator(mode="after")
    def _has_context(self) -> AdvisorApplicationTimingRequest:
        if not (
            self.target_regions
            or self.target_industries
            or self.target_companies
            or self.career_stage
            or self.application_window
        ):
            raise ValueError("application timing requires at least one target context")
        return self


class AdvisorComparedItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    label: str
    item_type: str
    demand_signals: dict[str, Any] = Field(default_factory=dict)
    coverage: dict[str, Any] | None = None
    explanation_summary: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdvisorTradeoff(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: str
    summary: str
    evidence_level: str = "directional"


class AdvisorToolResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: str
    generated_at: datetime
    comparison_type: AdvisorComparisonType
    compared_items: list[AdvisorComparedItem] = Field(default_factory=list)
    guidance: list[str] = Field(default_factory=list)
    tradeoffs: list[AdvisorTradeoff] = Field(default_factory=list)
    coverage_warnings: list[str] = Field(default_factory=list)
    data_freshness: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    privacy_notes: list[str] = Field(default_factory=list)


def build_region_comparison(
    session: Session,
    *,
    organization_id: str,
    request: AdvisorRegionComparisonRequest,
) -> AdvisorToolResponse:
    generated_at = _utc_now()
    search = search_regions(session)
    by_id = {region.region_id: region for region in search.regions}
    resolver = GeographicResolver(RegionRepository(session))
    hiring_by_region = _hiring_by_region(session)
    entry_by_region = _entry_by_region(session)
    items: list[AdvisorComparedItem] = []
    coverage_warnings: list[str] = []

    for requested in request.regions:
        resolution = resolver.resolve(requested)
        region = by_id.get(resolution.region_id or "") if resolution.resolved else None
        if region is None:
            items.append(_missing_item(requested, "region"))
            if resolution.status == "ambiguous":
                coverage_warnings.append(
                    f"Region reference is ambiguous: {requested}; candidates: "
                    f"{', '.join(resolution.candidate_region_ids)}."
                )
            else:
                coverage_warnings.append(f"Region not found or unavailable: {requested}.")
            continue
        hiring_rows = hiring_by_region.get(region.region_id, [])
        entry_rows = entry_by_region.get(region.region_id, [])
        coverage = _coverage_summary(region.coverage)
        item_warnings = _coverage_warnings(region.name, region.coverage)
        coverage_warnings.extend(item_warnings)
        items.append(
            AdvisorComparedItem(
                item_id=region.region_id,
                label=region.name,
                item_type="region",
                demand_signals={
                    "opportunity_score": region.opportunity_score,
                    "active_posting_count_now": sum(
                        row.active_posting_count_now or 0 for row in hiring_rows
                    ),
                    "currently_hiring_company_count": len(
                        {row.company_id for row in hiring_rows if row.currently_hiring_flag}
                    ),
                    "entry_level_signal_count": _entry_level_signal_count(entry_rows),
                    "trend_signal": _most_common(
                        row.annualized_trend_signal for row in hiring_rows
                    )
                    or "unknown",
                },
                coverage=coverage,
                explanation_summary=[
                    "Region comparison uses existing region search, coverage, "
                    "hiring, and entry-level signals.",
                    _context_sentence(
                        career_stage=request.career_stage,
                        industry_context=request.industry_context,
                        role_context=request.role_context,
                    ),
                ],
                warnings=item_warnings,
                metadata={
                    "region_id": region.region_id,
                    "requested_region": requested,
                    "resolution_source": resolution.resolution_source,
                    "freshness_status": region.freshness.freshness_status.value,
                    "data_basis": region.freshness.data_basis.value,
                },
            )
        )

    return _response(
        organization_id=organization_id,
        generated_at=generated_at,
        comparison_type=AdvisorComparisonType.REGIONS,
        compared_items=items,
        guidance=[
            "Use region comparisons to frame tradeoffs, not to guarantee outcomes.",
            "Verify current postings and source freshness before advising on final targets.",
        ],
        tradeoffs=_tradeoffs_for_items(items),
        coverage_warnings=coverage_warnings,
        data_freshness=_freshness_summary(generated_at, items),
    )


def build_industry_comparison(
    session: Session,
    *,
    organization_id: str,
    request: AdvisorIndustryComparisonRequest,
) -> AdvisorToolResponse:
    generated_at = _utc_now()
    companies = search_companies(session).companies
    region_filter = _canonical_region_filter(session, request.region_context)
    items: list[AdvisorComparedItem] = []
    coverage_warnings: list[str] = []

    for industry in request.industries:
        matches = [
            company
            for company in companies
            if _matches_industry(company, industry)
            and (
                not region_filter
                or any(
                    region_id in region_filter
                    for region_id in company.matched_region_ids
                )
            )
        ]
        weak_coverage_count = sum(
            1
            for company in matches
            for coverage in company.matched_region_coverage.values()
            if _coverage_is_weak(coverage)
        )
        if weak_coverage_count:
            coverage_warnings.append(
                f"{_display_label(industry)} has {weak_coverage_count} weak "
                "coverage region signal(s)."
            )
        item_warnings = (
            [f"No company examples matched {_display_label(industry)} in the selected context."]
            if not matches
            else []
        )
        items.append(
            AdvisorComparedItem(
                item_id=_normalize_key(industry),
                label=_display_label(industry),
                item_type="industry",
                demand_signals={
                    "company_count": len(matches),
                    "currently_hiring_company_count": sum(
                        1 for company in matches if company.current_hiring
                    ),
                    "entry_level_company_count": sum(
                        1 for company in matches if company.has_entry_level_access
                    ),
                    "example_companies": [company.name for company in matches[:3]],
                    "role_families": sorted(
                        {
                            role
                            for company in matches
                            for role in company.role_families
                        }
                    )[:8],
                },
                coverage=None,
                explanation_summary=[
                    "Industry comparison uses existing company search metadata, "
                    "region matches, hiring flags, and entry-level access flags.",
                    _context_sentence(career_stage=request.career_stage),
                ],
                warnings=item_warnings,
                metadata={
                    "industry_query": industry,
                    "region_context_count": len(request.region_context),
                },
            )
        )
        coverage_warnings.extend(item_warnings)

    return _response(
        organization_id=organization_id,
        generated_at=generated_at,
        comparison_type=AdvisorComparisonType.INDUSTRIES,
        compared_items=items,
        guidance=[
            "Use industry comparisons to identify market examples and coverage gaps.",
            "Treat company examples as directional because sector labels may be incomplete.",
        ],
        tradeoffs=_tradeoffs_for_items(items),
        coverage_warnings=coverage_warnings,
        data_freshness=_freshness_summary(generated_at, items),
    )


def build_company_comparison(
    session: Session,
    *,
    organization_id: str,
    request: AdvisorCompanyComparisonRequest,
) -> AdvisorToolResponse:
    generated_at = _utc_now()
    companies = search_companies(session).companies
    by_key = _company_lookup(companies)
    region_filter = _canonical_region_filter(session, request.region_context)
    items: list[AdvisorComparedItem] = []
    coverage_warnings: list[str] = []

    for requested in request.companies:
        company = by_key.get(_normalize_key(requested))
        if company is None:
            items.append(_missing_item(requested, "company"))
            coverage_warnings.append(f"Company not found or unavailable: {requested}.")
            continue
        geography = company_geography(session, company_id=company.company_id)
        region_items = geography.regions if geography is not None else []
        if region_filter:
            region_items = [
                row
                for row in region_items
                if row.region_id in region_filter
            ]
        item_warnings = [
            warning
            for row in region_items
            for warning in _coverage_warnings(row.region_name, row.coverage)
        ]
        coverage_warnings.extend(item_warnings)
        items.append(
            AdvisorComparedItem(
                item_id=company.company_id,
                label=company.name,
                item_type="company",
                demand_signals={
                    "current_hiring": company.current_hiring,
                    "has_entry_level_access": company.has_entry_level_access,
                    "matched_region_count": len(region_items),
                    "matched_region_ids": [row.region_id for row in region_items],
                    "role_families": company.role_families,
                    "sector": company.sector,
                    "industry": company.industry,
                },
                coverage=_company_coverage_summary(region_items),
                explanation_summary=[
                    "Company comparison uses existing company search and company "
                    "geography read models.",
                    _context_sentence(
                        career_stage=request.career_stage,
                        industry_context=request.industry_context,
                    ),
                ],
                warnings=item_warnings,
                metadata={
                    "company_id": company.company_id,
                    "freshness_status": company.freshness.freshness_status.value,
                    "data_basis": company.freshness.data_basis.value,
                },
            )
        )

    return _response(
        organization_id=organization_id,
        generated_at=generated_at,
        comparison_type=AdvisorComparisonType.COMPANIES,
        compared_items=items,
        guidance=[
            "Use company comparisons to discuss fit and evidence quality before "
            "students prioritize outreach.",
            "Current-hiring flags are advisory signals; advisors should verify live postings.",
        ],
        tradeoffs=_tradeoffs_for_items(items),
        coverage_warnings=coverage_warnings,
        data_freshness=_freshness_summary(generated_at, items),
    )


def build_career_stage_comparison(
    session: Session,
    *,
    organization_id: str,
    request: AdvisorCareerStageComparisonRequest,
) -> AdvisorToolResponse:
    generated_at = _utc_now()
    entry_rows = _filtered_entry_rows(
        session,
        regions=request.region_context,
        companies=request.company_context,
    )
    hiring_rows = _filtered_hiring_rows(
        session,
        regions=request.region_context,
        companies=request.company_context,
    )
    items: list[AdvisorComparedItem] = []
    coverage_warnings: list[str] = []

    for stage in request.career_stages:
        stage_key = _normalize_key(stage)
        signals = _stage_signals(stage_key, entry_rows=entry_rows, hiring_rows=hiring_rows)
        item_warnings = _stage_warnings(stage_key, signals)
        coverage_warnings.extend(item_warnings)
        items.append(
            AdvisorComparedItem(
                item_id=stage_key,
                label=_display_label(stage),
                item_type="career_stage",
                demand_signals=signals,
                coverage=None,
                explanation_summary=_stage_explanations(stage_key),
                warnings=item_warnings,
                metadata={
                    "region_context_count": len(request.region_context),
                    "company_context_count": len(request.company_context),
                    "industry_context": request.industry_context,
                },
            )
        )

    return _response(
        organization_id=organization_id,
        generated_at=generated_at,
        comparison_type=AdvisorComparisonType.CAREER_STAGES,
        compared_items=items,
        guidance=[
            "Use career-stage comparisons to tailor advising conversations, not "
            "to infer individual readiness.",
            "Where stage-specific evidence is missing, verify requirements "
            "manually before advising.",
        ],
        tradeoffs=_tradeoffs_for_items(items),
        coverage_warnings=coverage_warnings,
        data_freshness=_freshness_summary(generated_at, items),
    )


def build_application_timing(
    session: Session,
    *,
    organization_id: str,
    request: AdvisorApplicationTimingRequest,
) -> AdvisorToolResponse:
    generated_at = _utc_now()
    entry_rows = _filtered_entry_rows(
        session,
        regions=request.target_regions,
        companies=request.target_companies,
    )
    hiring_rows = _filtered_hiring_rows(
        session,
        regions=request.target_regions,
        companies=request.target_companies,
    )
    industry_matches = _industry_matches(session, request.target_industries)
    active_postings = sum(row.active_posting_count_now or 0 for row in hiring_rows)
    internship_count = sum(row.internship_count or 0 for row in entry_rows)
    coop_count = sum(row.coop_count or 0 for row in entry_rows)
    season_signal = _most_common(
        row.seasonal_student_hiring_signal for row in hiring_rows
    ) or _most_common(row.student_season_recurrence_signal for row in entry_rows)

    warnings = []
    if not hiring_rows and not entry_rows and not industry_matches:
        warnings.append("No structured timing evidence matched the selected context.")
    if season_signal is None:
        warnings.append("Student-season recurrence is unknown for the selected context.")

    item = AdvisorComparedItem(
        item_id="application_timing",
        label="Application timing planner",
        item_type="application_timing",
        demand_signals={
            "active_posting_count_now": active_postings,
            "internship_count": internship_count,
            "coop_count": coop_count,
            "matched_industry_company_count": len(industry_matches),
            "student_season_signal": season_signal or "unknown",
            "application_window": request.application_window,
        },
        coverage=None,
        explanation_summary=[
            "Timing guidance uses existing hiring windows, entry-level counts, "
            "student-season signals, and selected market context.",
            _context_sentence(career_stage=request.career_stage),
        ],
        warnings=warnings,
        metadata={
            "target_region_count": len(request.target_regions),
            "target_industry_count": len(request.target_industries),
            "target_company_count": len(request.target_companies),
        },
    )

    return _response(
        organization_id=organization_id,
        generated_at=generated_at,
        comparison_type=AdvisorComparisonType.APPLICATION_TIMING,
        compared_items=[item],
        guidance=[
            "For near-term applications, verify active postings before advising "
            "students to prioritize a target.",
            "For internships or co-ops, start planning at least one academic "
            "term ahead when possible.",
            "Use uncertain timing signals as a prompt for manual verification, "
            "not as a deadline guarantee.",
        ],
        tradeoffs=[
            AdvisorTradeoff(
                category="timing_uncertainty",
                summary=(
                    "Application windows vary by employer and source freshness; "
                    "manual verification is required."
                ),
            )
        ],
        coverage_warnings=warnings,
        data_freshness=_freshness_summary(generated_at, [item]),
    )


def _response(
    *,
    organization_id: str,
    generated_at: datetime,
    comparison_type: AdvisorComparisonType,
    compared_items: list[AdvisorComparedItem],
    guidance: list[str],
    tradeoffs: list[AdvisorTradeoff],
    coverage_warnings: list[str],
    data_freshness: dict[str, Any],
) -> AdvisorToolResponse:
    limitations = [
        "Advisor tools are decision-support surfaces and do not guarantee student outcomes.",
        "Advisor tools do not expose raw student searches, saved companies, "
        "recommendations, or personal activity.",
        "Coverage and freshness warnings should be reviewed before high-stakes advising decisions.",
    ]
    privacy_notes = [
        "Layer 16 advisor tools are guidance-oriented and use existing market intelligence.",
        "Student-specific advising remains disabled until explicit scoped consent exists.",
    ]
    return AdvisorToolResponse(
        organization_id=organization_id,
        generated_at=generated_at,
        comparison_type=comparison_type,
        compared_items=compared_items,
        guidance=[item for item in guidance if item],
        tradeoffs=tradeoffs or _tradeoffs_for_items(compared_items),
        coverage_warnings=sorted(set(item for item in coverage_warnings if item)),
        data_freshness=data_freshness,
        limitations=limitations,
        privacy_notes=privacy_notes,
    )


def _region_lookup(regions: list[Any]) -> dict[str, Any]:
    lookup: dict[str, Any] = {}
    for region in regions:
        for value in (region.region_id, region.name, region.region_name):
            lookup[_normalize_key(value)] = region
    return lookup


def _company_lookup(companies: list[Any]) -> dict[str, Any]:
    lookup: dict[str, Any] = {}
    for company in companies:
        for value in (company.company_id, company.name):
            lookup[_normalize_key(value)] = company
    return lookup


def _hiring_by_region(session: Session) -> dict[str, list[CompanyRegionHiring]]:
    rows = session.execute(select(CompanyRegionHiring)).scalars()
    grouped: dict[str, list[CompanyRegionHiring]] = defaultdict(list)
    for row in rows:
        grouped[row.region_id].append(row)
    return dict(grouped)


def _entry_by_region(session: Session) -> dict[str, list[CompanyRegionEntryLevel]]:
    rows = session.execute(select(CompanyRegionEntryLevel)).scalars()
    grouped: dict[str, list[CompanyRegionEntryLevel]] = defaultdict(list)
    for row in rows:
        grouped[row.region_id].append(row)
    return dict(grouped)


def _filtered_hiring_rows(
    session: Session,
    *,
    regions: list[str],
    companies: list[str],
) -> list[CompanyRegionHiring]:
    region_keys = _canonical_region_filter(session, regions)
    company_keys = {_normalize_key(company) for company in companies}
    rows = list(session.execute(select(CompanyRegionHiring)).scalars())
    return [
        row
        for row in rows
        if (not regions or row.region_id in region_keys)
        and (not company_keys or _normalize_key(row.company_id) in company_keys)
    ]


def _filtered_entry_rows(
    session: Session,
    *,
    regions: list[str],
    companies: list[str],
) -> list[CompanyRegionEntryLevel]:
    region_keys = _canonical_region_filter(session, regions)
    company_keys = {_normalize_key(company) for company in companies}
    rows = list(session.execute(select(CompanyRegionEntryLevel)).scalars())
    return [
        row
        for row in rows
        if (not regions or row.region_id in region_keys)
        and (not company_keys or _normalize_key(row.company_id) in company_keys)
    ]


def _industry_matches(session: Session, industries: list[str]) -> list[Any]:
    if not industries:
        return []
    companies = search_companies(session).companies
    return [
        company
        for company in companies
        if any(_matches_industry(company, industry) for industry in industries)
    ]


def _canonical_region_filter(session: Session, values: list[str]) -> set[str]:
    resolver = GeographicResolver(RegionRepository(session))
    return {
        resolution.region_id
        for value in values
        if (resolution := resolver.resolve(value)).resolved
        and resolution.region_id is not None
    }


def _matches_industry(company: Any, industry: str) -> bool:
    needle = _normalize_key(industry)
    return needle in {
        _normalize_key(company.sector),
        _normalize_key(company.industry),
    }


def _stage_signals(
    stage_key: str,
    *,
    entry_rows: list[CompanyRegionEntryLevel],
    hiring_rows: list[CompanyRegionHiring],
) -> dict[str, Any]:
    active_postings = sum(row.active_posting_count_now or 0 for row in hiring_rows)
    if stage_key in {"internship", "internships"}:
        return {
            "internship_count": sum(row.internship_count or 0 for row in entry_rows),
            "formal_program_count": sum(
                1 for row in entry_rows if row.formal_early_career_program_flag
            ),
            "student_season_signal": _most_common(
                row.student_season_recurrence_signal for row in entry_rows
            )
            or "unknown",
        }
    if stage_key in {"coop", "co_op", "co-op"}:
        return {
            "coop_count": sum(row.coop_count or 0 for row in entry_rows),
            "formal_program_count": sum(
                1 for row in entry_rows if row.formal_early_career_program_flag
            ),
            "student_season_signal": _most_common(
                row.student_season_recurrence_signal for row in entry_rows
            )
            or "unknown",
        }
    if stage_key in {"entry_level", "new_grad", "early_career"}:
        scores = [
            row.entry_level_access_score
            for row in entry_rows
            if row.entry_level_access_score is not None
        ]
        return {
            "entry_level_full_time_count": sum(
                row.entry_level_full_time_count or 0 for row in entry_rows
            ),
            "formal_program_count": sum(
                1 for row in entry_rows if row.formal_early_career_program_flag
            ),
            "average_entry_level_access_score": (
                round(sum(scores) / len(scores), 3) if scores else None
            ),
            "active_posting_count_now": active_postings,
        }
    return {
        "active_posting_count_now": active_postings,
        "stage_specific_signal_available": False,
    }


def _stage_explanations(stage_key: str) -> list[str]:
    if stage_key in {"internship", "internships", "coop", "co_op", "co-op"}:
        return [
            "Student-program guidance uses existing internship, co-op, formal "
            "program, and seasonality fields.",
            "Program timing can vary by employer, so advisors should verify current cycles.",
        ]
    if stage_key in {"entry_level", "new_grad", "early_career"}:
        return [
            "Entry-level guidance uses existing entry-level access and hiring fields.",
            "Use this as market context rather than an individualized readiness assessment.",
        ]
    return [
        "No dedicated stage-specific market model exists for this stage.",
        "Only broad hiring context is returned, with manual verification required.",
    ]


def _stage_warnings(stage_key: str, signals: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if signals.get("stage_specific_signal_available") is False:
        warnings.append(
            f"{_display_label(stage_key)} has no dedicated stage-specific "
            "signal in the current model."
        )
    if not any(value for value in signals.values() if isinstance(value, (int, float))):
        warnings.append(f"{_display_label(stage_key)} has limited structured signal.")
    return warnings


def _tradeoffs_for_items(items: list[AdvisorComparedItem]) -> list[AdvisorTradeoff]:
    tradeoffs: list[AdvisorTradeoff] = []
    if len(items) > 1:
        tradeoffs.append(
            AdvisorTradeoff(
                category="demand_variation",
                summary=(
                    "Demand signals vary by target; compare current hiring "
                    "against evidence quality."
                ),
            )
        )
    if any(item.warnings for item in items):
        tradeoffs.append(
            AdvisorTradeoff(
                category="coverage_confidence",
                summary=(
                    "Some targets carry coverage or availability warnings; "
                    "verify before advising students to prioritize them."
                ),
            )
        )
    if not tradeoffs:
        tradeoffs.append(
            AdvisorTradeoff(
                category="manual_verification",
                summary=(
                    "Use the returned signals as starting points and verify "
                    "current conditions manually."
                ),
            )
        )
    return tradeoffs


def _coverage_warnings(label: str, coverage: CoverageMetadataPayload) -> list[str]:
    if not _coverage_is_weak(coverage):
        return []
    return [
        f"{label} has limited coverage quality ({coverage.label}, {coverage.tier.value})."
    ]


def _coverage_is_weak(coverage: CoverageMetadataPayload) -> bool:
    return (
        coverage.tier.value in {"tier_3", "tier_4"}
        or coverage.quality_score < 50
        or not coverage.safe_for_confident_market_comparison
    )


def _coverage_summary(coverage: CoverageMetadataPayload) -> dict[str, Any]:
    return {
        "tier": coverage.tier.value,
        "label": coverage.label,
        "quality_score": coverage.quality_score,
        "safe_for_confident_market_comparison": (
            coverage.safe_for_confident_market_comparison
        ),
        "coverage_limitations": list(coverage.coverage_limitations),
    }


def _company_coverage_summary(region_items: list[Any]) -> dict[str, Any] | None:
    if not region_items:
        return None
    weak_count = sum(1 for row in region_items if _coverage_is_weak(row.coverage))
    return {
        "matched_region_count": len(region_items),
        "weak_coverage_region_count": weak_count,
        "region_coverage": {
            row.region_id: _coverage_summary(row.coverage) for row in region_items[:8]
        },
    }


def _entry_level_signal_count(rows: list[CompanyRegionEntryLevel]) -> int:
    return sum(
        (row.internship_count or 0)
        + (row.coop_count or 0)
        + (row.entry_level_full_time_count or 0)
        for row in rows
    )


def _freshness_summary(
    generated_at: datetime,
    items: list[AdvisorComparedItem],
) -> dict[str, Any]:
    statuses = [
        value
        for item in items
        if isinstance((value := item.metadata.get("freshness_status")), str)
    ]
    bases = [
        value
        for item in items
        if isinstance((value := item.metadata.get("data_basis")), str)
    ]
    return {
        "generated_at": generated_at.isoformat(),
        "freshness_statuses": sorted(set(statuses)) or ["unknown"],
        "data_basis": sorted(set(bases)) or ["unknown"],
        "source": "existing market search, coverage, hiring, and entry-level read models",
    }


def _context_sentence(
    *,
    career_stage: str | None = None,
    industry_context: str | None = None,
    role_context: str | None = None,
) -> str:
    parts = [
        f"career stage {career_stage}" if career_stage else None,
        f"industry context {industry_context}" if industry_context else None,
        f"role context {role_context}" if role_context else None,
    ]
    rendered = ", ".join(part for part in parts if part)
    return f"Requested context: {rendered}." if rendered else "No student-specific context is used."


def _missing_item(value: str, item_type: str) -> AdvisorComparedItem:
    label = _display_label(value)
    return AdvisorComparedItem(
        item_id=_normalize_key(value),
        label=label,
        item_type=item_type,
        demand_signals={},
        coverage=None,
        explanation_summary=[
            "The requested target was not found in existing market read models."
        ],
        warnings=[f"{label} was not found or has no readable market context."],
        metadata={},
    )


def _clean_list(value: list[str]) -> list[str]:
    cleaned = []
    for item in value:
        if not isinstance(item, str):
            continue
        stripped = item.strip()
        if stripped and stripped not in cleaned:
            cleaned.append(stripped)
    if not cleaned:
        raise ValueError("at least one nonblank value is required")
    return cleaned


def _clean_optional_list(value: list[str]) -> list[str]:
    cleaned = []
    for item in value:
        if not isinstance(item, str):
            continue
        stripped = item.strip()
        if stripped and stripped not in cleaned:
            cleaned.append(stripped)
    return cleaned


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_key(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().casefold().replace("-", "_").replace(" ", "_")


def _display_label(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def _most_common(values: Any) -> str | None:
    cleaned = [value for value in values if isinstance(value, str) and value.strip()]
    if not cleaned:
        return None
    return Counter(cleaned).most_common(1)[0][0]


def _utc_now() -> datetime:
    return datetime.now(UTC)
