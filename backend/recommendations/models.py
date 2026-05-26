"""Layer 14A recommendation-domain contracts.

The recommendation layer is a representation layer. It may explain why an
already-supported target looks useful, but it must not become the source of
market truth. Every explanatory claim below is either tied to structured app
evidence or explicitly marked as heuristic / missing-data context.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class RecommendationGoalMode(_Vocabulary):
    MAXIMIZE_ENTRY_LEVEL_ACCESS = "maximize_entry_level_access"
    MAXIMIZE_PRESTIGE = "maximize_prestige"
    MAXIMIZE_AI_CLOUD_CONCENTRATION = "maximize_ai_cloud_concentration"
    MAXIMIZE_UNDERRATED_MARKETS = "maximize_underrated_markets"
    MAXIMIZE_INTERNSHIP_COOP_ACCESS = "maximize_internship_coop_access"
    MAXIMIZE_LOWER_COMPETITION = "maximize_lower_competition"
    MAXIMIZE_GEOGRAPHIC_FLEXIBILITY = "maximize_geographic_flexibility"


class RecommendationTargetType(_Vocabulary):
    REGION = "region"
    COMPANY = "company"
    COMPANY_CATEGORY = "company_category"
    ROLE_FAMILY = "role_family"
    MARKET_STRATEGY = "market_strategy"
    WATCHLIST_ITEM = "watchlist_item"


class RecommendationEvidenceStrength(_Vocabulary):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    MISSING = "missing"
    INFERRED = "inferred"


class RecommendationEvidenceBasis(_Vocabulary):
    STRUCTURED_SCORE = "structured_score"
    MARKET_COVERAGE = "market_coverage"
    COMPANY_METADATA = "company_metadata"
    REGION_METADATA = "region_metadata"
    PROVENANCE = "provenance"
    FRESHNESS = "freshness"
    CONFIDENCE = "confidence"
    DATA_QUALITY_WARNING = "data_quality_warning"
    HEURISTIC_INFERENCE = "heuristic_inference"
    USER_PREFERENCE = "user_preference"
    MISSING_DATA = "missing_data"


_REFERENCE_OPTIONAL_BASIS: frozenset[RecommendationEvidenceBasis] = frozenset(
    {
        RecommendationEvidenceBasis.HEURISTIC_INFERENCE,
        RecommendationEvidenceBasis.USER_PREFERENCE,
        RecommendationEvidenceBasis.MISSING_DATA,
    }
)


class RecommendationClaimSupport(_Vocabulary):
    DIRECT = "direct"
    INFERRED = "inferred"


class RecommendationImportance(_Vocabulary):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendationReasonCategory(_Vocabulary):
    REGION_FIT = "region_fit"
    COMPANY_FIT = "company_fit"
    GOAL_ALIGNMENT = "goal_alignment"
    PREFERENCE_MATCH = "preference_match"
    DATA_STRENGTH = "data_strength"


class RecommendationWeaknessCategory(_Vocabulary):
    LOW_CONFIDENCE = "low_confidence"
    STALE_DATA = "stale_data"
    MISSING_DATA = "missing_data"
    COVERAGE_GAP = "coverage_gap"
    NARROW_EVIDENCE = "narrow_evidence"
    HEURISTIC_LIMITATION = "heuristic_limitation"


class RecommendationTradeoffCategory(_Vocabulary):
    OPPORTUNITY_VS_COMPETITION = "opportunity_vs_competition"
    AI_CLOUD_CONCENTRATION_VS_COMPANY_UNIVERSE = (
        "ai_cloud_concentration_vs_company_universe"
    )
    GROWTH_VS_PRESTIGE_DENSITY = "growth_vs_prestige_density"
    SECTOR_STRENGTH_VS_CONSUMER_TECH = "sector_strength_vs_consumer_tech"
    LOWER_COMPETITION_VS_ROLE_VOLUME = "lower_competition_vs_role_volume"
    PRESTIGE_VS_ENTRY_LEVEL_ACCESS = "prestige_vs_entry_level_access"
    GEOGRAPHIC_FLEXIBILITY_VS_CONSTRAINTS = "geographic_flexibility_vs_constraints"
    DATA_QUALITY = "data_quality"


class ManualVerificationCategory(_Vocabulary):
    CURRENT_JOB_POSTINGS = "current_job_postings"
    ENTRY_LEVEL_HIRING = "entry_level_hiring"
    INTERNSHIP_COOP_ACCESS = "internship_coop_access"
    LOCATION_REQUIREMENTS = "location_requirements"
    COMPANY_POLICY = "company_policy"
    DATA_FRESHNESS_OR_CONFIDENCE = "data_freshness_or_confidence"
    SOURCE_CONFIRMATION = "source_confirmation"
    OTHER = "other"


class RecommendationGoalModeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    goal_mode: RecommendationGoalMode
    label: str = Field(min_length=1, max_length=96)
    description: str = Field(min_length=1, max_length=256)

    @field_validator("label", "description")
    @classmethod
    def _strings_not_blank(cls, value: str) -> str:
        return _clean_required_string(value, "goal mode metadata")


def _clean_required_string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} entries must be strings")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{label} entries must not be blank")
    return stripped


_GOAL_MODE_DEFINITIONS: dict[
    RecommendationGoalMode,
    RecommendationGoalModeDefinition,
] = {
    RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS: RecommendationGoalModeDefinition(
        goal_mode=RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS,
        label="Maximize entry-level access",
        description="Favor markets and employers with stronger early-career access signals.",
    ),
    RecommendationGoalMode.MAXIMIZE_PRESTIGE: RecommendationGoalModeDefinition(
        goal_mode=RecommendationGoalMode.MAXIMIZE_PRESTIGE,
        label="Maximize prestige",
        description="Favor more selective, brand-dense, or high-prestige opportunities.",
    ),
    RecommendationGoalMode.MAXIMIZE_AI_CLOUD_CONCENTRATION: (
        RecommendationGoalModeDefinition(
            goal_mode=RecommendationGoalMode.MAXIMIZE_AI_CLOUD_CONCENTRATION,
            label="Maximize AI/cloud concentration",
            description="Favor targets with stronger app-owned AI and cloud concentration signals.",
        )
    ),
    RecommendationGoalMode.MAXIMIZE_UNDERRATED_MARKETS: RecommendationGoalModeDefinition(
        goal_mode=RecommendationGoalMode.MAXIMIZE_UNDERRATED_MARKETS,
        label="Maximize underrated markets",
        description="Favor markets that may offer useful opportunity outside obvious hubs.",
    ),
    RecommendationGoalMode.MAXIMIZE_INTERNSHIP_COOP_ACCESS: (
        RecommendationGoalModeDefinition(
            goal_mode=RecommendationGoalMode.MAXIMIZE_INTERNSHIP_COOP_ACCESS,
            label="Maximize internship/co-op access",
            description="Favor targets with stronger internship and co-op access signals.",
        )
    ),
    RecommendationGoalMode.MAXIMIZE_LOWER_COMPETITION: RecommendationGoalModeDefinition(
        goal_mode=RecommendationGoalMode.MAXIMIZE_LOWER_COMPETITION,
        label="Maximize lower competition",
        description="Favor targets where the app can justify a lower-competition thesis.",
    ),
    RecommendationGoalMode.MAXIMIZE_GEOGRAPHIC_FLEXIBILITY: (
        RecommendationGoalModeDefinition(
            goal_mode=RecommendationGoalMode.MAXIMIZE_GEOGRAPHIC_FLEXIBILITY,
            label="Maximize geographic flexibility",
            description="Favor targets that preserve useful location optionality.",
        )
    ),
}

GOAL_MODE_DEFINITIONS = MappingProxyType(_GOAL_MODE_DEFINITIONS)


def recommendation_goal_mode_definitions() -> tuple[RecommendationGoalModeDefinition, ...]:
    return tuple(GOAL_MODE_DEFINITIONS[mode] for mode in RecommendationGoalMode)


def recommendation_goal_mode_definition(
    goal_mode: RecommendationGoalMode | str,
) -> RecommendationGoalModeDefinition:
    return GOAL_MODE_DEFINITIONS[RecommendationGoalMode(goal_mode)]


class RecommendationTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_type: RecommendationTargetType
    target_id: str = Field(min_length=1, max_length=128)
    display_label: str | None = Field(default=None, min_length=1, max_length=128)
    parent_target_id: str | None = Field(default=None, min_length=1, max_length=128)
    related_target_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=25)

    @field_validator("target_id", "display_label", "parent_target_id")
    @classmethod
    def _optional_strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required_string(value, "target")

    @field_validator("related_target_ids")
    @classmethod
    def _related_ids_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_required_string(item, "related_target_ids") for item in value)


class RecommendationConfidenceSummary(BaseModel):
    """Reference to confidence metadata owned elsewhere in the app."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    confidence_level: str | None = Field(default=None, min_length=1, max_length=64)
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_status: str | None = Field(default=None, min_length=1, max_length=64)
    confidence_ref: str | None = Field(default=None, min_length=1, max_length=128)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=20)

    @field_validator("confidence_level", "confidence_status", "confidence_ref")
    @classmethod
    def _optional_strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required_string(value, "confidence summary")

    @field_validator("warnings")
    @classmethod
    def _warnings_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_required_string(item, "confidence warnings") for item in value)

    @model_validator(mode="after")
    def _must_reference_confidence(self) -> RecommendationConfidenceSummary:
        if not any(
            (
                self.confidence_level,
                self.confidence_score is not None,
                self.confidence_status,
                self.confidence_ref,
                self.warnings,
            )
        ):
            raise ValueError("confidence summary must reference existing confidence metadata")
        return self


