"""Public-safe application contracts for Explore Context and Explore Fit."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(item.value for item in cls)


class ExplorePersonalizationState(_Vocabulary):
    PERSONALIZED = "personalized"
    NEEDS_INPUT = "needs_input"
    GENERAL_MARKET_INTELLIGENCE = "general_market_intelligence"
    UNSUPPORTED = "unsupported"


class ExploreFitState(_Vocabulary):
    CONFIDENT = "confident"
    TENTATIVE = "tentative"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNSUPPORTED = "unsupported"
    ABSTAINED = "abstained"
    HARD_CONSTRAINT_EXCLUDED = "hard_constraint_excluded"
    GENERAL_MARKET_INTELLIGENCE = "general_market_intelligence"


class GoalMappingState(_Vocabulary):
    SUPPORTED = "supported"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


class GeographicScopeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_refs: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    excluded_region_refs: tuple[str, ...] = Field(default_factory=tuple, max_length=100)

    @field_validator("region_refs", "excluded_region_refs", mode="before")
    @classmethod
    def _clean_refs(cls, value: object) -> tuple[str, ...]:
        return _clean_optional_tuple(value) or ()


class ExploreSessionOverrides(BaseModel):
    """Explicit, request-scoped Explore values. This model is never persisted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    goal: str | None = Field(default=None, min_length=1, max_length=255)
    role_families: tuple[str, ...] | None = Field(default=None, max_length=25)
    industries: tuple[str, ...] | None = Field(default=None, max_length=25)
    opportunity_types: tuple[str, ...] | None = Field(default=None, max_length=12)
    work_arrangements: tuple[str, ...] | None = Field(default=None, max_length=12)
    geographic_scope: GeographicScopeInput | None = None

    @field_validator("goal")
    @classmethod
    def _clean_goal(cls, value: str | None) -> str | None:
        return _clean_text(value) if value is not None else None

    @field_validator(
        "role_families",
        "industries",
        "opportunity_types",
        "work_arrangements",
        mode="before",
    )
    @classmethod
    def _clean_tuples(cls, value: object) -> tuple[str, ...] | None:
        return _clean_optional_tuple(value)


class ExploreMarketsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_overrides: ExploreSessionOverrides = Field(default_factory=ExploreSessionOverrides)


class ExploreContextValues(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    goal: str | None = None
    role_families: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()
    opportunity_types: tuple[str, ...] = ()
    career_stage: str | None = None
    work_arrangements: tuple[str, ...] = ()
    preferred_region_ids: tuple[str, ...] = ()
    included_region_ids: tuple[str, ...] = ()
    excluded_region_ids: tuple[str, ...] = ()
    timing: tuple[str, ...] = ()


class ExploreContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    field: str
    source: str
    reason: str


class ExploreContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    career_identity_id: str | None
    career_identity_version: int | None
    personalization_consent: bool
    profile_defaults: ExploreContextValues
    session_overrides: ExploreContextValues
    effective_context: ExploreContextValues
    context_fingerprint: str
    fingerprint_version: str
    personalization_state: ExplorePersonalizationState
    supported_goal: str | None
    goal_mapping_state: GoalMappingState
    applied_context: tuple[str, ...] = ()
    unsupported_context: tuple[ExploreContextItem, ...] = ()
    limitations: tuple[str, ...] = ()


class ExploreRegion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str
    public_slug: str | None
    display_name: str
    region_type: str | None
    state_codes: tuple[str, ...] = ()
    primary_city: str | None = None
    centroid: dict[str, float] | None = None
    focus_bounds: dict[str, Any] | None = None
    market_support_status: str


class MarketEvidenceCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authority: str = "layer_34_market_intelligence"
    summary: str
    evidence_areas_used: tuple[str, ...] = ()
    evidence_areas_missing: tuple[str, ...] = ()


class OpportunityCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authority: str = "layer_38_current_opportunities"
    status: str
    active_opportunity_count: int = Field(ge=0)
    ranking_eligible_opportunity_count: int = Field(ge=0)
    fresh_opportunity_count: int = Field(ge=0)
    rationale: str | None = None
    limitations: tuple[str, ...] = ()
    affects_explore_fit: bool = False


class ExploreFitVersions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    algorithm_version: str
    market_evidence_authority_version: str
    market_evidence_bundle: str
    calibration_version: str
    context_fingerprint: str
    career_identity_version: int | None


class ExploreFitResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    market_key: str
    region: ExploreRegion
    state: ExploreFitState
    fit_score: float | None = Field(default=None, ge=0.0, le=1.0)
    fit_band: str | None = None
    rank: int | None = Field(default=None, ge=1)
    display_order: int = Field(ge=1)
    tied_region_ids: tuple[str, ...] = ()
    near_tie_region_ids: tuple[str, ...] = ()
    primary_drivers: tuple[dict[str, Any], ...] = ()
    tradeoffs: tuple[str, ...] = ()
    confidence: str
    evidence_sufficiency: str
    freshness: str
    market_coverage: MarketEvidenceCoverage
    opportunity_coverage: OpportunityCoverage
    material_limitations: tuple[str, ...] = ()
    abstention_reason: str | None = None
    hard_constraint_reasons: tuple[str, ...] = ()
    contradiction_status: str = "clear"
    contradiction_findings: tuple[dict[str, Any], ...] = ()
    contradiction_blocking: bool = False
    contradiction_summary: str | None = None
    evidence_hooks: dict[str, Any] = Field(default_factory=dict)
    versions: ExploreFitVersions


class RankingUniverse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    label: str
    region_ids: tuple[str, ...]
    market_count: int = Field(ge=0)
    nationally_representative: bool = False


class ExploreMarketsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context: ExploreContext
    ranking_universe: RankingUniverse
    markets: tuple[ExploreFitResult, ...]
    evaluated_at: datetime
    authority: str = "explore_fit"
    authority_version: str
    contradiction_status: str = "clear"
    contradiction_findings: tuple[dict[str, Any], ...] = ()
    contradiction_blocking: bool = False
    contradiction_summary: str | None = None
    limitations: tuple[str, ...] = ()


def _clean_text(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        raise ValueError("text values must not be blank")
    return cleaned


def _clean_optional_tuple(value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    values = (value,) if isinstance(value, str) else value
    if not isinstance(values, tuple | list):
        raise ValueError("expected a list of strings")
    return tuple(dict.fromkeys(_clean_text(str(item)) for item in values))
