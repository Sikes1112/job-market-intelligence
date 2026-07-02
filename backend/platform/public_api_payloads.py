"""Public-safe DTOs for Layer 20 Platform API responses.

These contracts are the external product surface. They intentionally avoid
raw scrape records, scoring ruleset fields, source identifiers, private user
data, institution-only data, billing records, and ingestion metadata.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.platform.product_catalog import PlatformApiProductId
from backend.shared.confidence import Confidence

PLATFORM_PUBLIC_API_VERSION = "v1"
PLATFORM_PUBLIC_API_SCHEMA_VERSION = "2026-06-20a"

PublicApiFreshnessStatus = Literal["fresh", "stale", "partial", "unknown"]
PublicApiDataBasis = Literal["public_safe_summary", "demo_template", "mixed", "unknown"]
PublicApiWarningSeverity = Literal["info", "low", "medium", "high"]

FORBIDDEN_PUBLIC_API_FIELD_NAMES = frozenset(
    {
        "admin_metadata",
        "api_key",
        "api_key_id",
        "billing_record",
        "billing_records",
        "classification_confidence",
        "eligibility_override_flag",
        "eligibility_override_reason",
        "eligibility_score",
        "fact_source_link_id",
        "formula_weights",
        "ingestion_metadata",
        "internal_formula_weights",
        "normalized_company_name",
        "observation_id",
        "output_id",
        "presence_id",
        "private_metadata",
        "prestige_score",
        "raw_job_record",
        "raw_job_records",
        "raw_scrape_record",
        "raw_scrape_records",
        "raw_source_refs",
        "raw_total_score",
        "recommendation_score",
        "region_score_id",
        "review_notes",
        "score_ruleset_version",
        "source_bundle_ref",
        "source_id",
        "source_ids",
        "source_ref_id",
        "source_refs",
        "source_version_bundle",
        "source_version_refs",
        "source_versions",
        "uploaded_by_user_id",
        "user_id",
    }
)


class PublicApiWarning(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=96)
    severity: PublicApiWarningSeverity = "info"
    message: str = Field(min_length=1, max_length=512)

    @field_validator("code", "message")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _clean_text(value)


class PublicApiFreshnessMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: PublicApiFreshnessStatus = "unknown"
    freshness_expires_at: datetime | None = None
    last_updated_at: datetime | None = None

    @field_validator("freshness_expires_at", "last_updated_at")
    @classmethod
    def _datetime_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("freshness datetime values must be timezone-aware")
        return value


class PublicApiConfidenceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    level: Confidence = Confidence.UNKNOWN
    label: str = Field(min_length=1, max_length=120)
    basis: Literal[
        "coverage_quality",
        "output_state",
        "aggregate_counts",
        "mixed",
        "unknown",
    ] = "unknown"

    @field_validator("label")
    @classmethod
    def _label_not_blank(cls, value: str) -> str:
        return _clean_text(value)


class PublicApiSourceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_basis: PublicApiDataBasis = "public_safe_summary"
    source_count: int = Field(default=0, ge=0)
    source_categories: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    notes: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @field_validator("source_categories", "notes")
    @classmethod
    def _tuple_strings_clean(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_text(item) for item in value if item.strip())


class PublicApiResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_version: Literal["v1"] = PLATFORM_PUBLIC_API_VERSION
    schema_version: Literal["2026-06-20a"] = PLATFORM_PUBLIC_API_SCHEMA_VERSION
    product_id: PlatformApiProductId
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    freshness: PublicApiFreshnessMetadata
    confidence: PublicApiConfidenceMetadata
    source_summary: PublicApiSourceSummary
    warnings: tuple[PublicApiWarning, ...] = Field(default_factory=tuple, max_length=24)


class PublicApiError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=96)
    message: str = Field(min_length=1, max_length=512)

    @field_validator("code", "message")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _clean_text(value)


class PublicApiEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["success", "partial", "error"]
    data: Any = None
    meta: PublicApiResponseMeta
    error: PublicApiError | None = None

    @model_validator(mode="after")
    def _envelope_is_safe(self) -> PublicApiEnvelope:
        found = find_forbidden_public_api_fields(self.model_dump(mode="python"))
        if found:
            raise ValueError(f"public API payload includes forbidden fields: {found!r}")
        if self.status == "error" and self.error is None:
            raise ValueError("error responses require an error object")
        if self.status != "error" and self.error is not None:
            raise ValueError("successful responses must not carry an error object")
        return self


class PublicScoreSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity: float | None = None
    structural_ecosystem: float | None = None
    live_market: float | None = None
    general_density: float | None = None
    tech_market_density: float | None = None
    early_career_access: float | None = None


class PublicRegionMarketSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    present_company_count: int = Field(ge=0)
    currently_hiring_company_count: int = Field(ge=0)
    early_career_signal_count: int = Field(ge=0)


class PublicRegionScoresPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1, max_length=64)
    region_name: str = Field(min_length=1, max_length=128)
    region_type: str = Field(min_length=1, max_length=64)
    score_scale: Literal["0_to_1"] = "0_to_1"
    scores: PublicScoreSet
    market_summary: PublicRegionMarketSummary
    coverage_tier: str = Field(min_length=1, max_length=64)
    coverage_label: str = Field(min_length=1, max_length=128)


class PublicCompanyRegionGeography(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1, max_length=64)
    region_name: str = Field(min_length=1, max_length=128)
    presence_status: str | None = Field(default=None, max_length=64)
    current_hiring: bool = False
    active_posting_count: int | None = Field(default=None, ge=0)
    has_early_career_access: bool = False
    early_career_access_score: float | None = None
    coverage_tier: str = Field(min_length=1, max_length=64)
    coverage_label: str = Field(min_length=1, max_length=128)


class PublicCompanyGeographyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: str = Field(min_length=1, max_length=64)
    company_name: str = Field(min_length=1, max_length=255)
    sector: str | None = Field(default=None, max_length=64)
    regions: tuple[PublicCompanyRegionGeography, ...] = Field(default_factory=tuple)
    region_count: int = Field(ge=0)


class PublicEarlyCareerAccessPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1, max_length=64)
    region_name: str = Field(min_length=1, max_length=128)
    early_career_access_score: float | None = None
    internship_count: int | None = Field(default=None, ge=0)
    coop_count: int | None = Field(default=None, ge=0)
    entry_level_full_time_count: int | None = Field(default=None, ge=0)
    formal_early_career_program_count: int = Field(ge=0)
    company_pairs_with_access: int = Field(ge=0)
    coverage_tier: str = Field(min_length=1, max_length=64)
    coverage_label: str = Field(min_length=1, max_length=128)


class PublicHiringConcentrationMarket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1, max_length=64)
    region_name: str = Field(min_length=1, max_length=128)
    currently_hiring_company_count: int = Field(ge=0)
    active_posting_count: int | None = Field(default=None, ge=0)
    posting_count_30d: int | None = Field(default=None, ge=0)
    posting_count_90d: int | None = Field(default=None, ge=0)
    concentration_share: float | None = Field(default=None, ge=0.0, le=1.0)


class PublicHiringConcentrationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    markets: tuple[PublicHiringConcentrationMarket, ...] = Field(default_factory=tuple)
    market_count: int = Field(ge=0)
    total_active_posting_count: int | None = Field(default=None, ge=0)


class PublicComparisonRegion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1, max_length=64)
    region_name: str = Field(min_length=1, max_length=128)
    scores: PublicScoreSet
    coverage_tier: str = Field(min_length=1, max_length=64)
    coverage_label: str = Field(min_length=1, max_length=128)


class PublicScoreComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: Literal[
        "opportunity",
        "structural_ecosystem",
        "live_market",
        "general_density",
        "tech_market_density",
        "early_career_access",
    ]
    region_a_value: float | None = None
    region_b_value: float | None = None
    winner_region_id: str | None = Field(default=None, max_length=64)


class PublicMarketComparisonPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_id: str = Field(min_length=1, max_length=160)
    region_a: PublicComparisonRegion
    region_b: PublicComparisonRegion
    score_comparisons: tuple[PublicScoreComparison, ...] = Field(default_factory=tuple)
    notes: tuple[str, ...] = Field(default_factory=tuple, max_length=12)


def build_public_api_envelope(
    *,
    product_id: PlatformApiProductId,
    data: Any,
    freshness: PublicApiFreshnessMetadata,
    confidence: PublicApiConfidenceMetadata,
    source_summary: PublicApiSourceSummary,
    warnings: tuple[PublicApiWarning, ...] = (),
    status: Literal["success", "partial"] = "success",
) -> PublicApiEnvelope:
    return PublicApiEnvelope(
        status=status,
        data=data,
        meta=PublicApiResponseMeta(
            product_id=product_id,
            freshness=freshness,
            confidence=confidence,
            source_summary=source_summary,
            warnings=warnings,
        ),
        error=None,
    )


def build_public_api_error_envelope(
    *,
    product_id: PlatformApiProductId,
    code: str,
    message: str,
    warnings: tuple[PublicApiWarning, ...] = (),
) -> PublicApiEnvelope:
    return PublicApiEnvelope(
        status="error",
        data=None,
        meta=PublicApiResponseMeta(
            product_id=product_id,
            freshness=PublicApiFreshnessMetadata(status="unknown"),
            confidence=PublicApiConfidenceMetadata(
                level=Confidence.UNKNOWN,
                label="Unknown",
                basis="unknown",
            ),
            source_summary=PublicApiSourceSummary(
                data_basis="unknown",
                source_count=0,
                source_categories=(),
                notes=("No public payload was returned.",),
            ),
            warnings=warnings,
        ),
        error=PublicApiError(code=code, message=message),
    )


def find_forbidden_public_api_fields(value: Any, path: str = "") -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in FORBIDDEN_PUBLIC_API_FIELD_NAMES:
                found.append(child_path)
            found.extend(find_forbidden_public_api_fields(child, child_path))
    elif isinstance(value, list | tuple):
        for index, child in enumerate(value):
            found.extend(find_forbidden_public_api_fields(child, f"{path}[{index}]"))
    return tuple(found)


def _clean_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped
