"""Public-safe report payload contracts for Layer 19B.

These payloads describe public market-intelligence report artifacts. They do
not define scoring formulas, benchmark indices, recommendation ranking, or
canonical market authority.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus


class PublicReportLink(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=120)
    href: str = Field(min_length=1, max_length=255)
    link_type: Literal["report", "public_page"]

    @field_validator("label", "href")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _clean_text(value)


class PublicReportCitation(BaseModel):
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
        return _clean_public_path(value, expected_prefix="/reports/")


class PublicReportShareSummary(BaseModel):
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
        return _clean_public_path(value, expected_prefix="/reports/")


class PublicReportSourceAuthority(BaseModel):
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


class PublicReportInstitutionalCta(BaseModel):
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


class PublicSourceProvenanceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_basis: Literal["demo_template", "public_safe_summary", "mixed", "unknown"]
    source_count: int = Field(ge=0)
    source_categories: tuple[str, ...] = Field(min_length=1, max_length=12)
    provenance_notes: tuple[str, ...] = Field(min_length=1, max_length=12)

    @field_validator("source_categories", "provenance_notes")
    @classmethod
    def _strings_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_text(item) for item in value)


class PublicReportMarket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    market_id: str = Field(min_length=1, max_length=64)
    market_label: str = Field(min_length=1, max_length=120)
    coverage_note: str = Field(min_length=1, max_length=240)

    @field_validator("market_id", "market_label", "coverage_note")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _clean_text(value)


class PublicReportMarketResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_type: Literal["featured", "ranked"]
    rank: int | None = Field(default=None, ge=1)
    market_id: str = Field(min_length=1, max_length=64)
    market_label: str = Field(min_length=1, max_length=120)
    headline: str = Field(min_length=1, max_length=160)
    rationale: str = Field(min_length=1, max_length=600)
    evidence_signals: tuple[str, ...] = Field(min_length=1, max_length=12)
    freshness_date: date
    confidence: Confidence
    warnings: tuple[str, ...] = Field(max_length=12)
    source_provenance_summary: PublicSourceProvenanceSummary

    @model_validator(mode="after")
    def _rank_matches_result_type(self) -> PublicReportMarketResult:
        if self.result_type == "ranked" and self.rank is None:
            raise ValueError("ranked results require rank")
        if self.result_type == "featured" and self.rank is not None:
            raise ValueError("featured results must not expose rank")
        return self

    @field_validator("market_id", "market_label", "headline", "rationale")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("evidence_signals", "warnings")
    @classmethod
    def _tuple_strings_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_clean_text(item) for item in value)


class PublicReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: str = Field(min_length=1, max_length=96)
    slug: str = Field(min_length=1, max_length=96)
    title: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    report_period: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=800)
    markets_covered: tuple[PublicReportMarket, ...] = Field(min_length=1, max_length=25)
    market_results: tuple[PublicReportMarketResult, ...] = Field(min_length=1, max_length=25)
    methodology_summary: str = Field(min_length=1, max_length=1200)
    limitations: tuple[str, ...] = Field(min_length=1, max_length=12)
    freshness_date: date
    freshness_status: FreshnessStatus
    confidence: Confidence
    warnings: tuple[str, ...] = Field(max_length=12)
    source_provenance_summary: PublicSourceProvenanceSummary
    related_links: tuple[PublicReportLink, ...] = Field(default_factory=tuple, max_length=12)
    suggested_citation: PublicReportCitation
    share_summary: PublicReportShareSummary
    source_authority: PublicReportSourceAuthority
    institutional_cta: PublicReportInstitutionalCta

    @model_validator(mode="after")
    def _result_markets_must_be_covered(self) -> PublicReportPayload:
        covered = {market.market_id for market in self.markets_covered}
        missing = [
            result.market_id
            for result in self.market_results
            if result.market_id not in covered
        ]
        if missing:
            raise ValueError(f"market result references uncovered market(s): {missing!r}")
        return self

    @model_validator(mode="after")
    def _authority_surfaces_match_public_slug(self) -> PublicReportPayload:
        expected_path = f"/reports/{self.slug}"
        if self.suggested_citation.public_path != expected_path:
            raise ValueError("suggested citation path must match public report slug")
        if self.share_summary.public_path != expected_path:
            raise ValueError("share summary path must match public report slug")
        labels = {label.lower() for label in self.source_authority.labels}
        required_labels = {"demo-safe", "low-confidence", "methodology-backed"}
        if not required_labels.issubset(labels):
            raise ValueError("source authority must disclose demo-safe methodology posture")
        return self

    @field_validator(
        "report_id",
        "slug",
        "title",
        "category",
        "report_period",
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


class PublicReportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: str
    slug: str
    title: str
    category: str
    report_period: str
    summary: str
    freshness_date: date
    confidence: Confidence
    warnings: tuple[str, ...] = Field(default_factory=tuple)


class PublicReportListPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reports: tuple[PublicReportSummary, ...]


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
