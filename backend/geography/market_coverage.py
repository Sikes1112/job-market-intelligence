"""Market coverage metadata and conservative quality helpers.

This module is intentionally pure domain/config code. It does not create
canonical regions, scrape sources, run ingestion, or publish output. The
coverage structures here describe how broad market coverage should be tracked
as regions move from placeholder candidates to researched markets.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.shared.coverage_payloads import (
    COVERAGE_SCORE_MAX,
    COVERAGE_SCORE_MIN,
    CoverageMetadataPayload,
    CoverageTier,
    PriorityMarket,
    SectorCoverageCategory,
    SectorCoverageLevel,
    SectorCoverageMetadataPayload,
)
from backend.shared.coverage_payloads import (
    CoverageQualityScorePayload as CoverageQualityScorePayload,
)
from backend.shared.coverage_payloads import (
    coverage_description_for_tier as coverage_description_for_tier,
)
from backend.shared.coverage_payloads import (
    coverage_label_for_tier as coverage_label_for_tier,
)
from backend.shared.coverage_payloads import (
    coverage_limitations_for_tier as coverage_limitations_for_tier,
)


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class RegionExpansionPlaybookStep(_Vocabulary):
    SOURCE_COLLECTION = "source_collection"
    COMPANY_UNIVERSE_DEFINITION = "company_universe_definition"
    PRESENCE_VALIDATION = "presence_validation"
    HIRING_SIGNAL_COLLECTION = "hiring_signal_collection"
    ENTRY_LEVEL_SIGNAL_COLLECTION = "entry_level_signal_collection"
    FRESHNESS_CLASSIFICATION = "freshness_classification"
    AUDIT_PASS = "audit_pass"
    FRONTEND_RELEASE = "frontend_release"


class CoverageQualityLabel(_Vocabulary):
    STRONG = "strong"
    PARTIAL = "partial"
    WATCHLIST = "watchlist"
    PLACEHOLDER = "placeholder"


class RegionExpansionPlaybookStepDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    step: RegionExpansionPlaybookStep
    label: str
    completion_rule: str
    coverage_warning: str


class CoverageTierDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tier: CoverageTier
    label: str
    meaning: str
    required_conditions: tuple[str, ...]
    safe_for_confident_market_comparison: bool = False
    directionally_useful_for_comparison: bool = False
    requires_partial_label: bool = False
    should_rank_as_confident_recommendation: bool = False


class SectorCoverageDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sector: SectorCoverageCategory
    label: str


class SectorCoverageLevelDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    level: SectorCoverageLevel
    label: str
    meaning: str
    can_be_inferred_from_missing_evidence: bool = False
    can_be_displayed_as_strong: bool = False


class CoverageQualityScore(BaseModel):
    """Heuristic, bounded coverage quality components.

    Each component is a human/audit-assigned value in ``[0, 100]``. These are
    coverage-readiness estimates, not objective opportunity scores and not
    source-derived market facts. A zero means absent or not demonstrated, not a
    negative market finding.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    company_coverage: float = Field(ge=COVERAGE_SCORE_MIN, le=COVERAGE_SCORE_MAX)
    hiring_coverage: float = Field(ge=COVERAGE_SCORE_MIN, le=COVERAGE_SCORE_MAX)
    entry_level_coverage: float = Field(ge=COVERAGE_SCORE_MIN, le=COVERAGE_SCORE_MAX)
    freshness: float = Field(ge=COVERAGE_SCORE_MIN, le=COVERAGE_SCORE_MAX)
    source_diversity: float = Field(ge=COVERAGE_SCORE_MIN, le=COVERAGE_SCORE_MAX)
    confidence: float = Field(ge=COVERAGE_SCORE_MIN, le=COVERAGE_SCORE_MAX)
    notes: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def component_scores(self) -> dict[str, float]:
        return {
            "company_coverage": self.company_coverage,
            "hiring_coverage": self.hiring_coverage,
            "entry_level_coverage": self.entry_level_coverage,
            "freshness": self.freshness,
            "source_diversity": self.source_diversity,
            "confidence": self.confidence,
        }

    @property
    def total_score(self) -> float:
        return coverage_quality_total(self)

    @property
    def suggested_tier(self) -> CoverageTier:
        return suggest_coverage_tier(self)

    @property
    def quality_label(self) -> CoverageQualityLabel:
        return coverage_quality_label(self)


class SectorCoverageProfile(BaseModel):
    """Coverage state for one sector inside one region.

    Sector coverage is independent of overall region coverage. A region can be
    broad Tier 2 while one sector is Tier 1, or broad Tier 1 while a specific
    sector remains weak. The sector level is intentionally conservative:
    missing sector evidence defaults to unknown and cannot become strong
    without quality support.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    sector: SectorCoverageCategory
    coverage_tier: CoverageTier
    coverage_level: SectorCoverageLevel = SectorCoverageLevel.UNKNOWN
    quality_score: CoverageQualityScore | None = None
    notes: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _quality_must_support_declared_tier(self) -> SectorCoverageProfile:
        _validate_declared_quality(
            self.coverage_tier,
            self.quality_score,
            context=f"sector {self.sector.value}",
        )
        _validate_sector_coverage_level(self)
        return self


class RegionCoverageProfile(BaseModel):
    """Coverage state for a region plus optional sector-specific overlays."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1, max_length=64)
    overall_tier: CoverageTier
    overall_quality_score: CoverageQualityScore | None = None
    sector_coverage: dict[SectorCoverageCategory, SectorCoverageProfile] = Field(
        default_factory=dict
    )
    notes: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _quality_and_sector_keys_must_be_consistent(self) -> RegionCoverageProfile:
        _validate_declared_quality(
            self.overall_tier,
            self.overall_quality_score,
            context=f"region {self.region_id}",
        )
        for sector, profile in self.sector_coverage.items():
            if profile.sector is not sector:
                raise ValueError(
                    "sector coverage key must match profile sector: "
                    f"{sector.value!r} != {profile.sector.value!r}"
                )
        return self


def _priority_markets() -> tuple[PriorityMarket, ...]:
    return (
        PriorityMarket(rank=1, market_id="nyc", display_name="NYC"),
        PriorityMarket(rank=2, market_id="seattle", display_name="Seattle"),
        PriorityMarket(rank=3, market_id="austin", display_name="Austin"),
        PriorityMarket(rank=4, market_id="dc_nova", display_name="DC / NoVA"),
        PriorityMarket(rank=5, market_id="atlanta", display_name="Atlanta"),
        PriorityMarket(rank=6, market_id="chicago", display_name="Chicago"),
        PriorityMarket(rank=7, market_id="los_angeles", display_name="Los Angeles"),
        PriorityMarket(
            rank=8,
            market_id="raleigh_durham",
            display_name="Raleigh-Durham",
        ),
        PriorityMarket(
            rank=9,
            market_id="denver_boulder",
            display_name="Denver / Boulder",
        ),
        PriorityMarket(rank=10, market_id="boston", display_name="Boston"),
        PriorityMarket(
            rank=11,
            market_id="sf_bay_area",
            display_name="SF Bay Area",
        ),
        PriorityMarket(rank=12, market_id="dallas", display_name="Dallas"),
        PriorityMarket(rank=13, market_id="miami", display_name="Miami"),
        PriorityMarket(rank=14, market_id="pittsburgh", display_name="Pittsburgh"),
        PriorityMarket(rank=15, market_id="minneapolis", display_name="Minneapolis"),
    )


def _validate_priority_markets(
    markets: tuple[PriorityMarket, ...],
) -> tuple[PriorityMarket, ...]:
    ranks = [market.rank for market in markets]
    expected_ranks = list(range(1, len(markets) + 1))
    if ranks != expected_ranks:
        raise RuntimeError(
            f"priority market ranks must be contiguous and ordered: {ranks!r}"
        )
    market_ids = [market.market_id for market in markets]
    if len(market_ids) != len(set(market_ids)):
        raise RuntimeError("priority market ids must be unique")
    display_names = [market.display_name for market in markets]
    if len(display_names) != len(set(display_names)):
        raise RuntimeError("priority market display names must be unique")
    return markets


PRIORITY_MARKETS: tuple[PriorityMarket, ...] = _validate_priority_markets(
    _priority_markets()
)


REGION_EXPANSION_PLAYBOOK: tuple[RegionExpansionPlaybookStepDefinition, ...] = (
    RegionExpansionPlaybookStepDefinition(
        step=RegionExpansionPlaybookStep.SOURCE_COLLECTION,
        label="Source collection",
        completion_rule=(
            "Collect candidate official, public, or licensed sources and record "
            "source type, origin, license posture, collection date, and owner."
        ),
        coverage_warning="A source list alone does not make a region covered.",
    ),
    RegionExpansionPlaybookStepDefinition(
        step=RegionExpansionPlaybookStep.COMPANY_UNIVERSE_DEFINITION,
        label="Company universe definition",
        completion_rule=(
            "Define the candidate company universe for the labor market and "
            "document inclusion and exclusion criteria."
        ),
        coverage_warning="A candidate company list is not validated presence.",
    ),
    RegionExpansionPlaybookStepDefinition(
        step=RegionExpansionPlaybookStep.PRESENCE_VALIDATION,
        label="Presence validation",
        completion_rule=(
            "Attach evidence that companies are meaningfully present in the "
            "region before using them in regional coverage claims."
        ),
        coverage_warning="Unvalidated presence must not drive confident coverage.",
    ),
    RegionExpansionPlaybookStepDefinition(
        step=RegionExpansionPlaybookStep.HIRING_SIGNAL_COLLECTION,
        label="Hiring signal collection",
        completion_rule=(
            "Collect current hiring signals with observed-at timestamps and "
            "unknown-count handling for unavailable values."
        ),
        coverage_warning="Missing hiring signals keep the market partial or watchlist.",
    ),
    RegionExpansionPlaybookStepDefinition(
        step=RegionExpansionPlaybookStep.ENTRY_LEVEL_SIGNAL_COLLECTION,
        label="Entry-level signal collection",
        completion_rule=(
            "Collect internship, co-op, entry-level full-time, and formal early "
            "career program signals when available."
        ),
        coverage_warning="General hiring strength is not entry-level coverage.",
    ),
    RegionExpansionPlaybookStepDefinition(
        step=RegionExpansionPlaybookStep.FRESHNESS_CLASSIFICATION,
        label="Freshness classification",
        completion_rule=(
            "Classify collected facts against existing freshness windows and "
            "preserve stale, partial, and unknown states."
        ),
        coverage_warning="Unknown freshness cannot be presented as fresh.",
    ),
    RegionExpansionPlaybookStepDefinition(
        step=RegionExpansionPlaybookStep.AUDIT_PASS,
        label="Audit pass",
        completion_rule=(
            "Review provenance, source diversity, score components, boundaries, "
            "warnings, and admin approval before release."
        ),
        coverage_warning="Audit approval is required before public confidence claims.",
    ),
    RegionExpansionPlaybookStepDefinition(
        step=RegionExpansionPlaybookStep.FRONTEND_RELEASE,
        label="Frontend release",
        completion_rule=(
            "Expose the region only with its current coverage tier, warnings, "
            "freshness/source labels, and sector-specific coverage where known."
        ),
        coverage_warning=(
            "Frontend release does not upgrade a partial or placeholder market."
        ),
    ),
)


COVERAGE_TIER_DEFINITIONS: dict[CoverageTier, CoverageTierDefinition] = {
    CoverageTier.TIER_1: CoverageTierDefinition(
        tier=CoverageTier.TIER_1,
        label="Tier 1 - fully covered market",
        meaning="Full coverage for confident market comparison.",
        required_conditions=(
            "Strong company universe",
            "Presence validated",
            "Hiring signals present",
            "Entry-level signals present",
            "Freshness acceptable",
            "Multiple source types",
            "Safe for confident market comparison",
        ),
        safe_for_confident_market_comparison=True,
        directionally_useful_for_comparison=True,
        should_rank_as_confident_recommendation=True,
    ),
    CoverageTier.TIER_2: CoverageTierDefinition(
        tier=CoverageTier.TIER_2,
        label="Tier 2 - partial but useful market",
        meaning="Useful but incomplete coverage that must be labeled partial.",
        required_conditions=(
            "Directionally useful for comparison",
            "At least one signal class may be weaker or incomplete",
            "Must be labeled as partial",
        ),
        directionally_useful_for_comparison=True,
        requires_partial_label=True,
    ),
    CoverageTier.TIER_3: CoverageTierDefinition(
        tier=CoverageTier.TIER_3,
        label="Tier 3 - watchlist / emerging market",
        meaning="Tracked for future expansion, not enough for confident recommendations.",
        required_conditions=(
            "Watchlist or emerging market",
            "Not enough for confident recommendations",
        ),
    ),
    CoverageTier.TIER_4: CoverageTierDefinition(
        tier=CoverageTier.TIER_4,
        label="Tier 4 - placeholder only",
        meaning="Placeholder only; should not be presented as analyzed.",
        required_conditions=(
            "Should not be presented as analyzed",
            "Should not be ranked as a confident recommendation",
        ),
    ),
}


