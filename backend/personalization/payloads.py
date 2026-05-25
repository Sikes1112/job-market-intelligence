"""Pydantic payload models for personalization input + output.

Shapes mirror ``API_SURFACES.md`` §8 closely. The personalization layer is
session-scoped: nothing here is persisted, and the response stays in
memory until Slice 12 hands it back to the caller.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.geography.market_coverage import (
    CoverageMetadataPayload,
    placeholder_coverage_metadata,
)
from backend.personalization.controls import ScoringWeightKey, ScoringWeightsInput
from backend.personalization.types import CareerStage, PreferenceLevel

_DEFAULT_LIMIT: int = 25
_MAX_LIMIT: int = 100


class UserPreferences(BaseModel):
    """The session-scoped preference payload for ``POST /discover/personalized``.

    Every field is optional except ``region_ids``: we cannot personalize over
    nothing. Missing preferences are treated *neutrally* by the scoring
    formula — never as an inferred strong signal.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    role_targets: list[str] = Field(default_factory=list)
    industry_preferences: list[str] = Field(default_factory=list)
    career_stage: CareerStage | None = None
    prestige_preference: PreferenceLevel | None = None
    brand_preference: PreferenceLevel | None = None
    region_ids: list[str] = Field(min_length=1)
    limit: int = Field(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT)

    @field_validator("role_targets", "industry_preferences", "region_ids")
    @classmethod
    def _strings_must_be_non_empty(cls, value: list[str]) -> list[str]:
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("entries must be non-empty strings")
        return value


class PersonalizedRegionEntry(BaseModel):
    """One region in the ranked-regions response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str
    display_name: str
    personal_market_score: float
    objective_opportunity_score: float | None = None
    coverage: CoverageMetadataPayload = Field(
        default_factory=placeholder_coverage_metadata
    )
    match_notes: list[str] = Field(default_factory=list)


class PersonalizedCompanyEntry(BaseModel):
    """One company-region pair in the ranked-companies response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: str
    company_name: str
    region_id: str
    region_display_name: str
    personal_company_score: float
    role_fit: float
    industry_fit: float
    prestige_fit: float
    brand_fit: float
    match_notes: list[str] = Field(default_factory=list)


class PersonalizedDiscoveryBody(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ranked_regions: list[PersonalizedRegionEntry] = Field(default_factory=list)
    ranked_companies: list[PersonalizedCompanyEntry] = Field(default_factory=list)


class PersonalizedDiscoveryResult(BaseModel):
    """Wrapper matching ``API_SURFACES.md`` §8 ``personalized`` block."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    personalized: PersonalizedDiscoveryBody
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class ScoringPreviewRequest(BaseModel):
    """Protected scoring-control preview input.

    The route may provide saved user preferences as defaults; caller-supplied
    fields are preview-only and do not persist anything by themselves.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    region_ids: list[str] = Field(min_length=1)
    role_interests: list[str] | None = None
    industry_interests: list[str] | None = None
    scoring_weights: ScoringWeightsInput | None = None

    @field_validator("region_ids")
    @classmethod
    def _region_ids_must_be_non_empty(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("region_ids entries must be non-empty strings")
            cleaned.append(item.strip())
        return cleaned

    @field_validator("role_interests", "industry_interests")
    @classmethod
    def _optional_lists_must_be_non_empty(
        cls,
        value: list[str] | None,
    ) -> list[str] | None:
        if value is None:
            return None
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("preference entries must be non-empty strings")
            cleaned.append(item.strip())
        return cleaned


class ScoringPreviewComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: float | None
    raw_weight: float
    effective_weight: float
    status: str
    evidence: list[str] = Field(default_factory=list)


class CanonicalDefaultScoreSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    objective_opportunity_score: float | None = None
    raw_total_score: float | None = None
    early_career_accessibility_score: float | None = None
    live_market_score: float | None = None
    score_ruleset_version: str | None = None


class ScoringPreviewRegion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str
    display_name: str
    canonical_default_scores: CanonicalDefaultScoreSummary
    coverage: CoverageMetadataPayload = Field(
        default_factory=placeholder_coverage_metadata
    )
    personalized_overlay_score: float | None = None
    components: dict[ScoringWeightKey, ScoringPreviewComponent]
    omitted_components: list[ScoringWeightKey] = Field(default_factory=list)


class ScoringPreviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scoring_weights: ScoringWeightsInput
    normalized_weights: dict[ScoringWeightKey, float]
    regions: list[ScoringPreviewRegion] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
