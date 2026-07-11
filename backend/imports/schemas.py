"""Public-safe schemas for curated import operations diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class MarketHealthStatus(_Vocabulary):
    HEALTHY = "healthy"
    NEEDS_REFRESH = "needs_refresh"
    LIMITED_COVERAGE = "limited_coverage"
    STALE_SOURCES = "stale_sources"
    VALIDATION_FAILED = "validation_failed"
    RANKING_LIMITED = "ranking_limited"


class OperationalSourceFreshnessStatus(_Vocabulary):
    CURRENT = "current"
    AGING = "aging"
    STALE = "stale"
    EXPIRED = "expired"
    NEEDS_REVIEW = "needs_review"


class RefreshReadinessStatus(_Vocabulary):
    READY = "ready"
    NEEDS_SOURCE_REFRESH = "needs_source_refresh"
    NEEDS_COVERAGE_EXPANSION = "needs_coverage_expansion"
    NEEDS_VALIDATION_FIX = "needs_validation_fix"
    NEEDS_RANKING_REVIEW = "needs_ranking_review"
    NOT_READY = "not_ready"


class GapSeverity(_Vocabulary):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DiffRisk(_Vocabulary):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKING = "blocking"


class FactArea(_Vocabulary):
    MARKET_IDENTITY = "market_identity"
    REGION = "region"
    COMPANY = "company"
    SOURCE = "source"
    PRESENCE = "presence"
    HIRING = "hiring"
    ENTRY_LEVEL = "entry_level"


class RankingExclusionCategory(_Vocabulary):
    STALE_SOURCE = "stale_source"
    LOW_CONFIDENCE = "low_confidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNSUPPORTED_FRESHNESS = "unsupported_freshness"
    SOURCE_NOT_ALLOWED = "source_not_allowed"
    MISSING_SOURCE = "missing_source"
    TRUST_OR_RISK_LIMITED = "trust_or_risk_limited"
    UNASSESSED = "unassessed"
    DEFAULT_DENIED = "default_denied"


class MaintenancePriority(_Vocabulary):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class PublicDTO:
    def as_dict(self) -> dict[str, Any]:
        return {field.name: _json_safe(getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class PublicIssue(PublicDTO):
    code: str
    message: str
    severity: str | None = None
    field: str | None = None
    file: str | None = None
    record_id: str | None = None


@dataclass(frozen=True, slots=True)
class MarketOperationalCounts(PublicDTO):
    company_count: int = 0
    source_count: int = 0
    presence_fact_count: int = 0
    hiring_fact_count: int = 0
    entry_level_fact_count: int = 0
    total_fact_count: int = 0
    unknown_fact_count: int = 0
    observed_zero_fact_count: int = 0
    ranking_eligible_fact_count: int = 0
    ranking_excluded_fact_count: int = 0
    stale_fact_count: int = 0
    stale_source_count: int = 0


@dataclass(frozen=True, slots=True)
class SourceDiagnostic(PublicDTO):
    source_id: str
    source_label: str
    source_type: str
    observed_date: str | None
    collected_date: str | None
    age_days: int | None
    freshness_status: OperationalSourceFreshnessStatus
    is_stale: bool
    license_or_terms_category: str | None
    fact_usage_count: int
    affected_areas: tuple[str, ...]
    affects_ranking_eligibility: bool
    impact: str


@dataclass(frozen=True, slots=True)
class SourceAgingReport(PublicDTO):
    market_key: str
    source_count: int
    stale_source_count: int
    aging_source_count: int
    expired_source_count: int
    oldest_source_age_days: int | None
    newest_source_age_days: int | None
    oldest_sources: tuple[SourceDiagnostic, ...]
    greatest_fact_impact_sources: tuple[SourceDiagnostic, ...]
    important_stale_sources: tuple[SourceDiagnostic, ...]
    sources: tuple[SourceDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class FactHealthFinding(PublicDTO):
    fact_type: str
    fact_id: str
    company_id: str | None
    region_id: str | None
    area: FactArea
    ranking_eligible: bool
    ranking_excluded_reasons: tuple[str, ...]
    freshness_status: str
    confidence: str
    observation_status: str
    source_count: int
    public_message: str


@dataclass(frozen=True, slots=True)
class FactHealthReport(PublicDTO):
    market_key: str
    total_facts: int
    ranking_eligible_facts: int
    ranking_excluded_facts: int
    stale_facts: int
    low_confidence_facts: int
    unknown_facts: int
    observed_zero_facts: int
    missing_useful_dimension_facts: int
    weak_source_coverage_facts: int
    trust_or_risk_limited_facts: int
    limiting_categories: tuple[str, ...]
    findings: tuple[FactHealthFinding, ...]


@dataclass(frozen=True, slots=True)
class CoverageGap(PublicDTO):
    gap_code: str
    severity: GapSeverity
    market_key: str
    affected_area: FactArea
    message: str
    supporting_counts: dict[str, int | float | str | None]
    recommended_action: str
    estimated_impact: str


@dataclass(frozen=True, slots=True)
class CoverageGapReport(PublicDTO):
    market_key: str
    gap_count: int
    highest_severity: GapSeverity | None
    gaps: tuple[CoverageGap, ...]


@dataclass(frozen=True, slots=True)
class RankingExclusionDiagnostic(PublicDTO):
    fact_type: str
    fact_id: str
    area: FactArea
    reason_categories: tuple[RankingExclusionCategory, ...]
    explanation: str


@dataclass(frozen=True, slots=True)
class RankingExclusionReport(PublicDTO):
    market_key: str
    excluded_fact_count: int
    total_fact_count: int
    ranking_limited_ratio: float
    affected_areas: tuple[str, ...]
    reason_counts: dict[str, int]
    stale_source_exclusion_count: int
    low_confidence_exclusion_count: int
    insufficient_evidence_exclusion_count: int
    unsupported_freshness_exclusion_count: int
    trust_or_risk_limitation_count: int
    diagnostics: tuple[RankingExclusionDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class DatasetHealthReport(PublicDTO):
    market_key: str
    market_name: str
    validation_ok: bool
    missing_required_files: tuple[str, ...]
    counts: MarketOperationalCounts
    oldest_source_age_days: int | None
    newest_source_age_days: int | None
    coverage_summary: str
    freshness_summary: str
    health_status: MarketHealthStatus
    reasons: tuple[str, ...]
    recommended_next_action: str


@dataclass(frozen=True, slots=True)
class RefreshReadinessReport(PublicDTO):
    market_key: str
    readiness_status: RefreshReadinessStatus
    blocking_conditions: tuple[str, ...]
    warnings: tuple[str, ...]
    recommended_next_action: str
    ordered_actions: tuple[str, ...]
    reasons: tuple[str, ...]
    expected_impact: str
    maintenance_priority: MaintenancePriority
    priority_score: int


@dataclass(frozen=True, slots=True)
class PlatformImportedMarketSummary(PublicDTO):
    registered_market_count: int
    healthy_market_count: int
    markets_needing_refresh: int
    markets_with_limited_coverage: int
    markets_with_stale_sources: int
    total_stale_source_count: int
    total_ranking_excluded_fact_count: int
    highest_priority_maintenance_market: str | None
    recommended_next_maintenance_action: str
    overall_health_status: MarketHealthStatus


@dataclass(frozen=True, slots=True)
class ImportDiffChange(PublicDTO):
    area: FactArea
    change_type: str
    record_id: str
    field: str | None
    before: Any
    after: Any
    message: str


@dataclass(frozen=True, slots=True)
class ImportDiffWarning(PublicDTO):
    code: str
    severity: DiffRisk
    area: FactArea
    record_id: str | None
    message: str


@dataclass(frozen=True, slots=True)
class ImportDiffPreview(PublicDTO):
    market_key: str
    validation_ok: bool
    overall_diff_risk: DiffRisk
    risk_reasons: tuple[str, ...]
    blocking_issues: tuple[ImportDiffWarning, ...]
    warnings: tuple[ImportDiffWarning, ...]
    summary_counts: dict[str, int]
    narrative_summary: str
    changes: tuple[ImportDiffChange, ...]


def _json_safe(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, MappingProxyType):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_safe(item) for item in value]
    if is_dataclass(value):
        return {field.name: _json_safe(getattr(value, field.name)) for field in fields(value)}
    return value
