"""Deterministic recommendation ranking over structured recommendation inputs.

Layer 14C consumes Layer 14B goal-mode profiles and assembly outputs. It does
not own market facts, scoring truth, freshness rules, confidence rules,
provenance rules, API routes, frontend behavior, strategy generation, or AI
summaries.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.recommendations.assembly import (
    assemble_company_recommendation_explanation,
    assemble_region_recommendation_explanation,
)
from backend.recommendations.goal_modes import (
    GoalModePenaltyComponent,
    GoalModeWeightProfile,
    RecommendationScoreComponent,
    goal_mode_weight_profile,
)
from backend.recommendations.models import (
    ManualVerificationCategory,
    RecommendationClaimSupport,
    RecommendationEvidenceBasis,
    RecommendationEvidenceReference,
    RecommendationEvidenceStrength,
    RecommendationExplanation,
    RecommendationGoalMode,
    RecommendationImportance,
    RecommendationManualVerificationItem,
    RecommendationReason,
    RecommendationReasonCategory,
    RecommendationTarget,
    RecommendationTargetType,
    RecommendationWeakness,
    RecommendationWeaknessCategory,
)
from backend.recommendations.tradeoffs import (
    TradeoffSignal,
    TradeoffSignalStatus,
    generate_controlled_tradeoffs,
)

RANKING_PROFILE_VERSION = "layer14c_deterministic_ranking_v1"
TIE_BREAKER_DESCRIPTION = (
    "Sort by final_score descending, then display label, then stable target id."
)


class ScoreComponentStatus(StrEnum):
    USED = "used"
    MISSING = "missing"
    PROXY = "proxy"


class PenaltyApplicationMode(StrEnum):
    HIGH_VALUE = "high_value"
    LOW_VALUE = "low_value"
    ALWAYS = "always"


class ResolvedScoreComponent(BaseModel):
    """A bounded component resolved from existing structured app output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    component: RecommendationScoreComponent
    status: ScoreComponentStatus
    value: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )
    source_fields: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    is_proxy: bool = False
    inferred: bool = False
    warning: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("source_fields")
    @classmethod
    def _source_fields_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(item.strip() for item in value if item.strip())

    @model_validator(mode="after")
    def _component_is_traceable(self) -> ResolvedScoreComponent:
        if self.status is ScoreComponentStatus.MISSING:
            if self.value is not None:
                raise ValueError("missing score components cannot carry values")
            return self
        if self.value is None:
            raise ValueError("used score components must carry bounded values")
        if self.status is ScoreComponentStatus.PROXY and not self.is_proxy:
            raise ValueError("proxy score components must be marked proxy")
        if RecommendationEvidenceBasis.HEURISTIC_INFERENCE in self.evidence_basis:
            if not self.is_proxy or not self.inferred:
                raise ValueError("heuristic score components must be proxy/inferred")
        structured_basis = [
            basis
            for basis in self.evidence_basis
            if basis
            not in {
                RecommendationEvidenceBasis.HEURISTIC_INFERENCE,
                RecommendationEvidenceBasis.MISSING_DATA,
                RecommendationEvidenceBasis.USER_PREFERENCE,
            }
        ]
        if structured_basis and not self.evidence_refs:
            raise ValueError("structured score components require evidence references")
        return self


class WeightedScoreComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    component: RecommendationScoreComponent
    value: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    weighted_value: float = Field(ge=0.0, le=1.0)
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )
    source_fields: tuple[str, ...] = Field(default_factory=tuple)
    is_proxy: bool = False
    inferred: bool = False
    warning: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def _weighted_value_matches_inputs(self) -> WeightedScoreComponent:
        expected = self.value * self.weight
        if not math.isclose(self.weighted_value, expected, abs_tol=1e-9):
            raise ValueError("weighted score component does not match value * weight")
        if RecommendationEvidenceBasis.HEURISTIC_INFERENCE in self.evidence_basis:
            if not self.is_proxy or not self.inferred:
                raise ValueError("heuristic weighted components must be proxy/inferred")
        structured_basis = [
            basis
            for basis in self.evidence_basis
            if basis
            not in {
                RecommendationEvidenceBasis.HEURISTIC_INFERENCE,
                RecommendationEvidenceBasis.MISSING_DATA,
                RecommendationEvidenceBasis.USER_PREFERENCE,
            }
        ]
        if structured_basis and not self.evidence_refs:
            raise ValueError("structured weighted components require evidence refs")
        return self


class MissingScoreComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    component: RecommendationScoreComponent
    weight: float = Field(ge=0.0, le=1.0)
    unavailable_behavior: str = Field(min_length=1, max_length=512)
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    warning: str | None = Field(default=None, min_length=1, max_length=256)


class AppliedRankingPenalty(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    component: RecommendationScoreComponent
    value: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    penalty_value: float = Field(ge=0.0, le=1.0)
    application_mode: PenaltyApplicationMode
    explanation: str = Field(min_length=1, max_length=256)
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )
    is_proxy: bool = False
    inferred: bool = False

    @model_validator(mode="after")
    def _penalty_is_traceable(self) -> AppliedRankingPenalty:
        if RecommendationEvidenceBasis.HEURISTIC_INFERENCE in self.evidence_basis:
            if not self.is_proxy or not self.inferred:
                raise ValueError("heuristic penalties must be proxy/inferred")
        structured_basis = [
            basis
            for basis in self.evidence_basis
            if basis
            not in {
                RecommendationEvidenceBasis.HEURISTIC_INFERENCE,
                RecommendationEvidenceBasis.MISSING_DATA,
                RecommendationEvidenceBasis.USER_PREFERENCE,
            }
        ]
        if structured_basis and not self.evidence_refs:
            raise ValueError("structured penalties require evidence refs")
        return self


class RecommendationRankingItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int = Field(ge=1)
    target: RecommendationTarget
    goal_mode: RecommendationGoalMode
    final_score: float = Field(ge=0.0, le=1.0)
    normalized_score: float = Field(ge=0.0, le=1.0)
    score_components_used: tuple[WeightedScoreComponent, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )
    score_components_missing: tuple[MissingScoreComponent, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )
    score_components_proxy: tuple[WeightedScoreComponent, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )
    penalties_applied: tuple[AppliedRankingPenalty, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )
    confidence_contribution: float | None = Field(default=None, ge=0.0, le=1.0)
    freshness_contribution: float | None = Field(default=None, ge=0.0, le=1.0)
    coverage_contribution: float | None = Field(default=None, ge=0.0, le=1.0)
    explanation: RecommendationExplanation
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=50)

    @field_validator("warnings")
    @classmethod
    def _warnings_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(item.strip() for item in value if item.strip())

    @model_validator(mode="after")
    def _ranking_item_is_coherent(self) -> RecommendationRankingItem:
        if not math.isclose(self.final_score, self.normalized_score, abs_tol=1e-9):
            raise ValueError("normalized score must match bounded final score")
        if self.explanation.target != self.target:
            raise ValueError("ranking explanation target must match ranked target")
        if self.explanation.goal_mode != self.goal_mode:
            raise ValueError("ranking explanation goal mode must match ranked goal")
        proxy_components = tuple(
            component for component in self.score_components_used if component.is_proxy
        )
        if self.score_components_proxy != proxy_components:
            raise ValueError("proxy component list must match used proxy components")
        return self


class RecommendationRankingResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    goal_mode: RecommendationGoalMode
    profile: GoalModeWeightProfile
    profile_version: str = RANKING_PROFILE_VERSION
    tie_breaker: str = TIE_BREAKER_DESCRIPTION
    ranked_recommendations: tuple[RecommendationRankingItem, ...]

    @model_validator(mode="after")
    def _result_is_coherent(self) -> RecommendationRankingResult:
        if self.profile.goal_mode is not self.goal_mode:
            raise ValueError("ranking profile goal mode must match result goal mode")
        ranks = [item.rank for item in self.ranked_recommendations]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("ranking items must have sequential ranks")
        if any(item.goal_mode is not self.goal_mode for item in self.ranked_recommendations):
            raise ValueError("ranking items must share result goal mode")
        return self


def rank_region_recommendations(
    region_payloads: Iterable[Any],
    *,
    goal_mode: RecommendationGoalMode | str,
    source_summaries: Mapping[str, Any] | None = None,
) -> RecommendationRankingResult:
    """Rank region-like payloads deterministically for a selected goal mode."""

    goal = RecommendationGoalMode(goal_mode)
    profile = goal_mode_weight_profile(goal)
    items: list[RecommendationRankingItem] = []
    for payload in region_payloads:
        if not _allows_ranking_influence(payload):
            continue
        target_id = _target_id(payload, RecommendationTargetType.REGION)
        source_summary = (source_summaries or {}).get(target_id)
        explanation = assemble_region_recommendation_explanation(
            payload,
            goal_mode=goal,
            source_summary=source_summary,
        )
        resolved = resolve_region_score_components(payload, explanation=explanation)
        items.append(
            _rank_one(
                explanation=explanation,
                resolved_components=resolved,
                profile=profile,
            )
        )
    return _rank_result(items, profile=profile)


def rank_company_recommendations(
    company_payloads: Iterable[Any],
    *,
    goal_mode: RecommendationGoalMode | str,
    source_summaries: Mapping[str, Any] | None = None,
) -> RecommendationRankingResult:
    """Rank company-like payloads deterministically for a selected goal mode."""

    goal = RecommendationGoalMode(goal_mode)
    profile = goal_mode_weight_profile(goal)
    items: list[RecommendationRankingItem] = []
    for payload in company_payloads:
        if not _allows_ranking_influence(payload):
            continue
        target_id = _target_id(payload, RecommendationTargetType.COMPANY)
        source_summary = (source_summaries or {}).get(target_id)
        explanation = assemble_company_recommendation_explanation(
            payload,
            goal_mode=goal,
            source_summary=source_summary,
        )
        resolved = resolve_company_score_components(payload, explanation=explanation)
        items.append(
            _rank_one(
                explanation=explanation,
                resolved_components=resolved,
                profile=profile,
            )
        )
    return _rank_result(items, profile=profile)


def resolve_region_score_components(
    region_payload: Any,
    *,
    explanation: RecommendationExplanation,
) -> tuple[ResolvedScoreComponent, ...]:
    """Resolve canonical ranking components from a region-like read model."""

    body = _field(region_payload, "region") or region_payload
    target = explanation.target
    refs = _ReferenceIndex(explanation)
    scores = _field(body, "scores")
    summary = _field(body, "summary")
    entry = _field(body, "entry_level_summary")

    components: dict[RecommendationScoreComponent, ResolvedScoreComponent] = {}
    components[RecommendationScoreComponent.ENTRY_LEVEL_ACCESS] = _value_component(
        RecommendationScoreComponent.ENTRY_LEVEL_ACCESS,
        _first_number(
            _field(scores, "early_career_accessibility_score"),
            _field(entry, "average_entry_level_access_score"),
        ),
        basis=(RecommendationEvidenceBasis.STRUCTURED_SCORE,),
        refs=refs.for_basis(
            RecommendationEvidenceBasis.STRUCTURED_SCORE,
            fallback=_fallback_ref(
                target,
                RecommendationEvidenceBasis.STRUCTURED_SCORE,
                "Region entry-level score fields",
                "region_entry_level_summary",
            ),
        ),
        source_fields=(
            "region.scores.early_career_accessibility_score",
            "region.entry_level_summary.average_entry_level_access_score",
        ),
        missing_warning="Entry-level access score fields are unavailable.",
    )
    internship_count = _sum_numbers(
        _field(entry, "internship_count_total"),
        _field(entry, "coop_count_total"),
    )
    components[RecommendationScoreComponent.INTERNSHIP_OR_COOP_ACCESS] = _value_component(
        RecommendationScoreComponent.INTERNSHIP_OR_COOP_ACCESS,
        _count_value(internship_count, divisor=10.0),
        basis=(RecommendationEvidenceBasis.STRUCTURED_SCORE,),
        refs=refs.for_basis(
            RecommendationEvidenceBasis.STRUCTURED_SCORE,
            fallback=_fallback_ref(
                target,
                RecommendationEvidenceBasis.STRUCTURED_SCORE,
                "Region internship/co-op summary fields",
                "region_entry_level_summary",
            ),
        ),
        source_fields=(
            "region.entry_level_summary.internship_count_total",
            "region.entry_level_summary.coop_count_total",
        ),
        missing_warning="Internship/co-op count fields are unavailable.",
    )
    components[RecommendationScoreComponent.PRESTIGE_DENSITY] = _region_prestige_component(
        body,
        scores=scores,
        summary=summary,
        refs=refs,
        target=target,
    )
    components[RecommendationScoreComponent.AI_CLOUD_CONCENTRATION] = (
        _region_ai_cloud_component(body, refs=refs, target=target)
    )
    components[RecommendationScoreComponent.COMPANY_DENSITY] = _value_component(
        RecommendationScoreComponent.COMPANY_DENSITY,
        _count_value(_field(summary, "present_company_count"), divisor=20.0),
        basis=(RecommendationEvidenceBasis.REGION_METADATA,),
        refs=refs.for_basis(
            RecommendationEvidenceBasis.REGION_METADATA,
            fallback=_fallback_ref(
                target,
                RecommendationEvidenceBasis.REGION_METADATA,
                "Region company-density summary fields",
                "region_summary",
            ),
        ),
        source_fields=("region.summary.present_company_count",),
        missing_warning="Company-density summary fields are unavailable.",
    )
    components[RecommendationScoreComponent.ROLE_DIVERSITY] = _role_diversity_component(
        body,
        refs=refs,
        target=target,
        metadata_basis=RecommendationEvidenceBasis.REGION_METADATA,
    )
    components[RecommendationScoreComponent.GEOGRAPHIC_FLEXIBILITY] = _missing_component(
        RecommendationScoreComponent.GEOGRAPHIC_FLEXIBILITY,
        "Region payloads do not contain location-flexibility policy or region-breadth signals.",
    )
    components[RecommendationScoreComponent.MARKET_COVERAGE] = _coverage_component(
        _field(body, "coverage"),
        refs=refs,
        target=target,
    )
    components[RecommendationScoreComponent.CONFIDENCE] = _confidence_component(
        body,
        refs=refs,
        explanation=explanation,
    )
    components[RecommendationScoreComponent.FRESHNESS] = _freshness_component(
        region_payload,
        refs=refs,
        explanation=explanation,
    )
    components[RecommendationScoreComponent.LOWER_COMPETITION_PROXY] = (
        _lower_competition_component(
            components,
            "Lower competition is inferred from prestige/company-density proxies.",
        )
    )
    return _ordered_components(components)


