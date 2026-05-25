"""Pydantic payload models for region / company / comparison outputs.

Shapes mirror ``docs/API_SURFACES.md`` §4 (region), §5 (company), and §6
(comparison) closely while staying purely structural — no chart configs,
no rendering hints, no frontend-specific layout keys.

The payload metadata block carries:

* ``state`` — the build-time outcome state (``fresh`` / ``partial`` /
  ``stale``). Distinct from the persisted :class:`OutputMetadata` row's
  state, which is governed by the :class:`backend.shared.state.ObjectState`
  transition graph.
* ``freshness_expires_at`` — minimum non-null freshness across inputs;
  may be ``None`` if no input carried freshness metadata.
* ``source_versions`` — deterministic JSON-safe dict capturing every
  input row's ``version`` that participated in the build.
* ``warnings`` — structured warnings using the existing
  :class:`backend.orchestration.jobs.errors.JobWarning` schema; no new
  warning vocabulary is introduced.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.geography.market_coverage import (
    CoverageMetadataPayload,
    SectorCoverageMetadataPayload,
    placeholder_coverage_metadata,
)
from backend.orchestration.jobs.errors import JobWarning

# ---------------------------------------------------------------------------
# Shared payload metadata
# ---------------------------------------------------------------------------


class OutputPayloadMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: str
    freshness_expires_at: datetime | None = None
    source_versions: dict[str, Any] = Field(default_factory=dict)
    warnings: list[JobWarning] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Shared building-block models
# ---------------------------------------------------------------------------


class RegionScoresPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    structural_ecosystem_score: float | None = None
    live_market_score: float | None = None
    objective_opportunity_score: float | None = None
    raw_total_score: float | None = None
    general_density_score: float | None = None
    tech_market_density_score: float | None = None
    early_career_accessibility_score: float | None = None
    score_ruleset_version: str | None = None


class RegionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    eligible_company_count: int
    major_tech_count: int
    mag7_count: int
    present_company_count: int
    currently_hiring_company_count: int


class CompanyEntry(BaseModel):
    """Compact company view inside region payloads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: str
    company_name: str
    sector_primary: str | None = None
    eligibility_status: str | None = None
    is_major_tech: bool = False
    is_mag7: bool = False
    prestige_score: float | None = None


class HiringCompanyEntry(BaseModel):
    """Company + hiring snapshot inside region payloads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: str
    company_name: str
    currently_hiring_flag: bool
    active_posting_count_now: int | None = None
    posting_count_30d: int | None = None
    posting_count_90d: int | None = None


class EntryLevelSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    internship_count_total: int | None = None
    coop_count_total: int | None = None
    entry_level_full_time_count_total: int | None = None
    formal_early_career_program_count: int = 0
    average_entry_level_access_score: float | None = None
    pairs_with_entry_level_access: int = 0


class MajorTechSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    count: int = 0
    company_ids: list[str] = Field(default_factory=list)


class Mag7Summary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    count: int = 0
    company_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Region output
# ---------------------------------------------------------------------------


class RegionOutputBody(BaseModel):
    """The ``region`` block per ``API_SURFACES.md`` §4."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str
    display_name: str
    region_type: str
    parent_region_id: str | None = None
    labor_market_group: str | None = None
    coverage: CoverageMetadataPayload = Field(
        default_factory=placeholder_coverage_metadata
    )
    sector_coverage: dict[str, SectorCoverageMetadataPayload] = Field(
        default_factory=dict
    )
    summary: RegionSummary
    scores: RegionScoresPayload | None = None
    top_companies_present: list[CompanyEntry] = Field(default_factory=list)
    top_companies_hiring: list[HiringCompanyEntry] = Field(default_factory=list)
    entry_level_summary: EntryLevelSummary
    major_tech_summary: MajorTechSummary
    mag7_summary: Mag7Summary


class RegionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region: RegionOutputBody
    metadata: OutputPayloadMetadata


# ---------------------------------------------------------------------------
# Company output
# ---------------------------------------------------------------------------


class CompanyRegionPresenceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str
    region_display_name: str
    presence_status: str
    presence_basis: str | None = None
    presence_confidence: str | None = None
    coverage: CoverageMetadataPayload = Field(
        default_factory=placeholder_coverage_metadata
    )
    sector_coverage: dict[str, SectorCoverageMetadataPayload] = Field(
        default_factory=dict
    )


class CompanyRegionHiringEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str
    region_display_name: str
    currently_hiring_flag: bool
    active_posting_count_now: int | None = None
    posting_count_30d: int | None = None
    posting_count_90d: int | None = None
    coverage: CoverageMetadataPayload = Field(
        default_factory=placeholder_coverage_metadata
    )
    sector_coverage: dict[str, SectorCoverageMetadataPayload] = Field(
        default_factory=dict
    )


class CompanyRegionEntryLevelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str
    region_display_name: str
    internship_count: int | None = None
    coop_count: int | None = None
    entry_level_full_time_count: int | None = None
    formal_early_career_program_flag: bool = False
    entry_level_access_score: float | None = None
    entry_level_confidence: str | None = None
    coverage: CoverageMetadataPayload = Field(
        default_factory=placeholder_coverage_metadata
    )
    sector_coverage: dict[str, SectorCoverageMetadataPayload] = Field(
        default_factory=dict
    )


class CompanyOutputBody(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: str
    company_name: str
    normalized_company_name: str
    sector_primary: str | None = None
    sector_secondary: str | None = None
    eligibility_status: str
    eligibility_override_flag: bool = False
    classification_confidence: str | None = None
    is_major_tech: bool = False
    is_mag7: bool = False
    prestige_score: float | None = None
    regions_present: list[CompanyRegionPresenceEntry] = Field(default_factory=list)
    regions_hiring: list[CompanyRegionHiringEntry] = Field(default_factory=list)
    entry_level_regions: list[CompanyRegionEntryLevelEntry] = Field(default_factory=list)


class CompanyOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    company: CompanyOutputBody
    metadata: OutputPayloadMetadata


# ---------------------------------------------------------------------------
# Comparison output
# ---------------------------------------------------------------------------


class ComparisonRegionSide(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str
    display_name: str
    scores: RegionScoresPayload | None = None
    coverage: CoverageMetadataPayload = Field(
        default_factory=placeholder_coverage_metadata
    )
    sector_coverage: dict[str, SectorCoverageMetadataPayload] = Field(
        default_factory=dict
    )


class ComparisonOutputBody(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_id: str
    region_a: ComparisonRegionSide
    region_b: ComparisonRegionSide
    # category_winners maps category-name -> winning region_id, or
    # ``None`` for an honest tie. Categories whose comparison cannot be
    # resolved (one or both sides missing the score) are omitted entirely.
    category_winners: dict[str, str | None] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ComparisonOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison: ComparisonOutputBody
    metadata: OutputPayloadMetadata