class RecommendationFreshnessSummary(BaseModel):
    """Reference to freshness metadata owned elsewhere in the app."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    freshness_status: str | None = Field(default=None, min_length=1, max_length=64)
    data_basis: str | None = Field(default=None, min_length=1, max_length=64)
    last_updated_at: datetime | None = None
    freshness_expires_at: datetime | None = None
    source_count: int | None = Field(default=None, ge=0, le=10_000)
    freshness_ref: str | None = Field(default=None, min_length=1, max_length=128)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=20)

    @field_validator("freshness_status", "data_basis", "freshness_ref")
    @classmethod
    def _optional_strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required_string(value, "freshness summary")

    @field_validator("last_updated_at", "freshness_expires_at")
    @classmethod
    def _timestamps_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("freshness timestamps must be timezone-aware")
        return value

    @field_validator("warnings")
    @classmethod
    def _warnings_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_required_string(item, "freshness warnings") for item in value)

    @model_validator(mode="after")
    def _must_reference_freshness(self) -> RecommendationFreshnessSummary:
        if not any(
            (
                self.freshness_status,
                self.data_basis,
                self.last_updated_at,
                self.freshness_expires_at,
                self.source_count is not None,
                self.freshness_ref,
                self.warnings,
            )
        ):
            raise ValueError("freshness summary must reference existing freshness metadata")
        return self


class RecommendationProvenanceReference(BaseModel):
    """Reference to provenance/source identifiers owned by Layer 3."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provenance_ref: str | None = Field(default=None, min_length=1, max_length=128)
    source_ref_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_observation_id: str | None = Field(default=None, min_length=1, max_length=128)
    fact_source_link_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_type: str | None = Field(default=None, min_length=1, max_length=64)
    origin: str | None = Field(default=None, min_length=1, max_length=64)
    source_refs: tuple[str, ...] = Field(default_factory=tuple, max_length=50)

    @field_validator(
        "provenance_ref",
        "source_ref_id",
        "source_observation_id",
        "fact_source_link_id",
        "source_type",
        "origin",
    )
    @classmethod
    def _optional_strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required_string(value, "provenance reference")

    @field_validator("source_refs")
    @classmethod
    def _source_refs_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_required_string(item, "source_refs") for item in value)

    @model_validator(mode="after")
    def _must_reference_provenance(self) -> RecommendationProvenanceReference:
        if not any(
            (
                self.provenance_ref,
                self.source_ref_id,
                self.source_observation_id,
                self.fact_source_link_id,
                self.source_refs,
            )
        ):
            raise ValueError("provenance reference must carry an app-owned reference id")
        return self


class RecommendationEvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    basis: RecommendationEvidenceBasis
    strength: RecommendationEvidenceStrength
    label: str | None = Field(default=None, min_length=1, max_length=128)
    reference_type: str | None = Field(default=None, min_length=1, max_length=64)
    reference_id: str | None = Field(default=None, min_length=1, max_length=128)
    provenance: RecommendationProvenanceReference | None = None
    confidence: RecommendationConfidenceSummary | None = None
    freshness: RecommendationFreshnessSummary | None = None
    coverage_warning_refs: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    data_quality_warning_refs: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    note: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("label", "reference_type", "reference_id", "note")
    @classmethod
    def _optional_strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required_string(value, "evidence reference")

    @field_validator("coverage_warning_refs", "data_quality_warning_refs")
    @classmethod
    def _warning_refs_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_required_string(item, "warning references") for item in value)

    @model_validator(mode="after")
    def _must_be_traceable_or_explicit(self) -> RecommendationEvidenceReference:
        if self.basis is RecommendationEvidenceBasis.HEURISTIC_INFERENCE:
            if self.strength is not RecommendationEvidenceStrength.INFERRED:
                raise ValueError("heuristic evidence must use inferred strength")
        elif self.strength is RecommendationEvidenceStrength.INFERRED:
            raise ValueError("inferred evidence must use heuristic_inference basis")

        if self.basis in _REFERENCE_OPTIONAL_BASIS:
            return self

        if not _evidence_reference_has_required_anchor(self):
            raise ValueError(
                "structured evidence references require an app-owned anchor "
                "matching their evidence basis"
            )
        return self