SECTOR_COVERAGE_DEFINITIONS: dict[
    SectorCoverageCategory, SectorCoverageDefinition
] = {
    SectorCoverageCategory.AI: SectorCoverageDefinition(
        sector=SectorCoverageCategory.AI, label="AI"
    ),
    SectorCoverageCategory.CLOUD: SectorCoverageDefinition(
        sector=SectorCoverageCategory.CLOUD, label="cloud"
    ),
    SectorCoverageCategory.CYBERSECURITY: SectorCoverageDefinition(
        sector=SectorCoverageCategory.CYBERSECURITY, label="cybersecurity"
    ),
    SectorCoverageCategory.FINTECH: SectorCoverageDefinition(
        sector=SectorCoverageCategory.FINTECH, label="fintech"
    ),
    SectorCoverageCategory.HEALTHTECH: SectorCoverageDefinition(
        sector=SectorCoverageCategory.HEALTHTECH, label="healthtech"
    ),
    SectorCoverageCategory.EDTECH: SectorCoverageDefinition(
        sector=SectorCoverageCategory.EDTECH, label="edtech"
    ),
    SectorCoverageCategory.ENTERPRISE_SAAS: SectorCoverageDefinition(
        sector=SectorCoverageCategory.ENTERPRISE_SAAS,
        label="enterprise SaaS",
    ),
    SectorCoverageCategory.PUBLIC_SECTOR_TECH: SectorCoverageDefinition(
        sector=SectorCoverageCategory.PUBLIC_SECTOR_TECH,
        label="public sector tech",
    ),
    SectorCoverageCategory.DEFENSE_TECH: SectorCoverageDefinition(
        sector=SectorCoverageCategory.DEFENSE_TECH,
        label="defense tech",
    ),
    SectorCoverageCategory.CONSUMER_TECH: SectorCoverageDefinition(
        sector=SectorCoverageCategory.CONSUMER_TECH,
        label="consumer tech",
    ),
}


def unknown_sector_coverage_metadata() -> dict[str, SectorCoverageMetadataPayload]:
    return {
        definition.sector.value: SectorCoverageMetadataPayload(
            sector=definition.sector,
            label=definition.label,
            coverage_level=SectorCoverageLevel.UNKNOWN,
            coverage=placeholder_coverage_metadata(
                note=(
                    "No sector-specific coverage evidence is available for "
                    f"{definition.label} in this region."
                )
            ),
        )
        for definition in SECTOR_COVERAGE_DEFINITIONS.values()
    }


SECTOR_COVERAGE_LEVEL_DEFINITIONS: dict[
    SectorCoverageLevel, SectorCoverageLevelDefinition
] = {
    SectorCoverageLevel.UNKNOWN: SectorCoverageLevelDefinition(
        level=SectorCoverageLevel.UNKNOWN,
        label="unknown",
        meaning="No sector-specific coverage evidence has been demonstrated.",
        can_be_inferred_from_missing_evidence=True,
    ),
    SectorCoverageLevel.LIMITED: SectorCoverageLevelDefinition(
        level=SectorCoverageLevel.LIMITED,
        label="limited",
        meaning="Some sector-specific evidence exists, but it is not enough for use.",
    ),
    SectorCoverageLevel.WATCHLIST: SectorCoverageLevelDefinition(
        level=SectorCoverageLevel.WATCHLIST,
        label="watchlist",
        meaning="Tracked sector signal exists, but coverage is not recommendation-ready.",
    ),
    SectorCoverageLevel.PARTIAL: SectorCoverageLevelDefinition(
        level=SectorCoverageLevel.PARTIAL,
        label="partial",
        meaning="Sector coverage is useful but incomplete and must be labeled partial.",
    ),
    SectorCoverageLevel.STRONG: SectorCoverageLevelDefinition(
        level=SectorCoverageLevel.STRONG,
        label="strong",
        meaning="Sector coverage is supported by strong validated coverage inputs.",
        can_be_displayed_as_strong=True,
    ),
}