def resolve_company_score_components(
    company_payload: Any,
    *,
    explanation: RecommendationExplanation,
) -> tuple[ResolvedScoreComponent, ...]:
    """Resolve canonical ranking components from a company-like read model."""

    body = _field(company_payload, "company") or company_payload
    target = explanation.target
    refs = _ReferenceIndex(explanation)
    entry_regions = tuple(_field(body, "entry_level_regions") or ())
    present_regions = tuple(_field(body, "regions_present") or ())
    matched_region_ids = tuple(_field(body, "matched_region_ids") or ())

    components: dict[RecommendationScoreComponent, ResolvedScoreComponent] = {}
    components[RecommendationScoreComponent.ENTRY_LEVEL_ACCESS] = (
        _company_entry_level_component(body, entry_regions, refs=refs, target=target)
    )
    components[RecommendationScoreComponent.INTERNSHIP_OR_COOP_ACCESS] = (
        _company_internship_component(entry_regions, refs=refs, target=target)
    )
    components[RecommendationScoreComponent.PRESTIGE_DENSITY] = _company_prestige_component(
        body,
        refs=refs,
        target=target,
    )
    components[RecommendationScoreComponent.AI_CLOUD_CONCENTRATION] = (
        _company_ai_cloud_component(body, refs=refs, target=target)
    )
    region_count = len(
        {
            *_region_ids_from_rows(present_regions),
            *_region_ids_from_rows(tuple(_field(body, "regions_hiring") or ())),
            *_region_ids_from_rows(entry_regions),
            *(_string_or_none(item) for item in matched_region_ids),
        }
        - {None}
    )
    components[RecommendationScoreComponent.COMPANY_DENSITY] = _value_component(
        RecommendationScoreComponent.COMPANY_DENSITY,
        _count_value(region_count if region_count else None, divisor=5.0),
        basis=(RecommendationEvidenceBasis.COMPANY_METADATA,),
        refs=refs.for_basis(
            RecommendationEvidenceBasis.COMPANY_METADATA,
            fallback=_fallback_ref(
                target,
                RecommendationEvidenceBasis.COMPANY_METADATA,
                "Company region-breadth metadata",
                "company_region_summary",
            ),
        ),
        source_fields=(
            "company.regions_present",
            "company.regions_hiring",
            "company.entry_level_regions",
            "matched_region_ids",
        ),
        missing_warning="Company region-breadth fields are unavailable.",
    )
    components[RecommendationScoreComponent.ROLE_DIVERSITY] = _role_diversity_component(
        body,
        refs=refs,
        target=target,
        metadata_basis=RecommendationEvidenceBasis.COMPANY_METADATA,
    )
    components[RecommendationScoreComponent.GEOGRAPHIC_FLEXIBILITY] = _value_component(
        RecommendationScoreComponent.GEOGRAPHIC_FLEXIBILITY,
        _count_value(region_count if region_count else None, divisor=5.0),
        basis=(RecommendationEvidenceBasis.COMPANY_METADATA,),
        refs=refs.for_basis(
            RecommendationEvidenceBasis.COMPANY_METADATA,
            fallback=_fallback_ref(
                target,
                RecommendationEvidenceBasis.COMPANY_METADATA,
                "Company region-breadth metadata",
                "company_region_summary",
            ),
        ),
        source_fields=("company region breadth",),
        is_proxy=True,
        warning="Geographic flexibility is inferred from region breadth, not policy.",
        missing_warning="Company region-breadth fields are unavailable.",
    )
    components[RecommendationScoreComponent.MARKET_COVERAGE] = _coverage_component(
        _average_coverage(_company_coverages(body)),
        refs=refs,
        target=target,
    )
    components[RecommendationScoreComponent.CONFIDENCE] = _confidence_component(
        body,
        refs=refs,
        explanation=explanation,
    )
    components[RecommendationScoreComponent.FRESHNESS] = _freshness_component(
        company_payload,
        refs=refs,
        explanation=explanation,
    )
    components[RecommendationScoreComponent.LOWER_COMPETITION_PROXY] = (
        _lower_competition_component(
            components,
            "Lower competition is inferred from prestige/company-density proxies.",
        )
    )
    return _ordered_components(components)


