"""Deterministic market strategy planning from ranked recommendations.

Layer 14D consumes Layer 14C ranking outputs. It does not rank from scratch,
invent current openings, call AI providers, scrape live data, or own scoring,
freshness, confidence, provenance, or coverage truth.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.recommendations.goal_modes import RecommendationScoreComponent
from backend.recommendations.models import (
    ManualVerificationCategory,
    RecommendationClaimSupport,
    RecommendationEvidenceBasis,
    RecommendationEvidenceReference,
    RecommendationEvidenceStrength,
    RecommendationGoalMode,
    RecommendationImportance,
    RecommendationManualVerificationItem,
    RecommendationTarget,
    RecommendationTargetType,
    RecommendationTradeoffCategory,
)
from backend.recommendations.ranking import (
    RecommendationRankingItem,
    RecommendationRankingResult,
)

STRATEGY_GENERATOR_VERSION = "layer14d_market_strategy_v1"
PRIMARY_SCORE_THRESHOLD = 0.55
SECONDARY_SCORE_THRESHOLD = 0.35
WATCHLIST_SCORE_THRESHOLD = 0.45
WEAK_EVIDENCE_THRESHOLD = 0.35
PROXY_HEAVY_WEIGHT_THRESHOLD = 0.35


class StrategyRegionTargetRole(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    FALLBACK = "fallback"


class StrategyTimingCategory(StrEnum):
    PRIORITIZE_HIGH_FIT = "prioritize_high_fit"
    VERIFY_CURRENT_POSTINGS = "verify_current_postings"
    MONITOR_WATCHLIST = "monitor_watchlist"
    REVISIT_AFTER_REFRESH = "revisit_after_refresh"
    INTERNSHIP_COOP_CHECK = "internship_coop_check"
    LOCATION_REQUIREMENTS_CHECK = "location_requirements_check"


class StrategyWatchlistCategory(StrEnum):
    EVIDENCE_QUALITY = "evidence_quality"
    PROXY_HEAVY = "proxy_heavy"
    MISSING_DATA = "missing_data"
    TRADEOFF_UPSIDE = "tradeoff_upside"


class StrategyWarningCategory(StrEnum):
    COVERAGE = "coverage"
    CONFIDENCE = "confidence"
    FRESHNESS = "freshness"
    PROVENANCE = "provenance"
    PROXY = "proxy"
    MISSING_DATA = "missing_data"
    MANUAL_VERIFICATION = "manual_verification"


class StrategySourceRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1, max_length=192)
    rank: int = Field(ge=1)
    target: RecommendationTarget
    final_score: float = Field(ge=0.0, le=1.0)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=50)

    @field_validator("warnings")
    @classmethod
    def _warnings_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(item.strip() for item in value if item.strip())


class StrategyRegionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target: RecommendationTarget
    target_role: StrategyRegionTargetRole
    source_rank: int = Field(ge=1)
    final_score: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1, max_length=512)
    tradeoff_categories: tuple[RecommendationTradeoffCategory, ...] = Field(
        default_factory=tuple,
        max_length=12,
    )
    source_recommendation_ids: tuple[str, ...] = Field(min_length=1, max_length=20)
    evidence_strength: RecommendationEvidenceStrength
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    support: RecommendationClaimSupport = RecommendationClaimSupport.DIRECT
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )

    @model_validator(mode="after")
    def _traceable_region_target(self) -> StrategyRegionTarget:
        _validate_strategy_trace(
            evidence_basis=self.evidence_basis,
            evidence_strength=self.evidence_strength,
            support=self.support,
            evidence_refs=self.evidence_refs,
            source_recommendation_ids=self.source_recommendation_ids,
        )
        return self


class StrategyCompanyTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target: RecommendationTarget
    source_rank: int = Field(ge=1)
    final_score: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1, max_length=512)
    source_recommendation_ids: tuple[str, ...] = Field(min_length=1, max_length=20)
    evidence_strength: RecommendationEvidenceStrength
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    support: RecommendationClaimSupport = RecommendationClaimSupport.DIRECT
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )

    @model_validator(mode="after")
    def _traceable_company_target(self) -> StrategyCompanyTarget:
        if self.target.target_type is not RecommendationTargetType.COMPANY:
            raise ValueError("company strategy targets must use company target type")
        _validate_strategy_trace(
            evidence_basis=self.evidence_basis,
            evidence_strength=self.evidence_strength,
            support=self.support,
            evidence_refs=self.evidence_refs,
            source_recommendation_ids=self.source_recommendation_ids,
        )
        return self


class StrategyCompanyCategoryTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target: RecommendationTarget
    rationale: str = Field(min_length=1, max_length=512)
    source_recommendation_ids: tuple[str, ...] = Field(min_length=1, max_length=20)
    evidence_strength: RecommendationEvidenceStrength
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    support: RecommendationClaimSupport = RecommendationClaimSupport.DIRECT
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )

    @model_validator(mode="after")
    def _traceable_company_category(self) -> StrategyCompanyCategoryTarget:
        if self.target.target_type is not RecommendationTargetType.COMPANY_CATEGORY:
            raise ValueError("company categories must use company_category target type")
        _validate_strategy_trace(
            evidence_basis=self.evidence_basis,
            evidence_strength=self.evidence_strength,
            support=self.support,
            evidence_refs=self.evidence_refs,
            source_recommendation_ids=self.source_recommendation_ids,
        )
        return self


class StrategyRoleFamilyTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target: RecommendationTarget
    rationale: str = Field(min_length=1, max_length=512)
    source_recommendation_ids: tuple[str, ...] = Field(min_length=1, max_length=20)
    evidence_strength: RecommendationEvidenceStrength
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    support: RecommendationClaimSupport = RecommendationClaimSupport.DIRECT
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )

    @model_validator(mode="after")
    def _traceable_role_family(self) -> StrategyRoleFamilyTarget:
        if self.target.target_type is not RecommendationTargetType.ROLE_FAMILY:
            raise ValueError("role-family strategy targets must use role_family target type")
        _validate_strategy_trace(
            evidence_basis=self.evidence_basis,
            evidence_strength=self.evidence_strength,
            support=self.support,
            evidence_refs=self.evidence_refs,
            source_recommendation_ids=self.source_recommendation_ids,
        )
        return self


class StrategyTimingGuidance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    timing_category: StrategyTimingCategory
    label: str = Field(min_length=1, max_length=128)
    guidance: str = Field(min_length=1, max_length=512)
    importance: RecommendationImportance = RecommendationImportance.MEDIUM
    source_recommendation_ids: tuple[str, ...] = Field(min_length=1, max_length=20)
    evidence_strength: RecommendationEvidenceStrength
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    support: RecommendationClaimSupport = RecommendationClaimSupport.DIRECT
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )

    @model_validator(mode="after")
    def _traceable_timing_guidance(self) -> StrategyTimingGuidance:
        _validate_strategy_trace(
            evidence_basis=self.evidence_basis,
            evidence_strength=self.evidence_strength,
            support=self.support,
            evidence_refs=self.evidence_refs,
            source_recommendation_ids=self.source_recommendation_ids,
        )
        return self


class StrategyWatchlistItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    watchlist_category: StrategyWatchlistCategory
    target: RecommendationTarget
    reason: str = Field(min_length=1, max_length=512)
    upside: str = Field(min_length=1, max_length=512)
    what_to_verify: str = Field(min_length=1, max_length=512)
    revisit_after_refresh: bool = False
    source_recommendation_ids: tuple[str, ...] = Field(min_length=1, max_length=20)
    evidence_strength: RecommendationEvidenceStrength
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    support: RecommendationClaimSupport = RecommendationClaimSupport.DIRECT
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )

    @model_validator(mode="after")
    def _traceable_watchlist_item(self) -> StrategyWatchlistItem:
        _validate_strategy_trace(
            evidence_basis=self.evidence_basis,
            evidence_strength=self.evidence_strength,
            support=self.support,
            evidence_refs=self.evidence_refs,
            source_recommendation_ids=self.source_recommendation_ids,
        )
        return self


class StrategyManualVerificationEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item: RecommendationManualVerificationItem
    source_recommendation_ids: tuple[str, ...] = Field(min_length=1, max_length=20)


class StrategyManualVerificationChecklist(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[StrategyManualVerificationEntry, ...] = Field(
        default_factory=tuple,
        max_length=50,
    )


class StrategyEvidenceWarning(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    warning_category: StrategyWarningCategory
    label: str = Field(min_length=1, max_length=128)
    detail: str | None = Field(default=None, min_length=1, max_length=512)
    source_recommendation_ids: tuple[str, ...] = Field(min_length=1, max_length=20)
    evidence_strength: RecommendationEvidenceStrength
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    support: RecommendationClaimSupport = RecommendationClaimSupport.DIRECT
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )

    @model_validator(mode="after")
    def _traceable_warning(self) -> StrategyEvidenceWarning:
        _validate_strategy_trace(
            evidence_basis=self.evidence_basis,
            evidence_strength=self.evidence_strength,
            support=self.support,
            evidence_refs=self.evidence_refs,
            source_recommendation_ids=self.source_recommendation_ids,
        )
        return self


class MarketStrategyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    goal_mode: RecommendationGoalMode
    strategy_version: str = STRATEGY_GENERATOR_VERSION
    source_recommendations: tuple[StrategySourceRecommendation, ...] = Field(
        min_length=1,
        max_length=100,
    )
    primary_region_targets: tuple[StrategyRegionTarget, ...] = Field(
        default_factory=tuple,
        max_length=10,
    )
    secondary_region_targets: tuple[StrategyRegionTarget, ...] = Field(
        default_factory=tuple,
        max_length=10,
    )
    fallback_region_targets: tuple[StrategyRegionTarget, ...] = Field(
        default_factory=tuple,
        max_length=10,
    )
    company_targets: tuple[StrategyCompanyTarget, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )
    company_category_targets: tuple[StrategyCompanyCategoryTarget, ...] = Field(
        default_factory=tuple,
        max_length=10,
    )
    role_family_targets: tuple[StrategyRoleFamilyTarget, ...] = Field(
        default_factory=tuple,
        max_length=12,
    )
    timing_guidance: tuple[StrategyTimingGuidance, ...] = Field(
        default_factory=tuple,
        max_length=12,
    )
    watchlist_items: tuple[StrategyWatchlistItem, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )
    manual_verification_checklist: StrategyManualVerificationChecklist
    evidence_warnings: tuple[StrategyEvidenceWarning, ...] = Field(
        default_factory=tuple,
        max_length=50,
    )

    @model_validator(mode="after")
    def _plan_has_actionable_structure(self) -> MarketStrategyPlan:
        if not any(
            (
                self.primary_region_targets,
                self.secondary_region_targets,
                self.fallback_region_targets,
                self.company_targets,
                self.company_category_targets,
                self.role_family_targets,
                self.timing_guidance,
                self.watchlist_items,
            )
        ):
            raise ValueError("market strategy plan must contain structured strategy items")
        known_source_ids = {source.source_id for source in self.source_recommendations}
        for source_ids in _all_strategy_source_ids(self):
            if not set(source_ids) <= known_source_ids:
                raise ValueError("strategy items must reference known ranked recommendations")
        return self


def generate_market_strategy_plan(
    region_rankings: RecommendationRankingResult,
    *,
    company_rankings: RecommendationRankingResult | None = None,
    goal_mode: RecommendationGoalMode | str | None = None,
    max_primary_regions: int = 3,
    max_secondary_regions: int = 3,
    max_fallback_regions: int = 3,
    max_watchlist_items: int = 6,
    max_company_targets: int = 5,
) -> MarketStrategyPlan:
    """Generate a deterministic strategy plan from ranked recommendation outputs."""

    goal = RecommendationGoalMode(goal_mode) if goal_mode is not None else region_rankings.goal_mode
    if region_rankings.goal_mode is not goal:
        raise ValueError("region ranking goal mode must match requested strategy goal")
    if company_rankings is not None and company_rankings.goal_mode is not goal:
        raise ValueError("company ranking goal mode must match requested strategy goal")

    region_items = tuple(region_rankings.ranked_recommendations)
    company_items = tuple(company_rankings.ranked_recommendations) if company_rankings else ()
    sources = _source_references(region_items, "region") + _source_references(
        company_items,
        "company",
    )
    primary_items = _select_primary_regions(region_items, max_primary_regions)
    watchlist_items = _build_watchlist_items(region_items, max_watchlist_items)
    watchlist_ids = {item.target.target_id for item in watchlist_items}
    primary_ids = {item.target.target_id for item in primary_items}
    fallback_items = _select_fallback_regions(
        region_items,
        goal=goal,
        excluded_ids=primary_ids | watchlist_ids,
        limit=max_fallback_regions,
    )
    fallback_ids = {item.target.target_id for item in fallback_items}
    secondary_items = _select_secondary_regions(
        region_items,
        excluded_ids=primary_ids | watchlist_ids | fallback_ids,
        limit=max_secondary_regions,
    )

    primary_targets = tuple(
        _region_target(item, StrategyRegionTargetRole.PRIMARY, "Top ranked actionable target")
        for item in primary_items
    )
    secondary_targets = tuple(
        _region_target(
            item,
            StrategyRegionTargetRole.SECONDARY,
            "Viable ranked target after primary and fallback selections",
        )
        for item in secondary_items
    )
    fallback_targets = tuple(
        _region_target(
            item,
            StrategyRegionTargetRole.FALLBACK,
            _fallback_rationale(item, goal),
        )
        for item in fallback_items
    )
    company_targets = tuple(
        _company_target(item)
        for item in company_items[:max_company_targets]
    )
    category_targets = _company_category_targets(company_items, region_items, goal=goal)
    role_targets = _role_family_targets(goal, region_items, company_items)
    manual_entries = _manual_verification_entries(
        region_items,
        company_items,
        goal=goal,
        has_heuristic_role_targets=bool(role_targets),
        has_company_rankings=bool(company_items),
    )
    timing = _timing_guidance(
        goal,
        primary_items=primary_items,
        watchlist_items=watchlist_items,
        region_items=region_items,
        company_items=company_items,
        has_heuristic_role_targets=bool(role_targets),
    )
    warnings = _evidence_warnings(
        region_items,
        company_items,
        include_company_gap=not company_items,
    )
    return MarketStrategyPlan(
        goal_mode=goal,
        source_recommendations=sources,
        primary_region_targets=primary_targets,
        secondary_region_targets=secondary_targets,
        fallback_region_targets=fallback_targets,
        company_targets=company_targets,
        company_category_targets=category_targets,
        role_family_targets=role_targets,
        timing_guidance=timing,
        watchlist_items=watchlist_items,
        manual_verification_checklist=StrategyManualVerificationChecklist(
            items=manual_entries,
        ),
        evidence_warnings=warnings,
    )


def _select_primary_regions(
    items: tuple[RecommendationRankingItem, ...],
    limit: int,
) -> tuple[RecommendationRankingItem, ...]:
    actionable = [
        item
        for item in items
        if item.final_score >= PRIMARY_SCORE_THRESHOLD and _watchlist_signal(item) is None
    ]
    if not actionable and items and _watchlist_signal(items[0]) is None:
        actionable = [items[0]]
    return tuple(actionable[:limit])


def _select_secondary_regions(
    items: tuple[RecommendationRankingItem, ...],
    *,
    excluded_ids: set[str],
    limit: int,
) -> tuple[RecommendationRankingItem, ...]:
    return tuple(
        item
        for item in items
        if item.target.target_id not in excluded_ids
        and item.final_score >= SECONDARY_SCORE_THRESHOLD
        and _watchlist_signal(item) is None
    )[:limit]


def _select_fallback_regions(
    items: tuple[RecommendationRankingItem, ...],
    *,
    goal: RecommendationGoalMode,
    excluded_ids: set[str],
    limit: int,
) -> tuple[RecommendationRankingItem, ...]:
    candidates = [
        item
        for item in items
        if item.target.target_id not in excluded_ids
        and item.final_score >= SECONDARY_SCORE_THRESHOLD
        and _watchlist_signal(item) is None
    ]
    if goal in {
        RecommendationGoalMode.MAXIMIZE_LOWER_COMPETITION,
        RecommendationGoalMode.MAXIMIZE_UNDERRATED_MARKETS,
    }:
        candidates.sort(
            key=lambda item: (
                -(
                    _component_value(
                        item,
                        RecommendationScoreComponent.LOWER_COMPETITION_PROXY,
                    )
                    or 0
                ),
                -item.final_score,
                item.rank,
            )
        )
        return tuple(
            item
            for item in candidates
            if (_component_value(item, RecommendationScoreComponent.LOWER_COMPETITION_PROXY) or 0)
            >= 0.5
        )[:limit]
    return tuple(
        item
        for item in candidates
        if item.explanation.tradeoffs
        or _component_value(item, RecommendationScoreComponent.LOWER_COMPETITION_PROXY)
        is not None
    )[:limit]


def _region_target(
    item: RecommendationRankingItem,
    role: StrategyRegionTargetRole,
    rationale: str,
) -> StrategyRegionTarget:
    refs = _item_evidence_refs(item)
    basis = _basis_from_refs(refs)
    return StrategyRegionTarget(
        target=item.target,
        target_role=role,
        source_rank=item.rank,
        final_score=item.final_score,
        rationale=rationale,
        tradeoff_categories=tuple(
            tradeoff.tradeoff_category for tradeoff in item.explanation.tradeoffs
        ),
        source_recommendation_ids=(_source_id(item),),
        evidence_strength=RecommendationEvidenceStrength.MODERATE,
        evidence_basis=basis,
        evidence_refs=refs,
    )


def _company_target(item: RecommendationRankingItem) -> StrategyCompanyTarget:
    refs = _item_evidence_refs(item)
    return StrategyCompanyTarget(
        target=item.target,
        source_rank=item.rank,
        final_score=item.final_score,
        rationale="Company target is included because it appears in supplied ranked outputs.",
        source_recommendation_ids=(_source_id(item),),
        evidence_strength=RecommendationEvidenceStrength.MODERATE,
        evidence_basis=_basis_from_refs(refs),
        evidence_refs=refs,
    )


def _company_category_targets(
    company_items: tuple[RecommendationRankingItem, ...],
    region_items: tuple[RecommendationRankingItem, ...],
    *,
    goal: RecommendationGoalMode,
) -> tuple[StrategyCompanyCategoryTarget, ...]:
    if not company_items:
        return ()
    categories: list[StrategyCompanyCategoryTarget] = []
    ai_items = [
        item
        for item in company_items
        if (_component_value(item, RecommendationScoreComponent.AI_CLOUD_CONCENTRATION) or 0)
        >= 0.7
    ]
    if ai_items:
        categories.append(
            _company_category(
                "ai_cloud_oriented_companies",
                "AI/cloud-oriented companies from ranked inputs",
                (
                    "Derived from supplied company rankings with AI/cloud component "
                    "evidence; it does not claim current openings."
                ),
                ai_items,
                inferred=any(
                    _component_is_proxy(
                        item,
                        RecommendationScoreComponent.AI_CLOUD_CONCENTRATION,
                    )
                    for item in ai_items
                ),
            )
        )
    if goal is RecommendationGoalMode.MAXIMIZE_PRESTIGE:
        prestige_items = [
            item
            for item in company_items
            if (_component_value(item, RecommendationScoreComponent.PRESTIGE_DENSITY) or 0)
            >= 0.7
        ]
        if prestige_items:
            categories.append(
                _company_category(
                    "high_prestige_ranked_companies",
                    "High-prestige companies from ranked inputs",
                    "Derived from supplied company prestige metadata in ranked outputs.",
                    prestige_items,
                    inferred=any(
                        _component_is_proxy(
                            item,
                            RecommendationScoreComponent.PRESTIGE_DENSITY,
                        )
                        for item in prestige_items
                    ),
                )
            )
    if goal in {
        RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS,
        RecommendationGoalMode.MAXIMIZE_INTERNSHIP_COOP_ACCESS,
    }:
        entry_items = [
            item
            for item in company_items
            if (_component_value(item, RecommendationScoreComponent.ENTRY_LEVEL_ACCESS) or 0)
            >= 0.65
        ]
        if entry_items:
            categories.append(
                _company_category(
                    "entry_level_signal_companies",
                    "Companies with stronger entry-level signals from ranked inputs",
                    "Derived from supplied entry-level company ranking components.",
                    entry_items,
                    inferred=False,
                )
            )
    return tuple(categories[:3])


def _company_category(
    target_id: str,
    label: str,
    rationale: str,
    items: Sequence[RecommendationRankingItem],
    *,
    inferred: bool,
) -> StrategyCompanyCategoryTarget:
    refs = _dedupe_refs(
        tuple(ref for item in items for ref in _item_evidence_refs(item))
    )[:25]
    basis = _basis_from_refs(
        refs,
        extra=(
            (RecommendationEvidenceBasis.HEURISTIC_INFERENCE,)
            if inferred
            else ()
        ),
    )
    return StrategyCompanyCategoryTarget(
        target=RecommendationTarget(
            target_type=RecommendationTargetType.COMPANY_CATEGORY,
            target_id=target_id,
            display_label=label,
            related_target_ids=tuple(item.target.target_id for item in items[:10]),
        ),
        rationale=rationale,
        source_recommendation_ids=tuple(_source_id(item) for item in items[:10]),
        evidence_strength=(
            RecommendationEvidenceStrength.INFERRED
            if inferred
            else RecommendationEvidenceStrength.MODERATE
        ),
        evidence_basis=basis,
        support=(
            RecommendationClaimSupport.INFERRED
            if inferred
            else RecommendationClaimSupport.DIRECT
        ),
        evidence_refs=refs,
    )


def _role_family_targets(
    goal: RecommendationGoalMode,
    region_items: tuple[RecommendationRankingItem, ...],
    company_items: tuple[RecommendationRankingItem, ...],
) -> tuple[StrategyRoleFamilyTarget, ...]:
    source_items = (company_items or region_items)[:3]
    if not source_items:
        return ()
    role_labels = _heuristic_role_labels(goal)
    return tuple(
        StrategyRoleFamilyTarget(
            target=RecommendationTarget(
                target_type=RecommendationTargetType.ROLE_FAMILY,
                target_id=_slug(label),
                display_label=label,
            ),
            rationale=(
                "Heuristic role-family suggestion tied to the selected goal mode; "
                "it does not claim current openings."
            ),
            source_recommendation_ids=tuple(_source_id(item) for item in source_items),
            evidence_strength=RecommendationEvidenceStrength.INFERRED,
            evidence_basis=(RecommendationEvidenceBasis.HEURISTIC_INFERENCE,),
            support=RecommendationClaimSupport.INFERRED,
        )
        for label in role_labels
    )


def _heuristic_role_labels(goal: RecommendationGoalMode) -> tuple[str, ...]:
    mapping = {
        RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS: (
            "Business/data analyst",
            "Implementation/solutions analyst",
        ),
        RecommendationGoalMode.MAXIMIZE_INTERNSHIP_COOP_ACCESS: (
            "Product analyst",
            "Business/data analyst",
        ),
        RecommendationGoalMode.MAXIMIZE_AI_CLOUD_CONCENTRATION: (
            "AI product operations",
            "Cloud solutions associate",
            "Customer-facing AI solutions associate",
        ),
        RecommendationGoalMode.MAXIMIZE_PRESTIGE: (
            "Product analyst",
            "Technical program analyst",
        ),
        RecommendationGoalMode.MAXIMIZE_LOWER_COMPETITION: (
            "Implementation/solutions analyst",
            "Business/data analyst",
        ),
        RecommendationGoalMode.MAXIMIZE_UNDERRATED_MARKETS: (
            "Implementation/solutions analyst",
            "Customer-facing AI solutions associate",
        ),
        RecommendationGoalMode.MAXIMIZE_GEOGRAPHIC_FLEXIBILITY: (
            "Cloud solutions associate",
            "Customer-facing AI solutions associate",
        ),
    }
    return mapping[goal]


def _timing_guidance(
    goal: RecommendationGoalMode,
    *,
    primary_items: tuple[RecommendationRankingItem, ...],
    watchlist_items: tuple[StrategyWatchlistItem, ...],
    region_items: tuple[RecommendationRankingItem, ...],
    company_items: tuple[RecommendationRankingItem, ...],
    has_heuristic_role_targets: bool,
) -> tuple[StrategyTimingGuidance, ...]:
    source_items = primary_items or region_items[:1]
    timing: list[StrategyTimingGuidance] = []
    if source_items:
        refs = _dedupe_refs(
            tuple(ref for item in source_items for ref in _item_evidence_refs(item))
        )
        timing.append(
            StrategyTimingGuidance(
                timing_category=StrategyTimingCategory.PRIORITIZE_HIGH_FIT,
                label="Apply first to high-fit ranked targets",
                guidance=(
                    "Start with the highest-ranked targets that have usable confidence, "
                    "freshness, and coverage context."
                ),
                importance=RecommendationImportance.HIGH,
                source_recommendation_ids=tuple(_source_id(item) for item in source_items),
                evidence_strength=RecommendationEvidenceStrength.MODERATE,
                evidence_basis=_basis_from_refs(refs),
                evidence_refs=refs,
            )
        )
    posting_sources = (company_items or region_items)[:3]
    if posting_sources:
        timing.append(
            _missing_data_timing(
                StrategyTimingCategory.VERIFY_CURRENT_POSTINGS,
                "Verify current postings before acting",
                "Check current company/career pages before treating ranked targets as actionable.",
                posting_sources,
                importance=RecommendationImportance.HIGH,
            )
        )
    if watchlist_items:
        timing.append(
            StrategyTimingGuidance(
                timing_category=StrategyTimingCategory.MONITOR_WATCHLIST,
                label="Monitor watchlist targets before committing effort",
                guidance=(
                    "Use watchlist targets for monitoring until their weak, stale, "
                    "missing, or proxy-heavy evidence is resolved."
                ),
                importance=RecommendationImportance.MEDIUM,
                source_recommendation_ids=tuple(
                    source_id
                    for item in watchlist_items
                    for source_id in item.source_recommendation_ids
                )[:20],
                evidence_strength=RecommendationEvidenceStrength.MISSING,
                evidence_basis=(RecommendationEvidenceBasis.MISSING_DATA,),
            )
        )
        if any(item.revisit_after_refresh for item in watchlist_items):
            timing.append(
                StrategyTimingGuidance(
                    timing_category=StrategyTimingCategory.REVISIT_AFTER_REFRESH,
                    label="Revisit after data refresh",
                    guidance=(
                        "Return to stale, low-confidence, or weak-coverage targets after "
                        "the app refreshes structured evidence."
                    ),
                    importance=RecommendationImportance.MEDIUM,
                    source_recommendation_ids=tuple(
                        source_id
                        for item in watchlist_items
                        for source_id in item.source_recommendation_ids
                    )[:20],
                    evidence_strength=RecommendationEvidenceStrength.MISSING,
                    evidence_basis=(RecommendationEvidenceBasis.MISSING_DATA,),
                )
            )
    if goal is RecommendationGoalMode.MAXIMIZE_INTERNSHIP_COOP_ACCESS:
        timing.append(
            _missing_data_timing(
                StrategyTimingCategory.INTERNSHIP_COOP_CHECK,
                "Verify internship/co-op availability early",
                (
                    "Internship and co-op signals can be seasonal; verify eligibility "
                    "and availability before prioritizing."
                ),
                (company_items or region_items)[:3],
                importance=RecommendationImportance.HIGH,
            )
        )
    if goal is RecommendationGoalMode.MAXIMIZE_GEOGRAPHIC_FLEXIBILITY:
        timing.append(
            _heuristic_timing(
                StrategyTimingCategory.LOCATION_REQUIREMENTS_CHECK,
                "Verify location and hybrid requirements",
                "Geographic flexibility is proxy-based until direct location-policy data exists.",
                (company_items or region_items)[:3],
            )
        )
    if has_heuristic_role_targets:
        timing.append(
            _heuristic_timing(
                StrategyTimingCategory.VERIFY_CURRENT_POSTINGS,
                "Verify role-family fit",
                (
                    "Role-family guidance is heuristic unless future structured "
                    "role-family data is attached."
                ),
                (company_items or region_items)[:3],
            )
        )
    return tuple(_dedupe_timing(timing))


def _missing_data_timing(
    category: StrategyTimingCategory,
    label: str,
    guidance: str,
    source_items: Sequence[RecommendationRankingItem],
    *,
    importance: RecommendationImportance,
) -> StrategyTimingGuidance:
    return StrategyTimingGuidance(
        timing_category=category,
        label=label,
        guidance=guidance,
        importance=importance,
        source_recommendation_ids=tuple(_source_id(item) for item in source_items[:10]),
        evidence_strength=RecommendationEvidenceStrength.MISSING,
        evidence_basis=(RecommendationEvidenceBasis.MISSING_DATA,),
    )


def _heuristic_timing(
    category: StrategyTimingCategory,
    label: str,
    guidance: str,
    source_items: Sequence[RecommendationRankingItem],
) -> StrategyTimingGuidance:
    return StrategyTimingGuidance(
        timing_category=category,
        label=label,
        guidance=guidance,
        importance=RecommendationImportance.HIGH,
        source_recommendation_ids=tuple(_source_id(item) for item in source_items[:10]),
        evidence_strength=RecommendationEvidenceStrength.INFERRED,
        evidence_basis=(RecommendationEvidenceBasis.HEURISTIC_INFERENCE,),
        support=RecommendationClaimSupport.INFERRED,
    )


def _build_watchlist_items(
    items: tuple[RecommendationRankingItem, ...],
    limit: int,
) -> tuple[StrategyWatchlistItem, ...]:
    watchlist: list[StrategyWatchlistItem] = []
    for item in items:
        signal = _watchlist_signal(item)
        if signal is None:
            continue
        category, reason, support, strength, extra_basis = signal
        refs = _item_evidence_refs(item)
        watchlist.append(
            StrategyWatchlistItem(
                watchlist_category=category,
                target=item.target,
                reason=reason,
                upside=_watchlist_upside(item),
                what_to_verify=_watchlist_verification(item),
                revisit_after_refresh=category
                in {
                    StrategyWatchlistCategory.EVIDENCE_QUALITY,
                    StrategyWatchlistCategory.MISSING_DATA,
                },
                source_recommendation_ids=(_source_id(item),),
                evidence_strength=strength,
                evidence_basis=_basis_from_refs(refs, extra=extra_basis),
                support=support,
                evidence_refs=refs,
            )
        )
    return tuple(watchlist[:limit])


def _watchlist_signal(
    item: RecommendationRankingItem,
) -> tuple[
    StrategyWatchlistCategory,
    str,
    RecommendationClaimSupport,
    RecommendationEvidenceStrength,
    tuple[RecommendationEvidenceBasis, ...],
] | None:
    if _weak_evidence_quality(item):
        return (
            StrategyWatchlistCategory.EVIDENCE_QUALITY,
            "Ranked target has weak confidence, freshness, or coverage evidence.",
            RecommendationClaimSupport.DIRECT,
            RecommendationEvidenceStrength.WEAK,
            (),
        )
    if item.score_components_missing and item.final_score >= WATCHLIST_SCORE_THRESHOLD:
        return (
            StrategyWatchlistCategory.MISSING_DATA,
            "Ranked target has useful score but missing strategy-relevant components.",
            RecommendationClaimSupport.DIRECT,
            RecommendationEvidenceStrength.MISSING,
            (RecommendationEvidenceBasis.MISSING_DATA,),
        )
    if any(
        tradeoff.tradeoff_category is RecommendationTradeoffCategory.DATA_QUALITY
        for tradeoff in item.explanation.tradeoffs
    ) and item.final_score >= WATCHLIST_SCORE_THRESHOLD:
        return (
            StrategyWatchlistCategory.TRADEOFF_UPSIDE,
            "Ranked target has upside but data-quality tradeoffs remain.",
            RecommendationClaimSupport.DIRECT,
            RecommendationEvidenceStrength.WEAK,
            (),
        )
    if item.final_score >= WATCHLIST_SCORE_THRESHOLD and not item.explanation.provenance_refs:
        return (
            StrategyWatchlistCategory.EVIDENCE_QUALITY,
            "Ranked target lacks provenance references in its explanation.",
            RecommendationClaimSupport.DIRECT,
            RecommendationEvidenceStrength.MISSING,
            (RecommendationEvidenceBasis.MISSING_DATA,),
        )
    return None


def _watchlist_upside(item: RecommendationRankingItem) -> str:
    best_component = max(
        item.score_components_used,
        key=lambda component: component.weighted_value,
        default=None,
    )
    if best_component is None:
        return "The target remains ranked but has limited component detail."
    return f"Highest weighted component: {best_component.component.value}."


def _watchlist_verification(item: RecommendationRankingItem) -> str:
    if item.explanation.manual_verification:
        question = item.explanation.manual_verification[0].question
        if question.casefold().startswith("verify"):
            return question
        return f"Verify: {question}"
    if _weak_evidence_quality(item):
        return "Verify freshness, confidence, and coverage before acting."
    if item.score_components_missing:
        return "Verify whether missing structured inputs can be filled."
    return "Verify whether proxy assumptions still apply to the user's search."


def _manual_verification_entries(
    region_items: tuple[RecommendationRankingItem, ...],
    company_items: tuple[RecommendationRankingItem, ...],
    *,
    goal: RecommendationGoalMode,
    has_heuristic_role_targets: bool,
    has_company_rankings: bool,
) -> tuple[StrategyManualVerificationEntry, ...]:
    entries: list[StrategyManualVerificationEntry] = []
    for item in (*region_items, *company_items):
        for check in item.explanation.manual_verification:
            entries.append(
                StrategyManualVerificationEntry(
                    item=check,
                    source_recommendation_ids=(_source_id(item),),
                )
            )
    source_items = (company_items or region_items)[:3]
    if source_items:
        entries.append(
            _check_entry(
                ManualVerificationCategory.CURRENT_JOB_POSTINGS,
                "Verify current job postings",
                "Which current postings are relevant for each primary target?",
                source_items,
            )
        )
    if has_company_rankings:
        entries.append(
            _check_entry(
                ManualVerificationCategory.COMPANY_POLICY,
                "Verify company-specific hiring pages",
                "Do company hiring pages still show relevant entry-level or target-role paths?",
                company_items[:5],
            )
        )
    if goal in {
        RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS,
        RecommendationGoalMode.MAXIMIZE_INTERNSHIP_COOP_ACCESS,
    }:
        entries.append(
            _check_entry(
                ManualVerificationCategory.INTERNSHIP_COOP_ACCESS,
                "Verify internship/co-op eligibility",
                "Do internship or co-op paths match the user's timing and eligibility?",
                source_items,
            )
        )
    if goal is RecommendationGoalMode.MAXIMIZE_GEOGRAPHIC_FLEXIBILITY:
        entries.append(
            _heuristic_check_entry(
                ManualVerificationCategory.LOCATION_REQUIREMENTS,
                "Verify location/hybrid requirements",
                "Do the targets actually support the user's location constraints?",
                source_items,
            )
        )
    if has_heuristic_role_targets:
        entries.append(
            _heuristic_check_entry(
                ManualVerificationCategory.OTHER,
                "Verify role-family fit",
                "Do current postings match the heuristic role-family guidance?",
                source_items,
            )
        )
    return _dedupe_checks(entries)


def _check_entry(
    category: ManualVerificationCategory,
    label: str,
    question: str,
    source_items: Sequence[RecommendationRankingItem],
) -> StrategyManualVerificationEntry:
    return StrategyManualVerificationEntry(
        item=RecommendationManualVerificationItem(
            verification_category=category,
            label=label,
            question=question,
            importance=RecommendationImportance.HIGH,
            evidence_strength=RecommendationEvidenceStrength.MISSING,
            evidence_basis=(RecommendationEvidenceBasis.MISSING_DATA,),
        ),
        source_recommendation_ids=tuple(_source_id(item) for item in source_items[:10]),
    )


def _heuristic_check_entry(
    category: ManualVerificationCategory,
    label: str,
    question: str,
    source_items: Sequence[RecommendationRankingItem],
) -> StrategyManualVerificationEntry:
    return StrategyManualVerificationEntry(
        item=RecommendationManualVerificationItem(
            verification_category=category,
            label=label,
            question=question,
            importance=RecommendationImportance.HIGH,
            evidence_strength=RecommendationEvidenceStrength.INFERRED,
            evidence_basis=(RecommendationEvidenceBasis.HEURISTIC_INFERENCE,),
            support=RecommendationClaimSupport.INFERRED,
        ),
        source_recommendation_ids=tuple(_source_id(item) for item in source_items[:10]),
    )


def _evidence_warnings(
    region_items: tuple[RecommendationRankingItem, ...],
    company_items: tuple[RecommendationRankingItem, ...],
    *,
    include_company_gap: bool,
) -> tuple[StrategyEvidenceWarning, ...]:
    warnings: list[StrategyEvidenceWarning] = []
    for item in (*region_items, *company_items):
        source_id = _source_id(item)
        refs = _item_evidence_refs(item)
        if item.explanation.coverage_warnings or _weak_component(
            item,
            RecommendationScoreComponent.MARKET_COVERAGE,
        ):
            warnings.append(
                _warning(
                    StrategyWarningCategory.COVERAGE,
                    "Coverage warning attached to ranked recommendation",
                    "; ".join(item.explanation.coverage_warnings) or None,
                    source_id,
                    refs,
                    RecommendationEvidenceStrength.WEAK,
                )
            )
        if _weak_component(item, RecommendationScoreComponent.CONFIDENCE):
            warnings.append(
                _warning(
                    StrategyWarningCategory.CONFIDENCE,
                    "Low-confidence ranked recommendation",
                    None,
                    source_id,
                    refs,
                    RecommendationEvidenceStrength.WEAK,
                )
            )
        if _weak_component(item, RecommendationScoreComponent.FRESHNESS):
            warnings.append(
                _warning(
                    StrategyWarningCategory.FRESHNESS,
                    "Freshness risk attached to ranked recommendation",
                    None,
                    source_id,
                    refs,
                    RecommendationEvidenceStrength.WEAK,
                )
            )
        if not item.explanation.provenance_refs:
            warnings.append(
                StrategyEvidenceWarning(
                    warning_category=StrategyWarningCategory.PROVENANCE,
                    label="Provenance references are missing",
                    detail="The ranked explanation lacks app-owned source references.",
                    source_recommendation_ids=(source_id,),
                    evidence_strength=RecommendationEvidenceStrength.MISSING,
                    evidence_basis=(RecommendationEvidenceBasis.MISSING_DATA,),
                )
            )
        if item.score_components_proxy:
            warnings.append(
                StrategyEvidenceWarning(
                    warning_category=StrategyWarningCategory.PROXY,
                    label="Proxy components are used",
                    detail=_shorten(
                        ", ".join(
                            component.component.value
                            for component in item.score_components_proxy[:6]
                        )
                    ),
                    source_recommendation_ids=(source_id,),
                    evidence_strength=RecommendationEvidenceStrength.INFERRED,
                    evidence_basis=(RecommendationEvidenceBasis.HEURISTIC_INFERENCE,),
                    support=RecommendationClaimSupport.INFERRED,
                )
            )
        if item.score_components_missing:
            warnings.append(
                StrategyEvidenceWarning(
                    warning_category=StrategyWarningCategory.MISSING_DATA,
                    label="Ranking components are missing",
                    detail=_shorten(
                        ", ".join(
                            component.component.value
                            for component in item.score_components_missing[:6]
                        )
                    ),
                    source_recommendation_ids=(source_id,),
                    evidence_strength=RecommendationEvidenceStrength.MISSING,
                    evidence_basis=(RecommendationEvidenceBasis.MISSING_DATA,),
                )
            )
    if include_company_gap and region_items:
        warnings.append(
            StrategyEvidenceWarning(
                warning_category=StrategyWarningCategory.MANUAL_VERIFICATION,
                label="Company rankings were not supplied",
                detail=(
                    "Company targets and categories are limited because the strategy "
                    "input did not include company-ranked recommendations."
                ),
                source_recommendation_ids=tuple(_source_id(item) for item in region_items[:3]),
                evidence_strength=RecommendationEvidenceStrength.MISSING,
                evidence_basis=(RecommendationEvidenceBasis.MISSING_DATA,),
            )
        )
    return _dedupe_warnings(warnings)


def _warning(
    category: StrategyWarningCategory,
    label: str,
    detail: str | None,
    source_id: str,
    refs: tuple[RecommendationEvidenceReference, ...],
    strength: RecommendationEvidenceStrength,
) -> StrategyEvidenceWarning:
    return StrategyEvidenceWarning(
        warning_category=category,
        label=label,
        detail=_shorten(detail),
        source_recommendation_ids=(source_id,),
        evidence_strength=strength,
        evidence_basis=_basis_from_refs(refs),
        evidence_refs=refs,
    )


def _fallback_rationale(
    item: RecommendationRankingItem,
    goal: RecommendationGoalMode,
) -> str:
    if goal in {
        RecommendationGoalMode.MAXIMIZE_LOWER_COMPETITION,
        RecommendationGoalMode.MAXIMIZE_UNDERRATED_MARKETS,
    }:
        return "Fallback target selected for favorable lower-competition proxy."
    if any(
        tradeoff.tradeoff_category
        is RecommendationTradeoffCategory.LOWER_COMPETITION_VS_ROLE_VOLUME
        for tradeoff in item.explanation.tradeoffs
    ):
        return "Fallback target preserves lower-competition upside with role-volume caveats."
    return "Fallback target selected from ranked recommendations with useful tradeoffs."


def _source_references(
    items: Iterable[RecommendationRankingItem],
    prefix: str,
) -> tuple[StrategySourceRecommendation, ...]:
    return tuple(
        StrategySourceRecommendation(
            source_id=_source_id(item, prefix=prefix),
            rank=item.rank,
            target=item.target,
            final_score=item.final_score,
            warnings=item.warnings,
        )
        for item in items
    )


def _source_id(item: RecommendationRankingItem, prefix: str | None = None) -> str:
    resolved_prefix = prefix or item.target.target_type.value
    return f"{resolved_prefix}:{item.target.target_id}:rank:{item.rank}"


def _item_evidence_refs(
    item: RecommendationRankingItem,
) -> tuple[RecommendationEvidenceReference, ...]:
    refs = tuple(
        ref
        for component in item.score_components_used
        for ref in component.evidence_refs
    )
    if refs:
        return _dedupe_refs(refs)[:25]
    return _dedupe_refs(item.explanation.evidence_refs)[:25]


def _basis_from_refs(
    refs: tuple[RecommendationEvidenceReference, ...],
    *,
    extra: tuple[RecommendationEvidenceBasis, ...] = (),
) -> tuple[RecommendationEvidenceBasis, ...]:
    basis = tuple(dict.fromkeys((*[ref.basis for ref in refs], *extra)))
    return basis or extra or (RecommendationEvidenceBasis.MISSING_DATA,)


def _component_value(
    item: RecommendationRankingItem,
    component: RecommendationScoreComponent,
) -> float | None:
    for resolved in item.score_components_used:
        if resolved.component is component:
            return resolved.value
    return None


def _component_is_proxy(
    item: RecommendationRankingItem,
    component: RecommendationScoreComponent,
) -> bool:
    return any(
        resolved.component is component and resolved.is_proxy
        for resolved in item.score_components_used
    )


def _weak_component(
    item: RecommendationRankingItem,
    component: RecommendationScoreComponent,
) -> bool:
    value = _component_value(item, component)
    return value is not None and value <= WEAK_EVIDENCE_THRESHOLD


def _weak_evidence_quality(item: RecommendationRankingItem) -> bool:
    return any(
        _weak_component(item, component)
        for component in (
            RecommendationScoreComponent.MARKET_COVERAGE,
            RecommendationScoreComponent.CONFIDENCE,
            RecommendationScoreComponent.FRESHNESS,
        )
    )


def _proxy_weight(item: RecommendationRankingItem) -> float:
    return sum(component.weight for component in item.score_components_proxy)


def _dedupe_refs(
    refs: tuple[RecommendationEvidenceReference, ...],
) -> tuple[RecommendationEvidenceReference, ...]:
    deduped: dict[tuple[str, str | None, str | None], RecommendationEvidenceReference] = {}
    for ref in refs:
        deduped[(ref.basis.value, ref.reference_id, ref.label)] = ref
    return tuple(deduped[key] for key in sorted(deduped))


def _dedupe_checks(
    entries: list[StrategyManualVerificationEntry],
) -> tuple[StrategyManualVerificationEntry, ...]:
    deduped: dict[
        tuple[ManualVerificationCategory, str, str],
        StrategyManualVerificationEntry,
    ] = {}
    for entry in entries:
        key = (
            entry.item.verification_category,
            entry.item.label,
            entry.item.question,
        )
        if key not in deduped:
            deduped[key] = entry
        else:
            existing = deduped[key]
            source_ids = tuple(
                dict.fromkeys(
                    (*existing.source_recommendation_ids, *entry.source_recommendation_ids)
                )
            )
            deduped[key] = existing.model_copy(
                update={"source_recommendation_ids": source_ids[:20]}
            )
    return tuple(deduped.values())


def _dedupe_timing(
    timing: list[StrategyTimingGuidance],
) -> tuple[StrategyTimingGuidance, ...]:
    deduped: dict[tuple[StrategyTimingCategory, str], StrategyTimingGuidance] = {}
    for item in timing:
        deduped.setdefault((item.timing_category, item.label), item)
    return tuple(deduped.values())


def _dedupe_warnings(
    warnings: list[StrategyEvidenceWarning],
) -> tuple[StrategyEvidenceWarning, ...]:
    deduped: dict[
        tuple[StrategyWarningCategory, str, tuple[str, ...]],
        StrategyEvidenceWarning,
    ] = {}
    for warning in warnings:
        deduped.setdefault(
            (warning.warning_category, warning.label, warning.source_recommendation_ids),
            warning,
        )
    return tuple(deduped.values())[:50]


def _all_strategy_source_ids(plan: MarketStrategyPlan) -> Iterable[tuple[str, ...]]:
    for item in (
        *plan.primary_region_targets,
        *plan.secondary_region_targets,
        *plan.fallback_region_targets,
        *plan.company_targets,
        *plan.company_category_targets,
        *plan.role_family_targets,
        *plan.timing_guidance,
        *plan.watchlist_items,
        *plan.evidence_warnings,
    ):
        yield item.source_recommendation_ids
    for entry in plan.manual_verification_checklist.items:
        yield entry.source_recommendation_ids


def _validate_strategy_trace(
    *,
    evidence_basis: tuple[RecommendationEvidenceBasis, ...],
    evidence_strength: RecommendationEvidenceStrength,
    support: RecommendationClaimSupport,
    evidence_refs: tuple[RecommendationEvidenceReference, ...],
    source_recommendation_ids: tuple[str, ...],
) -> None:
    if not source_recommendation_ids:
        raise ValueError("strategy claims must reference ranked recommendations")
    basis = set(evidence_basis)
    if RecommendationEvidenceBasis.HEURISTIC_INFERENCE in basis:
        if support is not RecommendationClaimSupport.INFERRED:
            raise ValueError("heuristic strategy claims must be marked inferred")
        if evidence_strength is not RecommendationEvidenceStrength.INFERRED:
            raise ValueError("heuristic strategy claims must use inferred strength")
    elif support is RecommendationClaimSupport.INFERRED:
        raise ValueError("inferred strategy claims require heuristic_inference basis")
    structured_basis = {
        item
        for item in basis
        if item
        not in {
            RecommendationEvidenceBasis.HEURISTIC_INFERENCE,
            RecommendationEvidenceBasis.USER_PREFERENCE,
            RecommendationEvidenceBasis.MISSING_DATA,
        }
    }
    if structured_basis and not evidence_refs:
        raise ValueError("structured strategy claims require evidence refs")
    for ref in evidence_refs:
        if ref.basis not in basis:
            raise ValueError("strategy evidence_refs basis must be declared")


def _slug(label: str) -> str:
    return (
        label.casefold()
        .replace("/", " ")
        .replace("-", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace(" ", "_")
    )


def _shorten(value: str | None, *, limit: int = 512) -> str | None:
    if value is None or len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."
