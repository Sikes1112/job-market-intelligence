"""Shared API-safe coverage payload schemas.

These Pydantic models are read payload contracts used by multiple backend
layers. Coverage calculation and region-expansion policy remain in the
geography layer; this module contains only schema shapes and conservative
presentation defaults.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


COVERAGE_SCORE_MIN = 0.0
COVERAGE_SCORE_MAX = 100.0


class CoverageTier(_Vocabulary):
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"
    TIER_4 = "tier_4"


class SectorCoverageCategory(_Vocabulary):
    AI = "ai"
    CLOUD = "cloud"
    CYBERSECURITY = "cybersecurity"
    FINTECH = "fintech"
    HEALTHTECH = "healthtech"
    EDTECH = "edtech"
    ENTERPRISE_SAAS = "enterprise_saas"
    PUBLIC_SECTOR_TECH = "public_sector_tech"
    DEFENSE_TECH = "defense_tech"
    CONSUMER_TECH = "consumer_tech"


class SectorCoverageLevel(_Vocabulary):
    UNKNOWN = "unknown"
    LIMITED = "limited"
    WATCHLIST = "watchlist"
    PARTIAL = "partial"
    STRONG = "strong"


class PriorityMarket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int = Field(ge=1)
    market_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    display_name: str = Field(min_length=1, max_length=128)


class CoverageQualityScorePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    overall_score: float = Field(ge=COVERAGE_SCORE_MIN, le=COVERAGE_SCORE_MAX)
    components: dict[str, float]

    @field_validator("components", mode="before")
    @classmethod
    def _components_are_bounded(cls, value):
        return _validate_component_score_map(value)


class CoverageMetadataPayload(BaseModel):
    """API-safe coverage metadata.

    This is an explanatory read-model shape. It is not provenance, not source
    truth, and not an objective market opportunity score.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _populate_additive_api_fields(cls, value):
        if not isinstance(value, dict):
            return value
        data = dict(value)
        tier = data.get("tier") or data.get("coverage_tier")
        label = data.get("label") or data.get("coverage_label")
        quality_score = data.get("quality_score")
        components = data.get("components")
        quality_payload = data.get("coverage_quality_score")
        if quality_score is None and isinstance(quality_payload, dict):
            quality_score = quality_payload.get("overall_score")
        if components is None and isinstance(quality_payload, dict):
            components = quality_payload.get("components")
        if tier is not None:
            data.setdefault("coverage_tier", tier)
            data.setdefault("coverage_description", coverage_description_for_tier(tier))
        if label is not None:
            data.setdefault("coverage_label", label)
        elif tier is not None:
            data.setdefault("coverage_label", coverage_label_for_tier(tier))
        if quality_score is not None and components is not None:
            data.setdefault(
                "coverage_quality_score",
                {
                    "overall_score": quality_score,
                    "components": components,
                },
            )
        if tier is not None:
            data.setdefault(
                "coverage_limitations",
                coverage_limitations_for_tier(tier, notes=data.get("notes") or ()),
            )
        return data

    @field_validator("components", mode="before")
    @classmethod
    def _components_are_bounded(cls, value):
        return _validate_component_score_map(value)

    tier: CoverageTier
    label: str
    quality_score: float = Field(ge=COVERAGE_SCORE_MIN, le=COVERAGE_SCORE_MAX)
    components: dict[str, float]
    coverage_tier: CoverageTier
    coverage_label: str
    coverage_description: str
    coverage_quality_score: CoverageQualityScorePayload
    coverage_limitations: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    heuristic: bool = True
    safe_for_confident_market_comparison: bool = False
    should_rank_as_confident_recommendation: bool = False


class SectorCoverageMetadataPayload(BaseModel):
    """API-safe sector coverage metadata, kept separate from overall coverage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sector: SectorCoverageCategory
    label: str
    coverage_level: SectorCoverageLevel = SectorCoverageLevel.UNKNOWN
    coverage: CoverageMetadataPayload


def coverage_label_for_tier(tier: CoverageTier | str) -> str:
    try:
        normalized = tier if isinstance(tier, CoverageTier) else CoverageTier(tier)
    except ValueError:
        return "Coverage unavailable"
    if normalized is CoverageTier.TIER_1:
        return "Tier 1 - fully covered market"
    if normalized is CoverageTier.TIER_2:
        return "Tier 2 - partial but useful market"
    if normalized is CoverageTier.TIER_3:
        return "Tier 3 - watchlist / emerging market"
    return "Tier 4 - placeholder only"


def coverage_description_for_tier(tier: CoverageTier | str) -> str:
    try:
        normalized = tier if isinstance(tier, CoverageTier) else CoverageTier(tier)
    except ValueError:
        return "Coverage metadata is unavailable for this response."
    if normalized is CoverageTier.TIER_1:
        return "This market has enough validated coverage for confident comparison."
    if normalized is CoverageTier.TIER_2:
        return (
            "This market is directionally useful, but one or more coverage "
            "signals are incomplete and must be treated as partial."
        )
    if normalized is CoverageTier.TIER_3:
        return (
            "This market is tracked as watchlist or emerging coverage and is "
            "not enough for confident recommendations."
        )
    return (
        "This market is placeholder only and should not be treated as analyzed "
        "market intelligence."
    )


def coverage_limitations_for_tier(
    tier: CoverageTier | str,
    *,
    notes: tuple[str, ...] | list[str] = (),
) -> list[str]:
    try:
        normalized = tier if isinstance(tier, CoverageTier) else CoverageTier(tier)
    except ValueError:
        normalized = CoverageTier.TIER_4
    limitations = [
        (
            "Coverage scoring is heuristic and should be read together with "
            "freshness and source metadata."
        )
    ]
    if normalized is CoverageTier.TIER_2:
        limitations.append("Coverage is partial; at least one signal class is incomplete.")
    elif normalized is CoverageTier.TIER_3:
        limitations.append(
            "Coverage is watchlist/emerging and is not a confident recommendation basis."
        )
    elif normalized is CoverageTier.TIER_4:
        limitations.append(
            "Coverage is placeholder-only and must not be presented as analyzed."
        )
    for note in notes:
        if note and note not in limitations:
            limitations.append(note)
    return limitations


def placeholder_coverage_metadata(*, note: str | None = None) -> CoverageMetadataPayload:
    notes = [note] if note else ["No coverage evidence is available on this surface."]
    zero_components = {
        "company_coverage": 0.0,
        "hiring_coverage": 0.0,
        "entry_level_coverage": 0.0,
        "freshness": 0.0,
        "source_diversity": 0.0,
        "confidence": 0.0,
    }
    return CoverageMetadataPayload(
        tier=CoverageTier.TIER_4,
        label=coverage_label_for_tier(CoverageTier.TIER_4),
        quality_score=0.0,
        components=zero_components,
        notes=notes,
        heuristic=True,
        safe_for_confident_market_comparison=False,
        should_rank_as_confident_recommendation=False,
    )


def _validate_component_score_map(value):
    if not isinstance(value, dict):
        return value
    for key, score in value.items():
        if isinstance(score, bool) or not isinstance(score, int | float):
            raise ValueError(f"coverage component {key!r} must be numeric")
        if score < COVERAGE_SCORE_MIN or score > COVERAGE_SCORE_MAX:
            raise ValueError(
                f"coverage component {key!r} must be between "
                f"{COVERAGE_SCORE_MIN:g} and {COVERAGE_SCORE_MAX:g}"
            )
    return value
