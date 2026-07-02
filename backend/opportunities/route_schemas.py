"""API-safe contracts for Layer 23C opportunity routing."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.opportunities.schemas import (
    OpportunityExpirationState,
    OpportunityLocationMode,
    OpportunityProgramType,
    OpportunityReviewStatus,
    OpportunitySeniorityLevel,
    OpportunityTrustLabel,
)


class OpportunityRouteConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OpportunityRouteSourceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_basis: str
    source_categories: tuple[str, ...] = Field(default_factory=tuple)
    source_count: int = Field(ge=0)
    notes: tuple[str, ...] = Field(default_factory=tuple)


class OpportunityRouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_intent_summary: str | None = Field(default=None, min_length=1, max_length=2048)
    profile_summary: str | None = Field(default=None, min_length=1, max_length=2048)
    target_regions: tuple[str, ...] = Field(min_length=1, max_length=12)
    target_role_families: tuple[str, ...] = Field(min_length=1, max_length=12)
    preferred_program_types: tuple[OpportunityProgramType, ...] = Field(
        default_factory=tuple,
        max_length=12,
    )
    preferred_location_modes: tuple[OpportunityLocationMode, ...] = Field(
        default_factory=tuple,
        max_length=8,
    )
    experience_level: OpportunitySeniorityLevel = OpportunitySeniorityLevel.UNKNOWN
    skills: tuple[str, ...] = Field(default_factory=tuple, max_length=24)
    background_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=24)
    constraints: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    opportunity_trust_preferences: tuple[OpportunityTrustLabel, ...] = Field(
        default_factory=tuple,
        max_length=8,
    )
    include_unverified: bool = False
    limit: int = Field(default=5, ge=1, le=25)

    @field_validator(
        "user_intent_summary",
        "profile_summary",
        mode="before",
    )
    @classmethod
    def _optional_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)

    @field_validator(
        "target_regions",
        "target_role_families",
        "skills",
        "background_tags",
        "constraints",
        mode="before",
    )
    @classmethod
    def _string_tuple_values_not_blank(cls, value: object) -> object:
        if isinstance(value, str):
            values = (value,)
        else:
            values = value
        if not isinstance(values, tuple | list):
            return values
        return tuple(_clean_required_string(str(item)) for item in values)

    @model_validator(mode="after")
    def _intent_or_profile_is_required(self) -> Self:
        if self.user_intent_summary is None and self.profile_summary is None:
            raise ValueError("user_intent_summary or profile_summary is required")
        return self


class MatchedOpportunity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity_id: str
    employer_name: str
    program_name: str
    program_type: OpportunityProgramType
    region: str
    metro: str | None = None
    role_family: str
    location_mode: OpportunityLocationMode
    trust_label: OpportunityTrustLabel
    review_status: OpportunityReviewStatus
    expiration_state: OpportunityExpirationState
    partner_submitted: bool
    paid_partner: bool
    application_url: str
    source_url: str
    fit_score: float = Field(ge=0.0, le=1.0)
    fit_explanation: str
    warnings: tuple[str, ...] = Field(default_factory=tuple)


class OpportunityRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    route_id: str
    route_title: str
    target_region: str
    target_role_family: str
    recommended_company_types: tuple[str, ...] = Field(default_factory=tuple)
    matched_opportunities: tuple[MatchedOpportunity, ...] = Field(default_factory=tuple)
    market_fit_score: float = Field(ge=0.0, le=1.0)
    region_fit_score: float = Field(ge=0.0, le=1.0)
    company_type_fit_score: float = Field(ge=0.0, le=1.0)
    opportunity_fit_score: float = Field(ge=0.0, le=1.0)
    role_family_fit_score: float = Field(ge=0.0, le=1.0)
    overall_route_fit_score: float = Field(ge=0.0, le=1.0)
    confidence: OpportunityRouteConfidence
    explanation: str
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    next_steps: tuple[str, ...] = Field(default_factory=tuple)
    source_summary: OpportunityRouteSourceSummary
    sponsored_or_partner_disclosure: str | None = None


class OpportunityRouteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    routes: tuple[OpportunityRoute, ...] = Field(default_factory=tuple)
    route_count: int = Field(ge=0)
    route_generation_note: str
    non_goal_disclosures: tuple[str, ...] = Field(default_factory=tuple)


def _clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def _clean_required_string(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped
