"""Public-safe benchmark payload contracts for Layer 19C.

These payloads describe category-defining public benchmark artifacts. They do
not define canonical scoring formulas, recommendation ranking, market coverage
authority, or production benchmark/index score authority.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus

PublicBenchmarkDataBasis = Literal[
    "demo_template",
    "public_safe_summary",
    "mixed",
    "unknown",
]


class PublicBenchmarkLink(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=120)
    href: str = Field(min_length=1, max_length=255)
    link_type: Literal["benchmark", "report", "public_page"]

    @field_validator("label", "href")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _clean_text(value)


class PublicBenchmarkCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_name: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=160)
    period: str = Field(min_length=1, max_length=80)
    product_attribution: str = Field(min_length=1, max_length=160)
    public_path: str = Field(min_length=1, max_length=255)
    accessed_or_freshness_date: date

    @field_validator(
        "source_name",
        "title",
        "period",
        "product_attribution",
    )
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("public_path")
    @classmethod
    def _public_path_is_safe(cls, value: str) -> str:
        return _clean_public_path(value, expected_prefix="/benchmarks/")


class PublicBenchmarkShareSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=160)
    category_claim: str = Field(min_length=1, max_length=200)
    confidence_label: str = Field(min_length=1, max_length=80)
    freshness_label: str = Field(min_length=1, max_length=120)
    takeaway: str = Field(min_length=1, max_length=280)
    public_path: str = Field(min_length=1, max_length=255)
    warning: str = Field(min_length=1, max_length=240)

    @field_validator(
        "title",
        "category_claim",
        "confidence_label",
        "freshness_label",
        "takeaway",
        "warning",
    )
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("public_path")
    @classmethod
    def _public_path_is_safe(cls, value: str) -> str:
        return _clean_public_path(value, expected_prefix="/benchmarks/")


class PublicBenchmarkSourceAuthority(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    labels: tuple[str, ...] = Field(min_length=1, max_length=8)
    summary: str = Field(min_length=1, max_length=400)

    @field_validator("labels")
    @classmethod
    def _labels_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_text(item) for item in value)

    @field_validator("summary")
    @classmethod
    def _summary_not_blank(cls, value: str) -> str:
        return _clean_text(value)


class PublicBenchmarkInstitutionalCta(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=300)
    href: str = Field(min_length=1, max_length=255)
    link_type: Literal["public_page"]

    @field_validator("label", "body", "href")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("href")
    @classmethod
    def _href_is_public_path(cls, value: str) -> str:
        return _clean_public_path(value, expected_prefix="/")


class PublicBenchmarkSourceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_basis: PublicBenchmarkDataBasis
    source_count: int = Field(ge=0)
    source_categories: tuple[str, ...] = Field(min_length=1, max_length=12)
    provenance_notes: tuple[str, ...] = Field(min_length=1, max_length=12)

    @field_validator("source_categories", "provenance_notes")
    @classmethod
    def _strings_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_text(item) for item in value)


class PublicBenchmarkScoreDisplay(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=120)
    value: float | None = Field(default=None, ge=0.0, le=100.0)
    display_value: str = Field(min_length=1, max_length=80)
    score_basis: Literal["demo_static", "public_safe_summary", "unavailable"]
    caveat: str = Field(min_length=1, max_length=240)

    @field_validator("label", "display_value", "caveat")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _clean_text(value)


class PublicBenchmarkSubscore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    value: float | None = Field(default=None, ge=0.0, le=100.0)
    display_value: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=300)

    @field_validator("key", "label", "display_value", "explanation")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _clean_text(value)


class PublicBenchmarkMarketResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_type: Literal["featured", "ranked"]
    rank: int | None = Field(default=None, ge=1)
    market_id: str = Field(min_length=1, max_length=64)
    market_label: str = Field(min_length=1, max_length=120)
    score_display: PublicBenchmarkScoreDisplay
    subscores: tuple[PublicBenchmarkSubscore, ...] = Field(min_length=1, max_length=12)
    explanation: str = Field(min_length=1, max_length=700)
    warnings: tuple[str, ...] = Field(min_length=1, max_length=12)
    freshness_date: date
    confidence: Confidence
    source_provenance_summary: PublicBenchmarkSourceSummary

    @model_validator(mode="after")
    def _rank_matches_result_type(self) -> PublicBenchmarkMarketResult:
        if self.result_type == "ranked" and self.rank is None:
            raise ValueError("ranked benchmark results require rank")
        if self.result_type == "featured" and self.rank is not None:
            raise ValueError("featured benchmark results must not expose rank")
        return self

    @model_validator(mode="after")
    def _demo_result_is_labeled(self) -> PublicBenchmarkMarketResult:
        if self.source_provenance_summary.data_basis != "demo_template":
            return self
        text = " ".join(
            (
                self.score_display.display_value,
                self.score_display.caveat,
                self.explanation,
                *self.warnings,
            )
        ).lower()
        if "demo" not in text or "not production" not in text:
            raise ValueError("demo benchmark results must be labeled as not production-grade")
        if self.confidence not in {Confidence.LOW, Confidence.UNKNOWN}:
            raise ValueError("demo benchmark results must be low or unknown confidence")
        return self

    @field_validator("market_id", "market_label", "explanation")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("warnings")
    @classmethod
    def _tuple_strings_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_text(item) for item in value)


class PublicBenchmarkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    benchmark_id: str = Field(min_length=1, max_length=96)
    slug: str = Field(min_length=1, max_length=96)
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    period: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=800)
    methodology_summary: str = Field(min_length=1, max_length=1200)
    limitations: tuple[str, ...] = Field(min_length=1, max_length=12)
    freshness_date: date
    freshness_status: FreshnessStatus
    confidence: Confidence
    warnings: tuple[str, ...] = Field(min_length=1, max_length=12)
    market_results: tuple[PublicBenchmarkMarketResult, ...] = Field(
        min_length=1,
        max_length=25,
    )
    source_provenance_summary: PublicBenchmarkSourceSummary
    related_links: tuple[PublicBenchmarkLink, ...] = Field(
        default_factory=tuple,
        max_length=12,
    )
    suggested_citation: PublicBenchmarkCitation
    share_summary: PublicBenchmarkShareSummary
    source_authority: PublicBenchmarkSourceAuthority
    institutional_cta: PublicBenchmarkInstitutionalCta

    @model_validator(mode="after")
    def _demo_benchmark_is_labeled(self) -> PublicBenchmarkPayload:
        if self.source_provenance_summary.data_basis != "demo_template":
            return self
        text = " ".join(
            (
                self.summary,
                self.methodology_summary,
                *self.limitations,
                *self.warnings,
            )
        ).lower()
        if "demo-safe" not in text or "not production" not in text:
            raise ValueError("demo benchmark payloads must be clearly labeled")
        if self.confidence not in {Confidence.LOW, Confidence.UNKNOWN}:
            raise ValueError("demo benchmark payloads must be low or unknown confidence")
        return self

    @model_validator(mode="after")
    def _authority_surfaces_match_public_slug(self) -> PublicBenchmarkPayload:
        expected_path = f"/benchmarks/{self.slug}"
        if self.suggested_citation.public_path != expected_path:
            raise ValueError("suggested citation path must match public benchmark slug")
        if self.share_summary.public_path != expected_path:
            raise ValueError("share summary path must match public benchmark slug")
        labels = {label.lower() for label in self.source_authority.labels}
        required_labels = {"demo-safe", "low-confidence", "methodology-backed"}
        if not required_labels.issubset(labels):
            raise ValueError("source authority must disclose demo-safe methodology posture")
        return self

    @field_validator(
        "benchmark_id",
        "slug",
        "name",
        "category",
        "period",
        "summary",
        "methodology_summary",
    )
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("slug")
    @classmethod
    def _slug_is_public_stable(cls, value: str) -> str:
        if value != value.lower() or "_" in value or " " in value:
            raise ValueError("slug must be lowercase kebab-case")
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
        if any(char not in allowed for char in value):
            raise ValueError("slug contains unsupported characters")
        if value.startswith("-") or value.endswith("-") or "--" in value:
            raise ValueError("slug must be stable kebab-case")
        return value

    @field_validator("limitations", "warnings")
    @classmethod
    def _tuple_strings_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_text(item) for item in value)


class PublicBenchmarkSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    benchmark_id: str
    slug: str
    name: str
    category: str
    period: str
    summary: str
    freshness_date: date
    confidence: Confidence
    warnings: tuple[str, ...] = Field(default_factory=tuple)


class PublicBenchmarkListPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    benchmarks: tuple[PublicBenchmarkSummary, ...]


def _clean_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def _clean_public_path(value: str, *, expected_prefix: str) -> str:
    stripped = _clean_text(value)
    if not stripped.startswith(expected_prefix):
        raise ValueError("public path must use an allowed public route")
    lowered = stripped.lower()
    forbidden_tokens = (
        "public_report:",
        "public_benchmark:",
        "internal",
        "admin",
        "private",
        "source_id",
    )
    if any(token in lowered for token in forbidden_tokens):
        raise ValueError("public path must not expose internal identifiers")
    if any(char in stripped for char in (" ", "\t", "\n", "\r", "?", "#")):
        raise ValueError("public path must be a stable route path")
    return stripped