COVERAGE_SCORE_DIMENSIONS: tuple[str, ...] = (
    "company_coverage",
    "hiring_coverage",
    "entry_level_coverage",
    "freshness",
    "source_diversity",
    "confidence",
)

_TIER_1_MINIMUMS: dict[str, float] = {
    "company_coverage": 75.0,
    "hiring_coverage": 75.0,
    "entry_level_coverage": 75.0,
    "freshness": 75.0,
    "source_diversity": 67.0,
    "confidence": 75.0,
}

_TIER_STRENGTH: dict[CoverageTier, int] = {
    CoverageTier.TIER_4: 1,
    CoverageTier.TIER_3: 2,
    CoverageTier.TIER_2: 3,
    CoverageTier.TIER_1: 4,
}

_ANALYZED_TIERS: frozenset[CoverageTier] = frozenset(
    {CoverageTier.TIER_1, CoverageTier.TIER_2}
)


def priority_market_by_id(market_id: str) -> PriorityMarket | None:
    for market in PRIORITY_MARKETS:
        if market.market_id == market_id:
            return market
    return None


def coverage_quality_total(score: CoverageQualityScore) -> float:
    return sum(score.component_scores.values()) / len(COVERAGE_SCORE_DIMENSIONS)


def quality_supports_tier_1(score: CoverageQualityScore) -> bool:
    return all(
        score.component_scores[dimension] >= minimum
        for dimension, minimum in _TIER_1_MINIMUMS.items()
    )


def suggest_coverage_tier(score: CoverageQualityScore) -> CoverageTier:
    if quality_supports_tier_1(score):
        return CoverageTier.TIER_1
    if (
        score.total_score >= 50.0
        and score.company_coverage >= 40.0
        and score.confidence >= 40.0
        and max(score.hiring_coverage, score.entry_level_coverage) >= 25.0
    ):
        return CoverageTier.TIER_2
    if any(value > 0 for value in score.component_scores.values()):
        return CoverageTier.TIER_3
    return CoverageTier.TIER_4


def coverage_quality_label(score: CoverageQualityScore) -> CoverageQualityLabel:
    tier = suggest_coverage_tier(score)
    if tier is CoverageTier.TIER_1:
        return CoverageQualityLabel.STRONG
    if tier is CoverageTier.TIER_2:
        return CoverageQualityLabel.PARTIAL
    if tier is CoverageTier.TIER_3:
        return CoverageQualityLabel.WATCHLIST
    return CoverageQualityLabel.PLACEHOLDER


def sector_coverage_level_from_quality(
    score: CoverageQualityScore | None,
) -> SectorCoverageLevel:
    if score is None:
        return SectorCoverageLevel.UNKNOWN
    tier = suggest_coverage_tier(score)
    if tier is CoverageTier.TIER_1:
        return SectorCoverageLevel.STRONG
    if tier is CoverageTier.TIER_2:
        return SectorCoverageLevel.PARTIAL
    if tier is CoverageTier.TIER_4:
        return SectorCoverageLevel.UNKNOWN
    if (
        max(
            score.company_coverage,
            score.hiring_coverage,
            score.entry_level_coverage,
        )
        >= 25.0
        and score.confidence >= 20.0
    ):
        return SectorCoverageLevel.WATCHLIST
    return SectorCoverageLevel.LIMITED


