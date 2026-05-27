"""Canonical monetization feature boundaries.

Feature definitions explain why a capability is free or paid. The core
recommendation conclusion remains visible in the free boundary; paid features
package added workflow value such as persistence, alerts, coverage depth, and
exportable reports.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class FeatureBoundary(_Vocabulary):
    FREE = "free"
    PAID = "paid"


class MonetizationFeatureKey(_Vocabulary):
    BASIC_REGION_EXPLORATION = "basic_region_exploration"
    PUBLIC_DEMO_MARKETS = "public_demo_markets"
    LIMITED_COMPARISONS = "limited_comparisons"
    LIMITED_PERSONALIZED_DISCOVERY = "limited_personalized_discovery"
    BASIC_RECOMMENDATION_PREVIEW = "basic_recommendation_preview"
    SAVED_WATCHLISTS = "saved_watchlists"
    ALERTS = "alerts"
    ADVANCED_RECOMMENDATION_REPORTS = "advanced_recommendation_reports"
    FULL_MARKET_COVERAGE = "full_market_coverage"
    EXPORTABLE_STRATEGY_PLANS = "exportable_strategy_plans"
    DEEPER_COMPANY_GEOGRAPHY = "deeper_company_geography"
    SAVED_COMPARISON_HISTORY = "saved_comparison_history"
    FULL_REPORT_GENERATION = "full_report_generation"
    INSTITUTIONAL_LICENSE_MANAGEMENT = "institutional_license_management"
    COHORT_GUIDANCE_TEMPLATES = "cohort_guidance_templates"
    PRIVACY_PRESERVING_PROGRAM_INSIGHTS = "privacy_preserving_program_insights"


class FeatureDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_key: MonetizationFeatureKey
    boundary: FeatureBoundary
    display_name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=360)
    boundary_rationale: str = Field(min_length=1, max_length=420)
    trust_constraint: str = Field(min_length=1, max_length=360)
    exposes_core_recommendation_conclusion: bool = False
    recommendation_influence: str = Field(default="none", min_length=1, max_length=64)

    @field_validator(
        "display_name",
        "description",
        "boundary_rationale",
        "trust_constraint",
        "recommendation_influence",
    )
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _clean_required_string(value, "feature metadata")


def _clean_required_string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} entries must be strings")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{label} entries must not be blank")
    return stripped


_FEATURES: dict[MonetizationFeatureKey, FeatureDefinition] = {
    MonetizationFeatureKey.BASIC_REGION_EXPLORATION: FeatureDefinition(
        feature_key=MonetizationFeatureKey.BASIC_REGION_EXPLORATION,
        boundary=FeatureBoundary.FREE,
        display_name="Basic region exploration",
        description="Browse core region identity, coverage, and high-level market context.",
        boundary_rationale=(
            "This is free because users need useful market orientation before "
            "deciding whether deeper paid workflow tools are worth it."
        ),
        trust_constraint="Free exploration must remain useful and must not alter ranking logic.",
    ),
    MonetizationFeatureKey.PUBLIC_DEMO_MARKETS: FeatureDefinition(
        feature_key=MonetizationFeatureKey.PUBLIC_DEMO_MARKETS,
        boundary=FeatureBoundary.FREE,
        display_name="Public demo markets",
        description=(
            "Inspect a representative set of demo markets without an institutional license."
        ),
        boundary_rationale=(
            "This is free so users and buyers can evaluate data quality and product "
            "fit before procurement or subscription decisions."
        ),
        trust_constraint=(
            "Demo availability must not imply that non-demo markets are lower quality."
        ),
    ),
    MonetizationFeatureKey.LIMITED_COMPARISONS: FeatureDefinition(
        feature_key=MonetizationFeatureKey.LIMITED_COMPARISONS,
        boundary=FeatureBoundary.FREE,
        display_name="Limited comparisons",
        description="Compare a small number of regions for basic tradeoff exploration.",
        boundary_rationale=(
            "This is free because comparison is part of understanding the product's "
            "recommendation quality; larger saved/history workflows are paid."
        ),
        trust_constraint="Comparison limits must not hide the basic recommendation conclusion.",
    ),
    MonetizationFeatureKey.LIMITED_PERSONALIZED_DISCOVERY: FeatureDefinition(
        feature_key=MonetizationFeatureKey.LIMITED_PERSONALIZED_DISCOVERY,
        boundary=FeatureBoundary.FREE,
        display_name="Limited personalized discovery",
        description="Preview preference-aware market discovery with bounded session usage.",
        boundary_rationale=(
            "This is free because users should see whether personalization is useful "
            "before paying for persistence, reports, or full coverage."
        ),
        trust_constraint="Personalization preview must not mutate canonical market scores.",
    ),
    MonetizationFeatureKey.BASIC_RECOMMENDATION_PREVIEW: FeatureDefinition(
        feature_key=MonetizationFeatureKey.BASIC_RECOMMENDATION_PREVIEW,
        boundary=FeatureBoundary.FREE,
        display_name="Basic recommendation preview",
        description=(
            "Show the basic recommendation result, including the conclusion and "
            "plain-language caveats, without full paid report packaging."
        ),
        boundary_rationale=(
            "The core recommendation conclusion is free because hiding it would "
            "undermine user trust and make monetization distort the product promise."
        ),
        trust_constraint=(
            "This feature is the explicit boundary that prevents the core "
            "recommendation conclusion from becoming paid-only."
        ),
        exposes_core_recommendation_conclusion=True,
    ),
    MonetizationFeatureKey.SAVED_WATCHLISTS: FeatureDefinition(
        feature_key=MonetizationFeatureKey.SAVED_WATCHLISTS,
        boundary=FeatureBoundary.PAID,
        display_name="Saved watchlists",
        description="Persist user-selected markets, companies, and strategy targets.",
        boundary_rationale=(
            "This is paid because it adds durable workflow value beyond the basic "
            "recommendation result."
        ),
        trust_constraint="Saving a watchlist must not feed back into market ranking authority.",
    ),
    MonetizationFeatureKey.ALERTS: FeatureDefinition(
        feature_key=MonetizationFeatureKey.ALERTS,
        boundary=FeatureBoundary.PAID,
        display_name="Alerts",
        description="Notify users about relevant changes to saved markets or targets.",
        boundary_rationale=(
            "This is paid because monitoring and notification delivery are ongoing "
            "workflow services, not the recommendation conclusion itself."
        ),
        trust_constraint="Alerts must report data changes without changing recommendation ranking.",
    ),
    MonetizationFeatureKey.ADVANCED_RECOMMENDATION_REPORTS: FeatureDefinition(
        feature_key=MonetizationFeatureKey.ADVANCED_RECOMMENDATION_REPORTS,
        boundary=FeatureBoundary.PAID,
        display_name="Advanced recommendation reports",
        description="Package deeper explanations, tradeoffs, and action planning into reports.",
        boundary_rationale=(
            "This is paid because it adds synthesis depth and decision support while "
            "leaving the basic recommendation preview free."
        ),
        trust_constraint="Reports explain recommendations; they must not own or alter ranking.",
    ),
    MonetizationFeatureKey.FULL_MARKET_COVERAGE: FeatureDefinition(
        feature_key=MonetizationFeatureKey.FULL_MARKET_COVERAGE,
        boundary=FeatureBoundary.PAID,
        display_name="Full market coverage",
        description="Access the full supported market catalog beyond public demo coverage.",
        boundary_rationale=(
            "This is paid because broad coverage requires data operations and quality "
            "maintenance beyond the public demo scope."
        ),
        trust_constraint="Coverage access must not imply paid users receive different rankings.",
    ),
    MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS: FeatureDefinition(
        feature_key=MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
        boundary=FeatureBoundary.PAID,
        display_name="Exportable strategy plans",
        description="Export structured market strategy plans for sharing or advising.",
        boundary_rationale=(
            "This is paid because export packaging is workflow value layered on top "
            "of visible recommendations."
        ),
        trust_constraint="Exports must preserve evidence and caveat labeling.",
    ),
    MonetizationFeatureKey.DEEPER_COMPANY_GEOGRAPHY: FeatureDefinition(
        feature_key=MonetizationFeatureKey.DEEPER_COMPANY_GEOGRAPHY,
        boundary=FeatureBoundary.PAID,
        display_name="Deeper company geography",
        description="Explore more complete company-region presence and geography context.",
        boundary_rationale=(
            "This is paid because company geography depth depends on maintained "
            "structured coverage beyond basic market exploration."
        ),
        trust_constraint="Company geography access must not bias market recommendations.",
    ),
    MonetizationFeatureKey.SAVED_COMPARISON_HISTORY: FeatureDefinition(
        feature_key=MonetizationFeatureKey.SAVED_COMPARISON_HISTORY,
        boundary=FeatureBoundary.PAID,
        display_name="Saved comparison history",
        description="Persist comparison runs and revisit previous tradeoff analysis.",
        boundary_rationale=(
            "This is paid because it adds account-level persistence and workflow "
            "continuity beyond limited free comparisons."
        ),
        trust_constraint="Saved history must not become hidden input to recommendation ranking.",
    ),
    MonetizationFeatureKey.FULL_REPORT_GENERATION: FeatureDefinition(
        feature_key=MonetizationFeatureKey.FULL_REPORT_GENERATION,
        boundary=FeatureBoundary.PAID,
        display_name="Full report generation",
        description="Generate complete report products from supported report catalog entries.",
        boundary_rationale=(
            "This is paid because full reports are packaged decision artifacts, not "
            "the basic recommendation conclusion."
        ),
        trust_constraint="Full reports must disclose evidence basis and preserve free previews.",
    ),
    MonetizationFeatureKey.INSTITUTIONAL_LICENSE_MANAGEMENT: FeatureDefinition(
        feature_key=MonetizationFeatureKey.INSTITUTIONAL_LICENSE_MANAGEMENT,
        boundary=FeatureBoundary.PAID,
        display_name="Institutional license management",
        description="Manage seats, cohorts, and organization-level access metadata.",
        boundary_rationale=(
            "This is paid because it supports institutional administration rather "
            "than individual recommendation access."
        ),
        trust_constraint="License metadata must not access private recommendation internals.",
    ),
    MonetizationFeatureKey.COHORT_GUIDANCE_TEMPLATES: FeatureDefinition(
        feature_key=MonetizationFeatureKey.COHORT_GUIDANCE_TEMPLATES,
        boundary=FeatureBoundary.PAID,
        display_name="Cohort guidance templates",
        description="Reusable market-guidance templates for advisors and program teams.",
        boundary_rationale=(
            "This is paid because it supports institutional advising workflows and "
            "program-scale repeatability."
        ),
        trust_constraint="Templates must remain guidance surfaces, not ranking inputs.",
    ),
    MonetizationFeatureKey.PRIVACY_PRESERVING_PROGRAM_INSIGHTS: FeatureDefinition(
        feature_key=MonetizationFeatureKey.PRIVACY_PRESERVING_PROGRAM_INSIGHTS,
        boundary=FeatureBoundary.PAID,
        display_name="Privacy-preserving program insights",
        description="Aggregate, non-private usage and coverage views for licensed programs.",
        boundary_rationale=(
            "This is paid because it adds buyer-facing reporting while preserving "
            "user trust boundaries."
        ),
        trust_constraint=(
            "Program insights must be aggregate and must not expose private "
            "recommendation internals or individual ranking reasons."
        ),
    ),
}

FEATURES = MappingProxyType(_FEATURES)


def feature_definitions() -> tuple[FeatureDefinition, ...]:
    return tuple(FEATURES[key] for key in MonetizationFeatureKey)


def feature_definition(
    feature_key: MonetizationFeatureKey | str,
) -> FeatureDefinition:
    return FEATURES[MonetizationFeatureKey(feature_key)]


def free_feature_keys() -> tuple[MonetizationFeatureKey, ...]:
    return tuple(
        feature.feature_key
        for feature in feature_definitions()
        if feature.boundary is FeatureBoundary.FREE
    )


def paid_feature_keys() -> tuple[MonetizationFeatureKey, ...]:
    return tuple(
        feature.feature_key
        for feature in feature_definitions()
        if feature.boundary is FeatureBoundary.PAID
    )