def _rank_one(
    *,
    explanation: RecommendationExplanation,
    resolved_components: Sequence[ResolvedScoreComponent],
    profile: GoalModeWeightProfile,
) -> RecommendationRankingItem:
    component_by_name = {component.component: component for component in resolved_components}
    used: list[WeightedScoreComponent] = []
    missing: list[MissingScoreComponent] = []
    warnings: list[str] = list(profile.warnings)

    score = 0.0
    for profile_component in profile.weighted_components:
        resolved = component_by_name.get(profile_component.component)
        if resolved is None or resolved.status is ScoreComponentStatus.MISSING:
            missing.append(
                MissingScoreComponent(
                    component=profile_component.component,
                    weight=profile_component.weight,
                    unavailable_behavior=profile_component.unavailable_behavior,
                    evidence_basis=(
                        resolved.evidence_basis
                        if resolved is not None
                        else profile_component.evidence_basis
                    ),
                    warning=profile_component.warning,
                )
            )
            warnings.append(
                f"Missing component {profile_component.component.value}: "
                f"{profile_component.unavailable_behavior}"
            )
            continue
        is_proxy = resolved.is_proxy or profile_component.is_proxy
        inferred = resolved.inferred or profile_component.requires_heuristic_inference
        weighted_value = resolved.value * profile_component.weight
        weighted = WeightedScoreComponent(
            component=resolved.component,
            value=resolved.value,
            weight=profile_component.weight,
            weighted_value=weighted_value,
            evidence_basis=resolved.evidence_basis,
            evidence_refs=resolved.evidence_refs,
            source_fields=resolved.source_fields,
            is_proxy=is_proxy,
            inferred=inferred,
            warning=resolved.warning or profile_component.warning,
        )
        used.append(weighted)
        score += weighted_value
        if weighted.warning:
            warnings.append(weighted.warning)

    penalties = _apply_penalties(profile.penalty_components, component_by_name)
    score -= sum(penalty.penalty_value for penalty in penalties)
    final_score = round(max(0.0, min(1.0, score)), 6)
    proxy_components = tuple(component for component in used if component.is_proxy)
    warnings.extend(_quality_warnings(used, missing, proxy_components, penalties))
    bound_explanation = _bind_ranking_explanation(
        explanation,
        profile=profile,
        used=tuple(used),
        missing=tuple(missing),
        proxy_components=proxy_components,
        penalties=tuple(penalties),
        final_score=final_score,
    )
    return RecommendationRankingItem(
        rank=1,
        target=explanation.target,
        goal_mode=profile.goal_mode,
        final_score=final_score,
        normalized_score=final_score,
        score_components_used=tuple(used),
        score_components_missing=tuple(missing),
        score_components_proxy=proxy_components,
        penalties_applied=tuple(penalties),
        confidence_contribution=_weighted_value_for(
            used,
            RecommendationScoreComponent.CONFIDENCE,
        ),
        freshness_contribution=_weighted_value_for(
            used,
            RecommendationScoreComponent.FRESHNESS,
        ),
        coverage_contribution=_weighted_value_for(
            used,
            RecommendationScoreComponent.MARKET_COVERAGE,
        ),
        explanation=bound_explanation,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _rank_result(
    items: list[RecommendationRankingItem],
    *,
    profile: GoalModeWeightProfile,
) -> RecommendationRankingResult:
    sorted_items = sorted(
        items,
        key=lambda item: (
            -item.final_score,
            (item.target.display_label or item.target.target_id).casefold(),
            item.target.target_id,
        ),
    )
    ranked = tuple(
        item.model_copy(update={"rank": index})
        for index, item in enumerate(sorted_items, start=1)
    )
    return RecommendationRankingResult(
        goal_mode=profile.goal_mode,
        profile=profile,
        ranked_recommendations=ranked,
    )


def _allows_ranking_influence(payload: Any) -> bool:
    """Reject explicit non-ranking payloads while preserving legacy output reads."""

    allowed = _field(payload, "ranking_influence_allowed")
    if allowed is False:
        return False
    decision = _field(payload, "ranking_influence_decision")
    decision_value = getattr(decision, "value", decision)
    if decision_value == "denied":
        return False
    return True


def _apply_penalties(
    penalty_components: Sequence[GoalModePenaltyComponent],
    resolved_components: Mapping[RecommendationScoreComponent, ResolvedScoreComponent],
) -> tuple[AppliedRankingPenalty, ...]:
    penalties: list[AppliedRankingPenalty] = []
    for penalty in penalty_components:
        resolved = resolved_components.get(penalty.component)
        if resolved is None or resolved.status is ScoreComponentStatus.MISSING:
            continue
        mode = _penalty_mode(penalty.component)
        factor = _penalty_factor(resolved.value, mode)
        penalty_value = round(max(0.0, min(1.0, factor * penalty.weight)), 6)
        if penalty_value <= 0:
            continue
        penalties.append(
            AppliedRankingPenalty(
                component=penalty.component,
                value=resolved.value,
                weight=penalty.weight,
                penalty_value=penalty_value,
                application_mode=mode,
                explanation=penalty.explanation,
                evidence_basis=_penalty_evidence_basis(resolved, penalty),
                evidence_refs=resolved.evidence_refs,
                is_proxy=resolved.is_proxy or penalty.is_proxy,
                inferred=resolved.inferred or penalty.requires_heuristic_inference,
            )
        )
    return tuple(penalties)


def _penalty_evidence_basis(
    resolved: ResolvedScoreComponent,
    penalty: GoalModePenaltyComponent,
) -> tuple[RecommendationEvidenceBasis, ...]:
    basis = list(resolved.evidence_basis)
    if penalty.requires_heuristic_inference and (
        RecommendationEvidenceBasis.HEURISTIC_INFERENCE not in basis
    ):
        basis.append(RecommendationEvidenceBasis.HEURISTIC_INFERENCE)
    return tuple(dict.fromkeys(basis))


def _penalty_mode(component: RecommendationScoreComponent) -> PenaltyApplicationMode:
    if component is RecommendationScoreComponent.GEOGRAPHIC_FLEXIBILITY:
        return PenaltyApplicationMode.ALWAYS
    if component in {
        RecommendationScoreComponent.ENTRY_LEVEL_ACCESS,
        RecommendationScoreComponent.COMPANY_DENSITY,
        RecommendationScoreComponent.ROLE_DIVERSITY,
        RecommendationScoreComponent.MARKET_COVERAGE,
        RecommendationScoreComponent.CONFIDENCE,
        RecommendationScoreComponent.FRESHNESS,
    }:
        return PenaltyApplicationMode.LOW_VALUE
    return PenaltyApplicationMode.HIGH_VALUE


def _penalty_factor(value: float, mode: PenaltyApplicationMode) -> float:
    if mode is PenaltyApplicationMode.ALWAYS:
        return 1.0
    if mode is PenaltyApplicationMode.LOW_VALUE:
        return 1.0 - value
    return value


def _bind_ranking_explanation(
    explanation: RecommendationExplanation,
    *,
    profile: GoalModeWeightProfile,
    used: tuple[WeightedScoreComponent, ...],
    missing: tuple[MissingScoreComponent, ...],
    proxy_components: tuple[WeightedScoreComponent, ...],
    penalties: tuple[AppliedRankingPenalty, ...],
    final_score: float,
) -> RecommendationExplanation:
    ranking_reason = _ranking_reason(profile, used, final_score)
    missing_weaknesses = tuple(
        RecommendationWeakness(
            weakness_category=RecommendationWeaknessCategory.MISSING_DATA,
            label=f"Ranking component is missing: {component.component.value}",
            detail=component.unavailable_behavior,
            evidence_strength=RecommendationEvidenceStrength.MISSING,
            evidence_basis=(RecommendationEvidenceBasis.MISSING_DATA,),
        )
        for component in missing
    )
    proxy_weaknesses = _proxy_weaknesses(proxy_components)
    penalty_weaknesses = _penalty_weaknesses(penalties)
    manual_verification = _ranking_manual_verification(
        missing,
        proxy_components,
        explanation.manual_verification,
    )
    tradeoff_signals = _tradeoff_signals(used, missing)
    generated_tradeoffs = generate_controlled_tradeoffs(
        tradeoff_signals,
        explanation=explanation,
        final_score=final_score,
    )
    return RecommendationExplanation(
        target=explanation.target,
        goal_mode=profile.goal_mode,
        headline=explanation.headline,
        fit_reasons=(
            *((ranking_reason,) if ranking_reason is not None else ()),
            *explanation.fit_reasons,
        )[:30],
        data_strengths=explanation.data_strengths,
        tradeoffs=(*explanation.tradeoffs, *generated_tradeoffs)[:30],
        weaknesses=(
            *explanation.weaknesses,
            *missing_weaknesses,
            *proxy_weaknesses,
            *penalty_weaknesses,
        )[:30],
        manual_verification=(*explanation.manual_verification, *manual_verification)[:30],
        evidence_refs=explanation.evidence_refs,
        confidence_summary=explanation.confidence_summary,
        freshness_summary=explanation.freshness_summary,
        provenance_refs=explanation.provenance_refs,
        coverage_warnings=explanation.coverage_warnings,
        data_quality_warnings=explanation.data_quality_warnings,
    )


def _ranking_reason(
    profile: GoalModeWeightProfile,
    used: tuple[WeightedScoreComponent, ...],
    final_score: float,
) -> RecommendationReason | None:
    refs: list[RecommendationEvidenceReference] = []
    for component in used:
        refs.extend(
            ref
            for ref in component.evidence_refs
            if ref.basis is not RecommendationEvidenceBasis.HEURISTIC_INFERENCE
        )
    refs_tuple = _dedupe_refs(tuple(refs))[:25]
    if not refs_tuple:
        if not used:
            return None
        return RecommendationReason(
            reason_category=RecommendationReasonCategory.GOAL_ALIGNMENT,
            label=f"Ranked by {profile.label}",
            detail=(
                "Only proxy or missing-data context was available for this ranking; "
                f"bounded score is {final_score:g}."
            ),
            evidence_strength=RecommendationEvidenceStrength.INFERRED,
            evidence_basis=(RecommendationEvidenceBasis.HEURISTIC_INFERENCE,),
            support=RecommendationClaimSupport.INFERRED,
        )
    basis = tuple(dict.fromkeys(ref.basis for ref in refs_tuple))
    component_names = ", ".join(component.component.value for component in used[:6])
    return RecommendationReason(
        reason_category=RecommendationReasonCategory.GOAL_ALIGNMENT,
        label=f"Ranked by {profile.label}",
        detail=f"Used weighted components: {component_names}. Bounded score is {final_score:g}.",
        evidence_strength=RecommendationEvidenceStrength.MODERATE,
        evidence_basis=basis,
        evidence_refs=refs_tuple,
    )


def _proxy_weaknesses(
    proxy_components: tuple[WeightedScoreComponent, ...],
) -> tuple[RecommendationWeakness, ...]:
    if not proxy_components:
        return ()
    labels = ", ".join(component.component.value for component in proxy_components[:6])
    return (
        RecommendationWeakness(
            weakness_category=RecommendationWeaknessCategory.HEURISTIC_LIMITATION,
            label="Ranking uses proxy components",
            detail=f"Proxy components used: {labels}.",
            evidence_strength=RecommendationEvidenceStrength.INFERRED,
            evidence_basis=(RecommendationEvidenceBasis.HEURISTIC_INFERENCE,),
            support=RecommendationClaimSupport.INFERRED,
        ),
    )


def _penalty_weaknesses(
    penalties: tuple[AppliedRankingPenalty, ...],
) -> tuple[RecommendationWeakness, ...]:
    weaknesses: list[RecommendationWeakness] = []
    for penalty in penalties:
        support = (
            RecommendationClaimSupport.INFERRED
            if RecommendationEvidenceBasis.HEURISTIC_INFERENCE in penalty.evidence_basis
            else RecommendationClaimSupport.DIRECT
        )
        strength = (
            RecommendationEvidenceStrength.INFERRED
            if support is RecommendationClaimSupport.INFERRED
            else RecommendationEvidenceStrength.MODERATE
        )
        weaknesses.append(
            RecommendationWeakness(
                weakness_category=RecommendationWeaknessCategory.NARROW_EVIDENCE,
                label=f"Ranking penalty applied: {penalty.component.value}",
                detail=penalty.explanation,
                evidence_strength=strength,
                evidence_basis=penalty.evidence_basis,
                support=support,
                evidence_refs=penalty.evidence_refs,
            )
        )
    return tuple(weaknesses)


def _ranking_manual_verification(
    missing: tuple[MissingScoreComponent, ...],
    proxy_components: tuple[WeightedScoreComponent, ...],
    existing: tuple[RecommendationManualVerificationItem, ...],
) -> tuple[RecommendationManualVerificationItem, ...]:
    items: list[RecommendationManualVerificationItem] = []
    if missing:
        names = ", ".join(component.component.value for component in missing[:6])
        items.append(
            RecommendationManualVerificationItem(
                verification_category=ManualVerificationCategory.SOURCE_CONFIRMATION,
                label="Verify missing ranking inputs",
                question=f"Can app-owned data fill these missing ranking components: {names}?",
                importance=RecommendationImportance.HIGH,
                evidence_strength=RecommendationEvidenceStrength.MISSING,
                evidence_basis=(RecommendationEvidenceBasis.MISSING_DATA,),
            )
        )
    if proxy_components:
        category = (
            ManualVerificationCategory.LOCATION_REQUIREMENTS
            if any(
                component.component
                is RecommendationScoreComponent.GEOGRAPHIC_FLEXIBILITY
                for component in proxy_components
            )
            else ManualVerificationCategory.OTHER
        )
        items.append(
            RecommendationManualVerificationItem(
                verification_category=category,
                label="Verify proxy ranking assumptions",
                question="Do the proxy components still hold for the user's actual search?",
                rationale="Proxy components are inspectable but not direct market facts.",
                importance=RecommendationImportance.HIGH,
                evidence_strength=RecommendationEvidenceStrength.INFERRED,
                evidence_basis=(RecommendationEvidenceBasis.HEURISTIC_INFERENCE,),
                support=RecommendationClaimSupport.INFERRED,
            )
        )
    existing_labels = {item.label for item in existing}
    return tuple(item for item in items if item.label not in existing_labels)


def _tradeoff_signals(
    used: tuple[WeightedScoreComponent, ...],
    missing: tuple[MissingScoreComponent, ...],
) -> dict[RecommendationScoreComponent, TradeoffSignal]:
    signals: dict[RecommendationScoreComponent, TradeoffSignal] = {}
    for component in used:
        signals[component.component] = TradeoffSignal(
            component=component.component,
            value=component.value,
            status=(
                TradeoffSignalStatus.PROXY
                if component.is_proxy
                else TradeoffSignalStatus.USED
            ),
            evidence_basis=component.evidence_basis,
            evidence_refs=component.evidence_refs,
            is_proxy=component.is_proxy,
            inferred=component.inferred,
        )
    for component in missing:
        signals.setdefault(
            component.component,
            TradeoffSignal(
                component=component.component,
                value=None,
                status=TradeoffSignalStatus.MISSING,
                evidence_basis=(RecommendationEvidenceBasis.MISSING_DATA,),
            ),
        )
    return signals


def _quality_warnings(
    used: list[WeightedScoreComponent],
    missing: list[MissingScoreComponent],
    proxy_components: tuple[WeightedScoreComponent, ...],
    penalties: tuple[AppliedRankingPenalty, ...],
) -> tuple[str, ...]:
    warnings: list[str] = []
    if missing:
        warnings.append("One or more weighted ranking components are missing.")
    if proxy_components:
        proxy_weight = sum(component.weight for component in proxy_components)
        warnings.append(f"Proxy components represent {proxy_weight:.0%} of profile weight.")
    if penalties:
        warnings.append("One or more explicit ranking penalties were applied.")
    for component in used:
        if component.component in {
            RecommendationScoreComponent.MARKET_COVERAGE,
            RecommendationScoreComponent.CONFIDENCE,
            RecommendationScoreComponent.FRESHNESS,
        } and component.value <= 0.35:
            warnings.append(f"Weak evidence-quality component: {component.component.value}.")
    return tuple(warnings)


def _weighted_value_for(
    used: list[WeightedScoreComponent],
    component: RecommendationScoreComponent,
) -> float | None:
    for item in used:
        if item.component is component:
            return item.weighted_value
    return None


def _ordered_components(
    components: Mapping[RecommendationScoreComponent, ResolvedScoreComponent],
) -> tuple[ResolvedScoreComponent, ...]:
    return tuple(components[component] for component in RecommendationScoreComponent)


def _value_component(
    component: RecommendationScoreComponent,
    value: float | None,
    *,
    basis: tuple[RecommendationEvidenceBasis, ...],
    refs: tuple[RecommendationEvidenceReference, ...],
    source_fields: tuple[str, ...],
    is_proxy: bool = False,
    inferred: bool = False,
    warning: str | None = None,
    missing_warning: str,
) -> ResolvedScoreComponent:
    normalized = _bounded(value)
    if normalized is None:
        return _missing_component(component, missing_warning)
    status = ScoreComponentStatus.PROXY if is_proxy else ScoreComponentStatus.USED
    evidence_basis = (
        (*basis, RecommendationEvidenceBasis.HEURISTIC_INFERENCE)
        if inferred and RecommendationEvidenceBasis.HEURISTIC_INFERENCE not in basis
        else basis
    )
    return ResolvedScoreComponent(
        component=component,
        status=status,
        value=normalized,
        evidence_basis=tuple(dict.fromkeys(evidence_basis)),
        evidence_refs=refs,
        source_fields=source_fields,
        is_proxy=is_proxy,
        inferred=inferred,
        warning=warning,
    )


def _missing_component(
    component: RecommendationScoreComponent,
    warning: str,
) -> ResolvedScoreComponent:
    return ResolvedScoreComponent(
        component=component,
        status=ScoreComponentStatus.MISSING,
        value=None,
        evidence_basis=(RecommendationEvidenceBasis.MISSING_DATA,),
        warning=warning,
    )


def _region_prestige_component(
    body: Any,
    *,
    scores: Any,
    summary: Any,
    refs: _ReferenceIndex,
    target: RecommendationTarget,
) -> ResolvedScoreComponent:
    structural = _number_or_none(_field(scores, "structural_ecosystem_score"))
    if structural is not None:
        return _value_component(
            RecommendationScoreComponent.PRESTIGE_DENSITY,
            structural,
            basis=(RecommendationEvidenceBasis.STRUCTURED_SCORE,),
            refs=refs.for_basis(
                RecommendationEvidenceBasis.STRUCTURED_SCORE,
                fallback=_fallback_ref(
                    target,
                    RecommendationEvidenceBasis.STRUCTURED_SCORE,
                    "Region structural ecosystem score",
                    "region_scores",
                ),
            ),
            source_fields=("region.scores.structural_ecosystem_score",),
            missing_warning="Prestige-density score fields are unavailable.",
        )
    major = _number_or_none(_field(summary, "major_tech_count"))
    mag7 = _number_or_none(_field(summary, "mag7_count"))
    if major is None and mag7 is None:
        return _missing_component(
            RecommendationScoreComponent.PRESTIGE_DENSITY,
            "Prestige-density metadata is unavailable.",
        )
    proxy_value = min(((major or 0.0) + (mag7 or 0.0) * 2.0) / 10.0, 1.0)
    return _value_component(
        RecommendationScoreComponent.PRESTIGE_DENSITY,
        proxy_value,
        basis=(RecommendationEvidenceBasis.REGION_METADATA,),
        refs=refs.for_basis(
            RecommendationEvidenceBasis.REGION_METADATA,
            fallback=_fallback_ref(
                target,
                RecommendationEvidenceBasis.REGION_METADATA,
                "Region major-tech/Mag 7 summary",
                "region_summary",
            ),
        ),
        source_fields=(
            "region.summary.major_tech_count",
            "region.summary.mag7_count",
        ),
        is_proxy=True,
        warning="Prestige density is derived from major-tech/Mag 7 summary metadata.",
        missing_warning="Prestige-density metadata is unavailable.",
    )


def _region_ai_cloud_component(
    body: Any,
    *,
    refs: _ReferenceIndex,
    target: RecommendationTarget,
) -> ResolvedScoreComponent:
    sector_value = _ai_cloud_sector_coverage_value(_field(body, "sector_coverage"))
    if sector_value is not None:
        return _value_component(
            RecommendationScoreComponent.AI_CLOUD_CONCENTRATION,
            sector_value,
            basis=(RecommendationEvidenceBasis.MARKET_COVERAGE,),
            refs=refs.for_basis(
                RecommendationEvidenceBasis.MARKET_COVERAGE,
                fallback=_fallback_ref(
                    target,
                    RecommendationEvidenceBasis.MARKET_COVERAGE,
                    "Region AI/cloud sector coverage",
                    "region_sector_coverage",
                ),
            ),
            source_fields=("region.sector_coverage.ai", "region.sector_coverage.cloud"),
            is_proxy=True,
            warning="AI/cloud concentration is resolved from sector coverage metadata.",
            missing_warning="AI/cloud sector coverage is unavailable.",
        )
    top_companies = tuple(_field(body, "top_companies_present") or ())
    if not top_companies:
        return _missing_component(
            RecommendationScoreComponent.AI_CLOUD_CONCENTRATION,
            "AI/cloud sector metadata is unavailable.",
        )
    matches = sum(1 for company in top_companies if _is_ai_cloud_company(company))
    return _value_component(
        RecommendationScoreComponent.AI_CLOUD_CONCENTRATION,
        matches / len(top_companies),
        basis=(
            RecommendationEvidenceBasis.COMPANY_METADATA,
            RecommendationEvidenceBasis.HEURISTIC_INFERENCE,
        ),
        refs=refs.for_basis(
            RecommendationEvidenceBasis.COMPANY_METADATA,
            fallback=_fallback_ref(
                target,
                RecommendationEvidenceBasis.COMPANY_METADATA,
                "Region top-company sector metadata",
                "region_top_companies",
            ),
        ),
        source_fields=("region.top_companies_present.sector_primary",),
        is_proxy=True,
        inferred=True,
        warning="AI/cloud concentration is inferred from top-company sector metadata.",
        missing_warning="AI/cloud sector metadata is unavailable.",
    )


def _company_entry_level_component(
    body: Any,
    entry_regions: tuple[Any, ...],
    *,
    refs: _ReferenceIndex,
    target: RecommendationTarget,
) -> ResolvedScoreComponent:
    scores = [
        value
        for row in entry_regions
        if (value := _number_or_none(_field(row, "entry_level_access_score"))) is not None
    ]
    if scores:
        value = sum(scores) / len(scores)
    else:
        flag = _field(body, "has_entry_level_access")
        value = 1.0 if flag is True else 0.0 if flag is False else None
    return _value_component(
        RecommendationScoreComponent.ENTRY_LEVEL_ACCESS,
        value,
        basis=(RecommendationEvidenceBasis.COMPANY_METADATA,),
        refs=refs.for_basis(
            RecommendationEvidenceBasis.COMPANY_METADATA,
            fallback=_fallback_ref(
                target,
                RecommendationEvidenceBasis.COMPANY_METADATA,
                "Company entry-level metadata",
                "company_entry_level_regions",
            ),
        ),
        source_fields=(
            "company.entry_level_regions.entry_level_access_score",
            "has_entry_level_access",
        ),
        missing_warning="Company entry-level access fields are unavailable.",
    )


def _company_internship_component(
    entry_regions: tuple[Any, ...],
    *,
    refs: _ReferenceIndex,
    target: RecommendationTarget,
) -> ResolvedScoreComponent:
    count = 0.0
    saw_field = False
    for row in entry_regions:
        for name in ("internship_count", "coop_count"):
            value = _number_or_none(_field(row, name))
            if value is not None:
                count += value
                saw_field = True
    return _value_component(
        RecommendationScoreComponent.INTERNSHIP_OR_COOP_ACCESS,
        _count_value(count if saw_field else None, divisor=8.0),
        basis=(RecommendationEvidenceBasis.COMPANY_METADATA,),
        refs=refs.for_basis(
            RecommendationEvidenceBasis.COMPANY_METADATA,
            fallback=_fallback_ref(
                target,
                RecommendationEvidenceBasis.COMPANY_METADATA,
                "Company internship/co-op metadata",
                "company_entry_level_regions",
            ),
        ),
        source_fields=(
            "company.entry_level_regions.internship_count",
            "company.entry_level_regions.coop_count",
        ),
        missing_warning="Company internship/co-op fields are unavailable.",
    )


def _company_prestige_component(
    body: Any,
    *,
    refs: _ReferenceIndex,
    target: RecommendationTarget,
) -> ResolvedScoreComponent:
    prestige = _number_or_none(_field(body, "prestige_score"))
    if prestige is None:
        if _field(body, "is_mag7") is True:
            prestige = 1.0
        elif _field(body, "is_major_tech") is True:
            prestige = 0.8
    return _value_component(
        RecommendationScoreComponent.PRESTIGE_DENSITY,
        prestige,
        basis=(RecommendationEvidenceBasis.COMPANY_METADATA,),
        refs=refs.for_basis(
            RecommendationEvidenceBasis.COMPANY_METADATA,
            fallback=_fallback_ref(
                target,
                RecommendationEvidenceBasis.COMPANY_METADATA,
                "Company prestige metadata",
                "company_metadata",
            ),
        ),
        source_fields=("company.prestige_score", "company.is_major_tech", "company.is_mag7"),
        missing_warning="Company prestige metadata is unavailable.",
    )


def _company_ai_cloud_component(
    body: Any,
    *,
    refs: _ReferenceIndex,
    target: RecommendationTarget,
) -> ResolvedScoreComponent:
    fields = (
        _field(body, "sector_primary"),
        _field(body, "sector_secondary"),
        _field(body, "sector"),
        _field(body, "industry"),
    )
    strings = tuple(text for value in fields if (text := _string_or_none(value)))
    if not strings:
        return _missing_component(
            RecommendationScoreComponent.AI_CLOUD_CONCENTRATION,
            "Company sector metadata is unavailable.",
        )
    value = 1.0 if any(_is_ai_cloud_text(text) for text in strings) else 0.0
    return _value_component(
        RecommendationScoreComponent.AI_CLOUD_CONCENTRATION,
        value,
        basis=(RecommendationEvidenceBasis.COMPANY_METADATA,),
        refs=refs.for_basis(
            RecommendationEvidenceBasis.COMPANY_METADATA,
            fallback=_fallback_ref(
                target,
                RecommendationEvidenceBasis.COMPANY_METADATA,
                "Company sector metadata",
                "company_metadata",
            ),
        ),
        source_fields=(
            "company.sector_primary",
            "company.sector_secondary",
            "sector",
            "industry",
        ),
        is_proxy=True,
        warning="AI/cloud concentration is resolved from sector metadata.",
        missing_warning="Company sector metadata is unavailable.",
    )


def _role_diversity_component(
    body: Any,
    *,
    refs: _ReferenceIndex,
    target: RecommendationTarget,
    metadata_basis: RecommendationEvidenceBasis,
) -> ResolvedScoreComponent:
    role_families = tuple(_field(body, "role_families") or ())
    role_counts = _field(body, "role_family_counts")
    if role_families:
        value = min(len(role_families) / 5.0, 1.0)
    elif isinstance(role_counts, Mapping) and role_counts:
        value = min(len(role_counts) / 5.0, 1.0)
    else:
        return _missing_component(
            RecommendationScoreComponent.ROLE_DIVERSITY,
            "Role-family diversity fields are unavailable.",
        )
    return _value_component(
        RecommendationScoreComponent.ROLE_DIVERSITY,
        value,
        basis=(metadata_basis,),
        refs=refs.for_basis(
            metadata_basis,
            fallback=_fallback_ref(
                target,
                metadata_basis,
                "Role-family metadata",
                "role_family_summary",
            ),
        ),
        source_fields=("role_families", "role_family_counts"),
        is_proxy=True,
        warning="Role diversity is resolved from available role-family metadata.",
        missing_warning="Role-family diversity fields are unavailable.",
    )


def _coverage_component(
    coverage: Any,
    *,
    refs: _ReferenceIndex,
    target: RecommendationTarget,
) -> ResolvedScoreComponent:
    score = _coverage_score(coverage)
    return _value_component(
        RecommendationScoreComponent.MARKET_COVERAGE,
        score,
        basis=(RecommendationEvidenceBasis.MARKET_COVERAGE,),
        refs=refs.for_basis(
            RecommendationEvidenceBasis.MARKET_COVERAGE,
            fallback=_fallback_ref(
                target,
                RecommendationEvidenceBasis.MARKET_COVERAGE,
                "Market coverage metadata",
                "coverage",
            ),
        ),
        source_fields=("coverage.quality_score", "coverage.coverage_quality_score"),
        is_proxy=bool(_field(coverage, "heuristic")),
        warning=(
            "Coverage quality is heuristic and should be read with freshness/confidence."
            if coverage is not None and _field(coverage, "heuristic")
            else None
        ),
        missing_warning="Market coverage metadata is unavailable.",
    )


def _confidence_component(
    body: Any,
    *,
    refs: _ReferenceIndex,
    explanation: RecommendationExplanation,
) -> ResolvedScoreComponent:
    score = (
        explanation.confidence_summary.confidence_score
        if explanation.confidence_summary is not None
        else None
    )
    if score is None:
        score = _confidence_score_from_text(_field(body, "classification_confidence"))
    if score is None:
        score = _confidence_from_coverage(_field(body, "coverage"))
    return _value_component(
        RecommendationScoreComponent.CONFIDENCE,
        score,
        basis=(RecommendationEvidenceBasis.CONFIDENCE,),
        refs=refs.for_basis(RecommendationEvidenceBasis.CONFIDENCE),
        source_fields=(
            "explanation.confidence_summary",
            "company.classification_confidence",
            "coverage.components.confidence",
        ),
        missing_warning="Confidence context is unavailable.",
    )


def _freshness_component(
    payload: Any,
    *,
    refs: _ReferenceIndex,
    explanation: RecommendationExplanation,
) -> ResolvedScoreComponent:
    status = (
        explanation.freshness_summary.freshness_status
        if explanation.freshness_summary is not None
        else None
    )
    freshness = _field(payload, "freshness")
    if freshness is None:
        body = _field(payload, "region") or _field(payload, "company")
        freshness = _field(body, "freshness")
    if status is None:
        status = _enum_or_string(_field(freshness, "freshness_status"))
    if status is None:
        metadata = _field(payload, "metadata") or payload
        status = _enum_or_string(_field(metadata, "state"))
    return _value_component(
        RecommendationScoreComponent.FRESHNESS,
        _freshness_status_score(status),
        basis=(RecommendationEvidenceBasis.FRESHNESS,),
        refs=refs.for_basis(RecommendationEvidenceBasis.FRESHNESS),
        source_fields=("explanation.freshness_summary", "metadata.state"),
        missing_warning="Freshness context is unavailable.",
    )


def _lower_competition_component(
    components: Mapping[RecommendationScoreComponent, ResolvedScoreComponent],
    warning: str,
) -> ResolvedScoreComponent:
    prestige = components.get(RecommendationScoreComponent.PRESTIGE_DENSITY)
    density = components.get(RecommendationScoreComponent.COMPANY_DENSITY)
    inputs: list[float] = []
    source_fields: list[str] = []
    if prestige is not None and prestige.value is not None:
        inputs.append(1.0 - prestige.value)
        source_fields.append("inverse prestige_density")
    if density is not None and density.value is not None:
        inputs.append(1.0 - density.value)
        source_fields.append("inverse company_density")
    if not inputs:
        return _missing_component(
            RecommendationScoreComponent.LOWER_COMPETITION_PROXY,
            "Lower-competition proxy inputs are unavailable.",
        )
    return ResolvedScoreComponent(
        component=RecommendationScoreComponent.LOWER_COMPETITION_PROXY,
        status=ScoreComponentStatus.PROXY,
        value=max(0.0, min(1.0, sum(inputs) / len(inputs))),
        evidence_basis=(RecommendationEvidenceBasis.HEURISTIC_INFERENCE,),
        source_fields=tuple(source_fields),
        is_proxy=True,
        inferred=True,
        warning=warning,
    )


def _tradeoff_signal_status(component: WeightedScoreComponent) -> TradeoffSignalStatus:
    return TradeoffSignalStatus.PROXY if component.is_proxy else TradeoffSignalStatus.USED


class _ReferenceIndex:
    def __init__(self, explanation: RecommendationExplanation) -> None:
        self._by_basis: dict[
            RecommendationEvidenceBasis,
            list[RecommendationEvidenceReference],
        ] = {}
        for ref in explanation.evidence_refs:
            self._by_basis.setdefault(ref.basis, []).append(ref)

    def for_basis(
        self,
        basis: RecommendationEvidenceBasis,
        *,
        fallback: RecommendationEvidenceReference | None = None,
    ) -> tuple[RecommendationEvidenceReference, ...]:
        refs = tuple(self._by_basis.get(basis, ()))
        if refs:
            return refs
        return (fallback,) if fallback is not None else ()


def _fallback_ref(
    target: RecommendationTarget,
    basis: RecommendationEvidenceBasis,
    label: str,
    reference_type: str,
) -> RecommendationEvidenceReference:
    return RecommendationEvidenceReference(
        basis=basis,
        strength=(
            RecommendationEvidenceStrength.INFERRED
            if basis is RecommendationEvidenceBasis.HEURISTIC_INFERENCE
            else RecommendationEvidenceStrength.MODERATE
        ),
        label=label,
        reference_type=reference_type,
        reference_id=f"{target.target_type.value}:{target.target_id}:{reference_type}",
    )


def _dedupe_refs(
    refs: tuple[RecommendationEvidenceReference, ...],
) -> tuple[RecommendationEvidenceReference, ...]:
    deduped: dict[tuple[str, str | None, str | None], RecommendationEvidenceReference] = {}
    for ref in refs:
        deduped[(ref.basis.value, ref.reference_id, ref.label)] = ref
    return tuple(deduped[key] for key in sorted(deduped))


def _target_id(payload: Any, target_type: RecommendationTargetType) -> str:
    body_name = "region" if target_type is RecommendationTargetType.REGION else "company"
    body = _field(payload, body_name) or payload
    field_name = "region_id" if target_type is RecommendationTargetType.REGION else "company_id"
    value = _string_or_none(_field(body, field_name))
    if value is None:
        raise ValueError(f"{field_name} is required for recommendation ranking")
    return value


def _coverage_score(coverage: Any) -> float | None:
    score = _number_or_none(_field(coverage, "quality_score"))
    if score is not None:
        return max(0.0, min(1.0, score / 100.0 if score > 1.0 else score))
    quality_payload = _field(coverage, "coverage_quality_score")
    score = _number_or_none(_field(quality_payload, "overall_score"))
    if score is None:
        return None
    return max(0.0, min(1.0, score / 100.0 if score > 1.0 else score))


def _average_coverage(coverages: tuple[Any, ...]) -> Mapping[str, Any] | Any | None:
    if not coverages:
        return None
    values = [value for coverage in coverages if (value := _coverage_score(coverage)) is not None]
    if not values:
        return coverages[0]
    return {
        "quality_score": sum(values) / len(values),
        "heuristic": any(bool(_field(coverage, "heuristic")) for coverage in coverages),
    }


def _company_coverages(body: Any) -> tuple[Any, ...]:
    coverages: list[Any] = []
    for collection_name in ("regions_present", "regions_hiring", "entry_level_regions"):
        for row in tuple(_field(body, collection_name) or ()):
            coverage = _field(row, "coverage")
            if coverage is not None:
                coverages.append(coverage)
    matched = _field(body, "matched_region_coverage")
    if isinstance(matched, Mapping):
        coverages.extend(coverage for coverage in matched.values() if coverage is not None)
    return tuple(coverages)


def _confidence_from_coverage(coverage: Any) -> float | None:
    components = _field(coverage, "components")
    if not isinstance(components, Mapping):
        return None
    return _coverage_component_value(components.get("confidence"))


def _coverage_component_value(value: Any) -> float | None:
    number = _number_or_none(value)
    if number is None:
        return None
    return max(0.0, min(1.0, number / 100.0 if number > 1.0 else number))


def _confidence_score_from_text(value: Any) -> float | None:
    text = _enum_or_string(value)
    if text is None:
        return None
    lowered = text.casefold()
    if "high" in lowered:
        return 1.0
    if "moderate" in lowered or "medium" in lowered:
        return 0.6
    if "low" in lowered:
        return 0.25
    if "unknown" in lowered:
        return 0.1
    return None


def _freshness_status_score(value: Any) -> float | None:
    text = _enum_or_string(value)
    if text is None:
        return None
    lowered = text.casefold()
    if lowered == "fresh":
        return 1.0
    if lowered == "partial":
        return 0.5
    if lowered in {"stale", "seeded_demo"}:
        return 0.2
    if lowered == "unknown":
        return 0.1
    return None


def _ai_cloud_sector_coverage_value(sector_coverage: Any) -> float | None:
    if not isinstance(sector_coverage, Mapping):
        return None
    values: list[float] = []
    for key in ("ai", "cloud"):
        entry = sector_coverage.get(key)
        level = _enum_or_string(_field(entry, "coverage_level"))
        if level is None:
            continue
        mapped = {
            "strong": 1.0,
            "partial": 0.65,
            "watchlist": 0.45,
            "limited": 0.25,
            "unknown": None,
        }.get(level)
        if mapped is not None:
            values.append(mapped)
    if not values:
        return None
    return sum(values) / len(values)


def _is_ai_cloud_company(company: Any) -> bool:
    return any(
        _is_ai_cloud_text(text)
        for name in ("sector_primary", "sector_secondary", "sector", "industry")
        if (text := _string_or_none(_field(company, name))) is not None
    )


def _is_ai_cloud_text(text: str) -> bool:
    normalized = text.casefold().replace("-", "_").replace(" ", "_")
    return normalized in {"ai", "artificial_intelligence", "cloud"} or any(
        token in normalized for token in ("ai_", "_ai", "cloud")
    )


def _region_ids_from_rows(rows: tuple[Any, ...]) -> set[str | None]:
    return {_string_or_none(_field(row, "region_id")) for row in rows}


def _count_value(value: Any, *, divisor: float) -> float | None:
    number = _number_or_none(value)
    if number is None:
        return None
    return max(0.0, min(1.0, number / divisor))


def _sum_numbers(*values: Any) -> float | None:
    total = 0.0
    found = False
    for value in values:
        number = _number_or_none(value)
        if number is None:
            continue
        found = True
        total += number
    return total if found else None


def _first_number(*values: Any) -> float | None:
    for value in values:
        number = _number_or_none(value)
        if number is not None:
            return number
    return None


def _bounded(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, value))


def _field(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _enum_or_string(value: Any) -> str | None:
    if value is None:
        return None
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return _string_or_none(value)
