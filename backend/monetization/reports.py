"""Report product catalog for future paid report generation.

This catalog declares report products and entitlement requirements only. It
does not generate PDFs, run checkout, or call payment providers.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.segments import AudienceSegmentKey


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class ReportProductKey(_Vocabulary):
    PERSONALIZED_MARKET_STRATEGY_REPORT = "personalized_market_strategy_report"
    REGION_COMPARISON_REPORT = "region_comparison_report"
    COMPANY_GEOGRAPHY_REPORT = "company_geography_report"
    EARLY_CAREER_OPPORTUNITY_REPORT = "early_career_opportunity_report"


class ReportProductDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    report_key: ReportProductKey
    display_name: str = Field(min_length=1, max_length=128)
    intended_segments: tuple[AudienceSegmentKey, ...] = Field(min_length=1, max_length=8)
    free_preview_available: bool
    preview_feature_key: MonetizationFeatureKey | None
    paid_full_report_required: bool
    paid_full_report_feature_keys: tuple[MonetizationFeatureKey, ...] = Field(
        min_length=1,
        max_length=8,
    )
    included_sections: tuple[str, ...] = Field(min_length=1, max_length=16)
    exportable: bool
    export_feature_key: MonetizationFeatureKey | None = None

    @field_validator("display_name")
    @classmethod
    def _display_name_not_blank(cls, value: str) -> str:
        return _clean_required_string(value, "report metadata")

    @field_validator("included_sections")
    @classmethod
    def _sections_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_required_string(item, "report section") for item in value)


def _clean_required_string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} entries must be strings")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{label} entries must not be blank")
    return stripped


_REPORTS: dict[ReportProductKey, ReportProductDefinition] = {
    ReportProductKey.PERSONALIZED_MARKET_STRATEGY_REPORT: ReportProductDefinition(
        report_key=ReportProductKey.PERSONALIZED_MARKET_STRATEGY_REPORT,
        display_name="Personalized Market Strategy Report",
        intended_segments=(
            AudienceSegmentKey.STUDENTS,
            AudienceSegmentKey.EARLY_CAREER_JOB_SEEKERS,
            AudienceSegmentKey.RELOCATION_CANDIDATES,
        ),
        free_preview_available=True,
        preview_feature_key=MonetizationFeatureKey.BASIC_RECOMMENDATION_PREVIEW,
        paid_full_report_required=True,
        paid_full_report_feature_keys=(
            MonetizationFeatureKey.ADVANCED_RECOMMENDATION_REPORTS,
            MonetizationFeatureKey.FULL_REPORT_GENERATION,
            MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
        ),
        included_sections=(
            "recommendation conclusion",
            "primary market targets",
            "secondary and fallback markets",
            "watchlist starters",
            "tradeoffs and weaknesses",
            "manual verification checklist",
            "timing guidance",
        ),
        exportable=True,
        export_feature_key=MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
    ),
    ReportProductKey.REGION_COMPARISON_REPORT: ReportProductDefinition(
        report_key=ReportProductKey.REGION_COMPARISON_REPORT,
        display_name="Region Comparison Report",
        intended_segments=(
            AudienceSegmentKey.EARLY_CAREER_JOB_SEEKERS,
            AudienceSegmentKey.RELOCATION_CANDIDATES,
            AudienceSegmentKey.PARENTS_ADVISORS,
        ),
        free_preview_available=True,
        preview_feature_key=MonetizationFeatureKey.LIMITED_COMPARISONS,
        paid_full_report_required=True,
        paid_full_report_feature_keys=(
            MonetizationFeatureKey.FULL_MARKET_COVERAGE,
            MonetizationFeatureKey.SAVED_COMPARISON_HISTORY,
            MonetizationFeatureKey.FULL_REPORT_GENERATION,
        ),
        included_sections=(
            "comparison summary",
            "region fit evidence",
            "opportunity tradeoffs",
            "coverage and confidence notes",
            "decision checklist",
        ),
        exportable=True,
        export_feature_key=MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
    ),
    ReportProductKey.COMPANY_GEOGRAPHY_REPORT: ReportProductDefinition(
        report_key=ReportProductKey.COMPANY_GEOGRAPHY_REPORT,
        display_name="Company Geography Report",
        intended_segments=(
            AudienceSegmentKey.EARLY_CAREER_JOB_SEEKERS,
            AudienceSegmentKey.RELOCATION_CANDIDATES,
            AudienceSegmentKey.PARENTS_ADVISORS,
        ),
        free_preview_available=True,
        preview_feature_key=MonetizationFeatureKey.BASIC_REGION_EXPLORATION,
        paid_full_report_required=True,
        paid_full_report_feature_keys=(
            MonetizationFeatureKey.DEEPER_COMPANY_GEOGRAPHY,
            MonetizationFeatureKey.FULL_REPORT_GENERATION,
        ),
        included_sections=(
            "company-region footprint",
            "presence evidence summary",
            "entry-level access notes",
            "geography tradeoffs",
            "manual verification checklist",
        ),
        exportable=True,
        export_feature_key=MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
    ),
    ReportProductKey.EARLY_CAREER_OPPORTUNITY_REPORT: ReportProductDefinition(
        report_key=ReportProductKey.EARLY_CAREER_OPPORTUNITY_REPORT,
        display_name="Early-Career Opportunity Report",
        intended_segments=(
            AudienceSegmentKey.STUDENTS,
            AudienceSegmentKey.EARLY_CAREER_JOB_SEEKERS,
            AudienceSegmentKey.PARENTS_ADVISORS,
        ),
        free_preview_available=True,
        preview_feature_key=MonetizationFeatureKey.BASIC_RECOMMENDATION_PREVIEW,
        paid_full_report_required=True,
        paid_full_report_feature_keys=(
            MonetizationFeatureKey.ADVANCED_RECOMMENDATION_REPORTS,
            MonetizationFeatureKey.FULL_REPORT_GENERATION,
        ),
        included_sections=(
            "early-career fit summary",
            "internship and entry-level access signals",
            "target region shortlist",
            "company-category guidance",
            "risk and caveat review",
            "next-step plan",
        ),
        exportable=True,
        export_feature_key=MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
    ),
}

REPORTS = MappingProxyType(_REPORTS)


def report_product_definitions() -> tuple[ReportProductDefinition, ...]:
    return tuple(REPORTS[key] for key in ReportProductKey)


def report_product_definition(
    report_key: ReportProductKey | str,
) -> ReportProductDefinition:
    return REPORTS[ReportProductKey(report_key)]