class RecommendationReason(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reason_category: RecommendationReasonCategory
    label: str = Field(min_length=1, max_length=128)
    detail: str | None = Field(default=None, min_length=1, max_length=512)
    evidence_strength: RecommendationEvidenceStrength
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    support: RecommendationClaimSupport = RecommendationClaimSupport.DIRECT
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )

    @field_validator("label", "detail")
    @classmethod
    def _optional_strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required_string(value, "recommendation reason")

    @model_validator(mode="after")
    def _claim_is_supported(self) -> RecommendationReason:
        _validate_claim_support(
            evidence_basis=self.evidence_basis,
            evidence_strength=self.evidence_strength,
            support=self.support,
            evidence_refs=self.evidence_refs,
        )
        return self


class RecommendationTradeoff(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tradeoff_category: RecommendationTradeoffCategory
    label: str = Field(min_length=1, max_length=128)
    positive_side: str = Field(min_length=1, max_length=512)
    negative_side: str = Field(min_length=1, max_length=512)
    importance: RecommendationImportance
    evidence_strength: RecommendationEvidenceStrength
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    support: RecommendationClaimSupport = RecommendationClaimSupport.DIRECT
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )

    @field_validator("label", "positive_side", "negative_side")
    @classmethod
    def _strings_not_blank(cls, value: str) -> str:
        return _clean_required_string(value, "recommendation tradeoff")

    @model_validator(mode="after")
    def _claim_is_supported(self) -> RecommendationTradeoff:
        _validate_claim_support(
            evidence_basis=self.evidence_basis,
            evidence_strength=self.evidence_strength,
            support=self.support,
            evidence_refs=self.evidence_refs,
        )
        return self


class RecommendationWeakness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    weakness_category: RecommendationWeaknessCategory
    label: str = Field(min_length=1, max_length=128)
    detail: str | None = Field(default=None, min_length=1, max_length=512)
    evidence_strength: RecommendationEvidenceStrength
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    support: RecommendationClaimSupport = RecommendationClaimSupport.DIRECT
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )

    @field_validator("label", "detail")
    @classmethod
    def _optional_strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required_string(value, "recommendation weakness")

    @model_validator(mode="after")
    def _claim_is_supported(self) -> RecommendationWeakness:
        _validate_claim_support(
            evidence_basis=self.evidence_basis,
            evidence_strength=self.evidence_strength,
            support=self.support,
            evidence_refs=self.evidence_refs,
        )
        return self


class RecommendationManualVerificationItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    verification_category: ManualVerificationCategory
    label: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=512)
    rationale: str | None = Field(default=None, min_length=1, max_length=512)
    importance: RecommendationImportance = RecommendationImportance.MEDIUM
    evidence_strength: RecommendationEvidenceStrength
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    support: RecommendationClaimSupport = RecommendationClaimSupport.DIRECT
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )

    @field_validator("label", "question", "rationale")
    @classmethod
    def _optional_strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required_string(value, "manual verification item")

    @model_validator(mode="after")
    def _claim_is_supported(self) -> RecommendationManualVerificationItem:
        _validate_claim_support(
            evidence_basis=self.evidence_basis,
            evidence_strength=self.evidence_strength,
            support=self.support,
            evidence_refs=self.evidence_refs,
        )
        return self


class RecommendationExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target: RecommendationTarget
    goal_mode: RecommendationGoalMode | None = None
    headline: str | None = Field(default=None, min_length=1, max_length=192)
    fit_reasons: tuple[RecommendationReason, ...] = Field(default_factory=tuple, max_length=30)
    data_strengths: tuple[RecommendationReason, ...] = Field(
        default_factory=tuple,
        max_length=30,
    )
    tradeoffs: tuple[RecommendationTradeoff, ...] = Field(default_factory=tuple, max_length=30)
    weaknesses: tuple[RecommendationWeakness, ...] = Field(default_factory=tuple, max_length=30)
    manual_verification: tuple[RecommendationManualVerificationItem, ...] = Field(
        default_factory=tuple,
        max_length=30,
    )
    evidence_refs: tuple[RecommendationEvidenceReference, ...] = Field(
        default_factory=tuple,
        max_length=50,
    )
    confidence_summary: RecommendationConfidenceSummary | None = None
    freshness_summary: RecommendationFreshnessSummary | None = None
    provenance_refs: tuple[RecommendationProvenanceReference, ...] = Field(
        default_factory=tuple,
        max_length=50,
    )
    coverage_warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=30)
    data_quality_warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=30)

    @field_validator("headline")
    @classmethod
    def _headline_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required_string(value, "recommendation headline")

    @field_validator("coverage_warnings", "data_quality_warnings")
    @classmethod
    def _warnings_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_required_string(item, "recommendation warnings") for item in value)

    @model_validator(mode="after")
    def _must_have_structured_explanation(self) -> RecommendationExplanation:
        if not any(
            (
                self.fit_reasons,
                self.data_strengths,
                self.tradeoffs,
                self.weaknesses,
                self.manual_verification,
            )
        ):
            raise ValueError(
                "recommendation explanation must include structured reasons, "
                "tradeoffs, weaknesses, or manual verification items"
            )
        return self


def _validate_claim_support(
    *,
    evidence_basis: tuple[RecommendationEvidenceBasis, ...],
    evidence_strength: RecommendationEvidenceStrength,
    support: RecommendationClaimSupport,
    evidence_refs: tuple[RecommendationEvidenceReference, ...],
) -> None:
    basis = frozenset(evidence_basis)
    if not basis:
        raise ValueError("recommendation claims require at least one evidence basis")

    if RecommendationEvidenceBasis.HEURISTIC_INFERENCE in basis:
        if support is not RecommendationClaimSupport.INFERRED:
            raise ValueError("heuristic recommendation claims must be marked inferred")
        if evidence_strength is not RecommendationEvidenceStrength.INFERRED:
            raise ValueError("heuristic recommendation claims must use inferred strength")
    elif support is RecommendationClaimSupport.INFERRED:
        raise ValueError("inferred recommendation claims require heuristic_inference basis")

    if evidence_strength is RecommendationEvidenceStrength.INFERRED and (
        RecommendationEvidenceBasis.HEURISTIC_INFERENCE not in basis
    ):
        raise ValueError("inferred evidence strength requires heuristic_inference basis")

    if any(item not in _REFERENCE_OPTIONAL_BASIS for item in basis) and not evidence_refs:
        raise ValueError(
            "structured recommendation claims require evidence_refs unless the "
            "basis is heuristic_inference, user_preference, or missing_data"
        )

    for ref in evidence_refs:
        if ref.basis not in basis:
            raise ValueError("evidence_refs basis must be included in the claim basis")


def _evidence_reference_has_required_anchor(
    ref: RecommendationEvidenceReference,
) -> bool:
    if ref.basis in {
        RecommendationEvidenceBasis.STRUCTURED_SCORE,
        RecommendationEvidenceBasis.COMPANY_METADATA,
        RecommendationEvidenceBasis.REGION_METADATA,
    }:
        return ref.reference_id is not None
    if ref.basis is RecommendationEvidenceBasis.MARKET_COVERAGE:
        return bool(ref.reference_id or ref.coverage_warning_refs)
    if ref.basis is RecommendationEvidenceBasis.PROVENANCE:
        return ref.provenance is not None
    if ref.basis is RecommendationEvidenceBasis.CONFIDENCE:
        return bool(ref.confidence or ref.reference_id)
    if ref.basis is RecommendationEvidenceBasis.FRESHNESS:
        return bool(ref.freshness or ref.reference_id)
    if ref.basis is RecommendationEvidenceBasis.DATA_QUALITY_WARNING:
        return bool(ref.data_quality_warning_refs or ref.reference_id)
    return False