def coverage_metadata_from_quality(
    score: CoverageQualityScore,
    *,
    notes: tuple[str, ...] | list[str] = (),
) -> CoverageMetadataPayload:
    tier = score.suggested_tier
    definition = COVERAGE_TIER_DEFINITIONS[tier]
    components = {
        dimension: round(score.component_scores[dimension], 4)
        for dimension in COVERAGE_SCORE_DIMENSIONS
    }
    return CoverageMetadataPayload(
        tier=tier,
        label=definition.label,
        quality_score=round(score.total_score, 4),
        components=components,
        notes=list(notes or score.notes),
        heuristic=True,
        safe_for_confident_market_comparison=(
            definition.safe_for_confident_market_comparison
        ),
        should_rank_as_confident_recommendation=(
            definition.should_rank_as_confident_recommendation
        ),
    )


def placeholder_coverage_metadata(*, note: str | None = None) -> CoverageMetadataPayload:
    notes = [note] if note else ["No coverage evidence is available on this surface."]
    return coverage_metadata_from_quality(
        CoverageQualityScore(
            company_coverage=0.0,
            hiring_coverage=0.0,
            entry_level_coverage=0.0,
            freshness=0.0,
            source_diversity=0.0,
            confidence=0.0,
            notes=tuple(notes),
        )
    )


def build_region_coverage_metadata(
    *,
    present_company_count: int = 0,
    presence_record_count: int = 0,
    hiring_record_count: int = 0,
    entry_level_record_count: int = 0,
    has_region_score: bool = False,
    freshness_expires_at_known: bool = False,
    freshness_is_stale: bool = False,
    source_count: int = 0,
    source_data_basis: str | None = None,
    source_evidence_loaded: bool = False,
) -> CoverageMetadataPayload:
    """Build conservative coverage metadata from already-loaded read data.

    The component values are heuristic completeness indicators. They are bounded
    and intentionally coarse so API consumers can distinguish full, partial,
    watchlist, and placeholder coverage without reading them as precise market
    facts.
    """

    _reject_negative_counts(
        present_company_count=present_company_count,
        presence_record_count=presence_record_count,
        hiring_record_count=hiring_record_count,
        entry_level_record_count=entry_level_record_count,
        source_count=source_count,
    )

    notes: list[str] = []
    company_coverage = _company_coverage_component(
        present_company_count=present_company_count,
        presence_record_count=presence_record_count,
    )
    hiring_coverage = _signal_component(hiring_record_count)
    entry_level_coverage = _signal_component(entry_level_record_count)
    freshness = _freshness_component(
        freshness_expires_at_known=freshness_expires_at_known,
        freshness_is_stale=freshness_is_stale,
        source_data_basis=source_data_basis,
    )
    source_diversity = _source_diversity_component(
        source_count=source_count,
        source_data_basis=source_data_basis,
    )
    confidence = _confidence_component(
        has_region_score=has_region_score,
        company_coverage=company_coverage,
        hiring_coverage=hiring_coverage,
        entry_level_coverage=entry_level_coverage,
        source_diversity=source_diversity,
    )
    if not (
        has_region_score
        or present_company_count
        or presence_record_count
        or hiring_record_count
        or entry_level_record_count
        or source_count
    ):
        freshness = 0.0
        confidence = 0.0

    if not has_region_score:
        notes.append("No region market score is available for coverage context.")
    if present_company_count == 0:
        notes.append("No present company universe is demonstrated for this region.")
    if hiring_record_count == 0:
        notes.append("No hiring signal records are available for this region.")
    if entry_level_record_count == 0:
        notes.append("No entry-level signal records are available for this region.")
    if freshness_is_stale:
        notes.append("One or more freshness inputs are stale.")
    elif not freshness_expires_at_known:
        notes.append("Source freshness is unknown from the available coverage inputs.")
    if not source_evidence_loaded:
        notes.append(
            "Source diversity was not loaded for this surface; coverage remains heuristic."
        )
    elif source_count == 0:
        notes.append("No source evidence is attached for coverage scoring.")
    elif source_data_basis == "seeded_demo":
        notes.append("Seeded demo evidence does not count as real source diversity.")

    score = CoverageQualityScore(
        company_coverage=company_coverage,
        hiring_coverage=hiring_coverage,
        entry_level_coverage=entry_level_coverage,
        freshness=freshness,
        source_diversity=source_diversity,
        confidence=confidence,
        notes=tuple(notes),
    )
    return coverage_metadata_from_quality(score)


