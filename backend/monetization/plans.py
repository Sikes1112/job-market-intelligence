"""Subscription and license plan catalog.

Plans are product metadata, not payment-provider state. Prices are represented
as configurable placeholders so Stripe or another adapter can map them later
without becoming the authority for product entitlements.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.monetization.features import MonetizationFeatureKey, free_feature_keys
from backend.monetization.segments import AudienceSegmentKey, BuyerSegmentKey


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PlanKey(_Vocabulary):
    FREE = "free"
    INDIVIDUAL_MONTHLY = "individual_monthly"
    INDIVIDUAL_ANNUAL = "individual_annual"
    STUDENT_ANNUAL = "student_annual"
    CAREER_CENTER_LICENSE = "career_center_license"
    BOOTCAMP_LICENSE = "bootcamp_license"
    UNIVERSITY_LICENSE = "university_license"
    WORKFORCE_BOARD_LICENSE = "workforce_board_license"


class BuyerKind(_Vocabulary):
    INDIVIDUAL = "individual"
    INSTITUTIONAL = "institutional"


class BillingInterval(_Vocabulary):
    FREE = "free"
    MONTHLY = "monthly"
    ANNUAL = "annual"
    LICENSE_TERM = "license_term"


class UsageLimitUnit(_Vocabulary):
    PER_MONTH = "per_month"
    ACTIVE_ITEMS = "active_items"
    SEATS = "seats"


class UsageLimit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_key: MonetizationFeatureKey
    limit: int = Field(ge=0)
    unit: UsageLimitUnit
    description: str = Field(min_length=1, max_length=240)

    @field_validator("description")
    @classmethod
    def _description_not_blank(cls, value: str) -> str:
        return _clean_required_string(value, "usage limit")


class PriceConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    price_config_key: str | None = Field(default=None, min_length=1, max_length=128)
    placeholder_amount_cents: int | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    final_price: bool = False
    note: str = Field(min_length=1, max_length=240)

    @field_validator("price_config_key", "currency", "note")
    @classmethod
    def _optional_text_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required_string(value, "price configuration")


class PlanDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_key: PlanKey
    display_name: str = Field(min_length=1, max_length=128)
    buyer_kind: BuyerKind
    buyer_segment: BuyerSegmentKey | None
    billing_interval: BillingInterval
    intended_audience: tuple[AudienceSegmentKey, ...] = Field(min_length=1, max_length=8)
    included_feature_keys: tuple[MonetizationFeatureKey, ...] = Field(
        min_length=1,
        max_length=32,
    )
    usage_limits: tuple[UsageLimit, ...] = Field(default_factory=tuple, max_length=32)
    upgrade_plan_keys: tuple[PlanKey, ...] = Field(default_factory=tuple, max_length=8)
    price: PriceConfiguration

    @field_validator("display_name")
    @classmethod
    def _display_name_not_blank(cls, value: str) -> str:
        return _clean_required_string(value, "plan metadata")


def _clean_required_string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} entries must be strings")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{label} entries must not be blank")
    return stripped


_FREE_FEATURES = free_feature_keys()
_INDIVIDUAL_PAID_FEATURES = (
    MonetizationFeatureKey.SAVED_WATCHLISTS,
    MonetizationFeatureKey.ALERTS,
    MonetizationFeatureKey.ADVANCED_RECOMMENDATION_REPORTS,
    MonetizationFeatureKey.FULL_MARKET_COVERAGE,
    MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
    MonetizationFeatureKey.DEEPER_COMPANY_GEOGRAPHY,
    MonetizationFeatureKey.SAVED_COMPARISON_HISTORY,
    MonetizationFeatureKey.FULL_REPORT_GENERATION,
)
_INSTITUTIONAL_FEATURES = (
    MonetizationFeatureKey.INSTITUTIONAL_LICENSE_MANAGEMENT,
    MonetizationFeatureKey.COHORT_GUIDANCE_TEMPLATES,
    MonetizationFeatureKey.PRIVACY_PRESERVING_PROGRAM_INSIGHTS,
)
_ALL_AUDIENCES = (
    AudienceSegmentKey.STUDENTS,
    AudienceSegmentKey.EARLY_CAREER_JOB_SEEKERS,
    AudienceSegmentKey.RELOCATION_CANDIDATES,
    AudienceSegmentKey.PARENTS_ADVISORS,
)


def _price(
    key: str | None,
    *,
    amount: int | None,
    note: str,
) -> PriceConfiguration:
    return PriceConfiguration(
        price_config_key=key,
        placeholder_amount_cents=amount,
        note=note,
    )


def _limit(
    feature_key: MonetizationFeatureKey,
    limit: int,
    unit: UsageLimitUnit,
    description: str,
) -> UsageLimit:
    return UsageLimit(
        feature_key=feature_key,
        limit=limit,
        unit=unit,
        description=description,
    )


_PLANS: dict[PlanKey, PlanDefinition] = {
    PlanKey.FREE: PlanDefinition(
        plan_key=PlanKey.FREE,
        display_name="Free",
        buyer_kind=BuyerKind.INDIVIDUAL,
        buyer_segment=None,
        billing_interval=BillingInterval.FREE,
        intended_audience=_ALL_AUDIENCES,
        included_feature_keys=_FREE_FEATURES,
        usage_limits=(
            _limit(
                MonetizationFeatureKey.LIMITED_COMPARISONS,
                3,
                UsageLimitUnit.PER_MONTH,
                "Free users can run a small number of region comparisons each month.",
            ),
            _limit(
                MonetizationFeatureKey.LIMITED_PERSONALIZED_DISCOVERY,
                5,
                UsageLimitUnit.PER_MONTH,
                "Free users can preview personalized discovery before paid workflow tools.",
            ),
        ),
        upgrade_plan_keys=(
            PlanKey.INDIVIDUAL_MONTHLY,
            PlanKey.INDIVIDUAL_ANNUAL,
            PlanKey.STUDENT_ANNUAL,
        ),
        price=_price(
            None,
            amount=0,
            note="Free access; no payment-provider price identifier required.",
        ),
    ),
    PlanKey.INDIVIDUAL_MONTHLY: PlanDefinition(
        plan_key=PlanKey.INDIVIDUAL_MONTHLY,
        display_name="Individual Monthly",
        buyer_kind=BuyerKind.INDIVIDUAL,
        buyer_segment=None,
        billing_interval=BillingInterval.MONTHLY,
        intended_audience=(
            AudienceSegmentKey.EARLY_CAREER_JOB_SEEKERS,
            AudienceSegmentKey.RELOCATION_CANDIDATES,
            AudienceSegmentKey.PARENTS_ADVISORS,
        ),
        included_feature_keys=(*_FREE_FEATURES, *_INDIVIDUAL_PAID_FEATURES),
        usage_limits=(
            _limit(
                MonetizationFeatureKey.SAVED_WATCHLISTS,
                25,
                UsageLimitUnit.ACTIVE_ITEMS,
                "Individual monthly users can keep a practical active watchlist.",
            ),
            _limit(
                MonetizationFeatureKey.ALERTS,
                10,
                UsageLimitUnit.ACTIVE_ITEMS,
                "Individual monthly users can monitor a focused target set.",
            ),
            _limit(
                MonetizationFeatureKey.FULL_REPORT_GENERATION,
                3,
                UsageLimitUnit.PER_MONTH,
                "Monthly report generation is bounded for test economics.",
            ),
            _limit(
                MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
                10,
                UsageLimitUnit.PER_MONTH,
                "Monthly strategy exports use a placeholder test limit.",
            ),
        ),
        upgrade_plan_keys=(PlanKey.INDIVIDUAL_ANNUAL,),
        price=_price(
            "JMI_PRICE_INDIVIDUAL_MONTHLY",
            amount=1900,
            note="Placeholder test value; final pricing belongs to configuration.",
        ),
    ),
    PlanKey.INDIVIDUAL_ANNUAL: PlanDefinition(
        plan_key=PlanKey.INDIVIDUAL_ANNUAL,
        display_name="Individual Annual",
        buyer_kind=BuyerKind.INDIVIDUAL,
        buyer_segment=None,
        billing_interval=BillingInterval.ANNUAL,
        intended_audience=(
            AudienceSegmentKey.EARLY_CAREER_JOB_SEEKERS,
            AudienceSegmentKey.RELOCATION_CANDIDATES,
            AudienceSegmentKey.PARENTS_ADVISORS,
        ),
        included_feature_keys=(*_FREE_FEATURES, *_INDIVIDUAL_PAID_FEATURES),
        usage_limits=(
            _limit(
                MonetizationFeatureKey.SAVED_WATCHLISTS,
                100,
                UsageLimitUnit.ACTIVE_ITEMS,
                "Annual users can maintain broader active watchlists.",
            ),
            _limit(
                MonetizationFeatureKey.ALERTS,
                25,
                UsageLimitUnit.ACTIVE_ITEMS,
                "Annual users can monitor a broader target set.",
            ),
            _limit(
                MonetizationFeatureKey.FULL_REPORT_GENERATION,
                10,
                UsageLimitUnit.PER_MONTH,
                "Annual report generation has a higher placeholder test limit.",
            ),
            _limit(
                MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
                40,
                UsageLimitUnit.PER_MONTH,
                "Annual strategy exports use a higher placeholder test limit.",
            ),
        ),
        upgrade_plan_keys=(),
        price=_price(
            "JMI_PRICE_INDIVIDUAL_ANNUAL",
            amount=14900,
            note="Placeholder test value; final pricing belongs to configuration.",
        ),
    ),
    PlanKey.STUDENT_ANNUAL: PlanDefinition(
        plan_key=PlanKey.STUDENT_ANNUAL,
        display_name="Student Annual",
        buyer_kind=BuyerKind.INDIVIDUAL,
        buyer_segment=None,
        billing_interval=BillingInterval.ANNUAL,
        intended_audience=(AudienceSegmentKey.STUDENTS,),
        included_feature_keys=(*_FREE_FEATURES, *_INDIVIDUAL_PAID_FEATURES),
        usage_limits=(
            _limit(
                MonetizationFeatureKey.SAVED_WATCHLISTS,
                50,
                UsageLimitUnit.ACTIVE_ITEMS,
                "Student users can maintain a school-year search watchlist.",
            ),
            _limit(
                MonetizationFeatureKey.ALERTS,
                10,
                UsageLimitUnit.ACTIVE_ITEMS,
                "Student users can monitor a focused target set.",
            ),
            _limit(
                MonetizationFeatureKey.FULL_REPORT_GENERATION,
                5,
                UsageLimitUnit.PER_MONTH,
                "Student annual report generation uses a discounted-plan test limit.",
            ),
            _limit(
                MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
                15,
                UsageLimitUnit.PER_MONTH,
                "Student strategy exports use a discounted-plan test limit.",
            ),
        ),
        upgrade_plan_keys=(PlanKey.INDIVIDUAL_ANNUAL,),
        price=_price(
            "JMI_PRICE_STUDENT_ANNUAL",
            amount=7900,
            note="Placeholder discounted test value; final pricing belongs to configuration.",
        ),
    ),
    PlanKey.CAREER_CENTER_LICENSE: PlanDefinition(
        plan_key=PlanKey.CAREER_CENTER_LICENSE,
        display_name="Career Center License",
        buyer_kind=BuyerKind.INSTITUTIONAL,
        buyer_segment=BuyerSegmentKey.CAREER_CENTERS,
        billing_interval=BillingInterval.LICENSE_TERM,
        intended_audience=(AudienceSegmentKey.STUDENTS, AudienceSegmentKey.PARENTS_ADVISORS),
        included_feature_keys=(
            *_FREE_FEATURES,
            *_INDIVIDUAL_PAID_FEATURES,
            *_INSTITUTIONAL_FEATURES,
        ),
        usage_limits=(
            _limit(
                MonetizationFeatureKey.INSTITUTIONAL_LICENSE_MANAGEMENT,
                250,
                UsageLimitUnit.SEATS,
                "Career-center license placeholder seat limit.",
            ),
            _limit(
                MonetizationFeatureKey.FULL_REPORT_GENERATION,
                100,
                UsageLimitUnit.PER_MONTH,
                "Institutional report generation test limit.",
            ),
            _limit(
                MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
                500,
                UsageLimitUnit.PER_MONTH,
                "Career-center strategy exports use an institutional test limit.",
            ),
        ),
        upgrade_plan_keys=(PlanKey.UNIVERSITY_LICENSE,),
        price=_price(
            "JMI_PRICE_CAREER_CENTER_LICENSE",
            amount=None,
            note="Configurable institutional quote; no final list price is encoded.",
        ),
    ),
    PlanKey.BOOTCAMP_LICENSE: PlanDefinition(
        plan_key=PlanKey.BOOTCAMP_LICENSE,
        display_name="Bootcamp License",
        buyer_kind=BuyerKind.INSTITUTIONAL,
        buyer_segment=BuyerSegmentKey.BOOTCAMPS,
        billing_interval=BillingInterval.LICENSE_TERM,
        intended_audience=(
            AudienceSegmentKey.STUDENTS,
            AudienceSegmentKey.EARLY_CAREER_JOB_SEEKERS,
        ),
        included_feature_keys=(
            *_FREE_FEATURES,
            *_INDIVIDUAL_PAID_FEATURES,
            *_INSTITUTIONAL_FEATURES,
        ),
        usage_limits=(
            _limit(
                MonetizationFeatureKey.INSTITUTIONAL_LICENSE_MANAGEMENT,
                150,
                UsageLimitUnit.SEATS,
                "Bootcamp license placeholder seat limit.",
            ),
            _limit(
                MonetizationFeatureKey.FULL_REPORT_GENERATION,
                75,
                UsageLimitUnit.PER_MONTH,
                "Bootcamp report generation test limit.",
            ),
            _limit(
                MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
                300,
                UsageLimitUnit.PER_MONTH,
                "Bootcamp strategy exports use an institutional test limit.",
            ),
        ),
        upgrade_plan_keys=(PlanKey.CAREER_CENTER_LICENSE,),
        price=_price(
            "JMI_PRICE_BOOTCAMP_LICENSE",
            amount=None,
            note="Configurable institutional quote; no final list price is encoded.",
        ),
    ),
    PlanKey.UNIVERSITY_LICENSE: PlanDefinition(
        plan_key=PlanKey.UNIVERSITY_LICENSE,
        display_name="University License",
        buyer_kind=BuyerKind.INSTITUTIONAL,
        buyer_segment=BuyerSegmentKey.UNIVERSITIES,
        billing_interval=BillingInterval.LICENSE_TERM,
        intended_audience=_ALL_AUDIENCES,
        included_feature_keys=(
            *_FREE_FEATURES,
            *_INDIVIDUAL_PAID_FEATURES,
            *_INSTITUTIONAL_FEATURES,
        ),
        usage_limits=(
            _limit(
                MonetizationFeatureKey.INSTITUTIONAL_LICENSE_MANAGEMENT,
                2500,
                UsageLimitUnit.SEATS,
                "University license placeholder seat limit.",
            ),
            _limit(
                MonetizationFeatureKey.FULL_REPORT_GENERATION,
                1000,
                UsageLimitUnit.PER_MONTH,
                "University report generation test limit.",
            ),
            _limit(
                MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
                5000,
                UsageLimitUnit.PER_MONTH,
                "University strategy exports use an institutional test limit.",
            ),
        ),
        upgrade_plan_keys=(),
        price=_price(
            "JMI_PRICE_UNIVERSITY_LICENSE",
            amount=None,
            note="Configurable institutional quote; no final list price is encoded.",
        ),
    ),
    PlanKey.WORKFORCE_BOARD_LICENSE: PlanDefinition(
        plan_key=PlanKey.WORKFORCE_BOARD_LICENSE,
        display_name="Workforce Board License",
        buyer_kind=BuyerKind.INSTITUTIONAL,
        buyer_segment=BuyerSegmentKey.WORKFORCE_BOARDS,
        billing_interval=BillingInterval.LICENSE_TERM,
        intended_audience=(
            AudienceSegmentKey.EARLY_CAREER_JOB_SEEKERS,
            AudienceSegmentKey.RELOCATION_CANDIDATES,
            AudienceSegmentKey.PARENTS_ADVISORS,
        ),
        included_feature_keys=(
            *_FREE_FEATURES,
            *_INDIVIDUAL_PAID_FEATURES,
            *_INSTITUTIONAL_FEATURES,
        ),
        usage_limits=(
            _limit(
                MonetizationFeatureKey.INSTITUTIONAL_LICENSE_MANAGEMENT,
                500,
                UsageLimitUnit.SEATS,
                "Workforce-board license placeholder seat limit.",
            ),
            _limit(
                MonetizationFeatureKey.FULL_REPORT_GENERATION,
                250,
                UsageLimitUnit.PER_MONTH,
                "Workforce-board report generation test limit.",
            ),
            _limit(
                MonetizationFeatureKey.EXPORTABLE_STRATEGY_PLANS,
                1000,
                UsageLimitUnit.PER_MONTH,
                "Workforce-board strategy exports use an institutional test limit.",
            ),
        ),
        upgrade_plan_keys=(),
        price=_price(
            "JMI_PRICE_WORKFORCE_BOARD_LICENSE",
            amount=None,
            note="Configurable institutional quote; no final list price is encoded.",
        ),
    ),
}

PLANS = MappingProxyType(_PLANS)


def plan_definitions() -> tuple[PlanDefinition, ...]:
    return tuple(PLANS[key] for key in PlanKey)


def plan_definition(plan_key: PlanKey | str) -> PlanDefinition:
    return PLANS[PlanKey(plan_key)]


def usage_limit_for_feature(
    plan: PlanDefinition,
    feature_key: MonetizationFeatureKey | str,
) -> UsageLimit | None:
    normalized = MonetizationFeatureKey(feature_key)
    for usage_limit in plan.usage_limits:
        if usage_limit.feature_key is normalized:
            return usage_limit
    return None
