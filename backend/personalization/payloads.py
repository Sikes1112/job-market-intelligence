"""Pydantic payload models for personalization input + output.

Shapes mirror ``API_SURFACES.md`` §8 closely. The personalization layer is
session-scoped: nothing here is persisted, and the response stays in
memory until Slice 12 hands it back to the caller.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