def declared_tier_is_supported(
    declared_tier: CoverageTier,
    quality_score: CoverageQualityScore,
) -> bool:
    suggested = suggest_coverage_tier(quality_score)
    return _TIER_STRENGTH[declared_tier] <= _TIER_STRENGTH[suggested]


def _validate_declared_quality(
    declared_tier: CoverageTier,
    quality_score: CoverageQualityScore | None,
    *,
    context: str,
) -> None:
    if declared_tier in _ANALYZED_TIERS and quality_score is None:
        raise ValueError(f"{context} {declared_tier.value} requires a quality score")
    if quality_score is None:
        return
    if not declared_tier_is_supported(declared_tier, quality_score):
        raise ValueError(
            f"{context} declared {declared_tier.value} is not supported by "
            f"heuristic coverage quality; suggested {quality_score.suggested_tier.value}"
        )


def _validate_sector_coverage_level(profile: SectorCoverageProfile) -> None:
    if profile.quality_score is None:
        if profile.coverage_level in {
            SectorCoverageLevel.UNKNOWN,
            SectorCoverageLevel.LIMITED,
        }:
            return
        raise ValueError(
            f"sector {profile.sector.value} {profile.coverage_level.value} "
            "requires a quality score"
        )

    inferred = sector_coverage_level_from_quality(profile.quality_score)
    if profile.coverage_level is SectorCoverageLevel.STRONG:
        if profile.coverage_tier is not CoverageTier.TIER_1:
            raise ValueError(
                f"sector {profile.sector.value} strong coverage requires tier_1"
            )
        if inferred is not SectorCoverageLevel.STRONG:
            raise ValueError(
                f"sector {profile.sector.value} strong coverage is not supported"
            )
    if profile.coverage_level is SectorCoverageLevel.PARTIAL and inferred not in {
        SectorCoverageLevel.PARTIAL,
        SectorCoverageLevel.STRONG,
    }:
        raise ValueError(
            f"sector {profile.sector.value} partial coverage is not supported"
        )
    if profile.coverage_level is SectorCoverageLevel.WATCHLIST and inferred in {
        SectorCoverageLevel.UNKNOWN,
        SectorCoverageLevel.LIMITED,
    }:
        raise ValueError(
            f"sector {profile.sector.value} watchlist coverage is not supported"
        )


def _reject_negative_counts(**counts: int) -> None:
    for name, value in counts.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{name} must be a non-negative int, got {value!r}")


def _company_coverage_component(
    *,
    present_company_count: int,
    presence_record_count: int,
) -> float:
    if present_company_count >= 10:
        return 90.0
    if present_company_count >= 3:
        return 72.0
    if present_company_count >= 1:
        return 50.0
    if presence_record_count >= 1:
        return 30.0
    return 0.0


def _signal_component(record_count: int) -> float:
    if record_count >= 10:
        return 90.0
    if record_count >= 3:
        return 72.0
    if record_count >= 1:
        return 58.0
    return 0.0


def _freshness_component(
    *,
    freshness_expires_at_known: bool,
    freshness_is_stale: bool,
    source_data_basis: str | None,
) -> float:
    if source_data_basis == "seeded_demo":
        return 10.0
    if freshness_is_stale:
        return 20.0
    if freshness_expires_at_known:
        return 80.0
    return 25.0


def _source_diversity_component(
    *,
    source_count: int,
    source_data_basis: str | None,
) -> float:
    if source_data_basis not in {"real_imported", "mixed"}:
        return 0.0
    if source_count >= 3:
        return 90.0
    if source_count == 2:
        return 67.0
    if source_count == 1:
        return 35.0
    return 0.0


def _confidence_component(
    *,
    has_region_score: bool,
    company_coverage: float,
    hiring_coverage: float,
    entry_level_coverage: float,
    source_diversity: float,
) -> float:
    if (
        has_region_score
        and company_coverage >= 72.0
        and hiring_coverage >= 58.0
        and entry_level_coverage >= 58.0
        and source_diversity >= 35.0
    ):
        return 80.0
    if has_region_score and company_coverage > 0 and (
        hiring_coverage > 0 or entry_level_coverage > 0
    ):
        return 58.0
    if has_region_score:
        return 40.0
    if company_coverage > 0 or hiring_coverage > 0 or entry_level_coverage > 0:
        return 25.0
    return 0.0
