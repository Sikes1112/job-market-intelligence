"""Structured results for curated canonical imports."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from backend.imports.validation import ImportValidationIssue, ImportValidationResult

IMPORT_COUNT_KEYS: tuple[str, ...] = (
    "source_refs",
    "source_observations",
    "fact_source_links",
    "regions",
    "companies",
    "presence",
    "hiring",
    "entry_level",
)

POST_IMPORT_COUNT_KEYS: tuple[str, ...] = (
    "trust_assessments",
    "risk_routing_decisions",
    "entry_level_scores",
    "region_scores",
    "region_outputs",
    "company_outputs",
    "comparison_outputs",
)


@dataclass(frozen=True, slots=True)
class ImportWriteCounts:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    failed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "skipped": self.skipped,
            "failed": self.failed,
        }


@dataclass(frozen=True, slots=True)
class CuratedImportDiagnostic:
    code: str
    message: str
    stage: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "stage": self.stage,
        }


@dataclass(frozen=True, slots=True)
class CuratedMarketImportResult:
    ok: bool
    status: str
    dataset_path: str
    validation: ImportValidationResult
    counts: Mapping[str, ImportWriteCounts]
    diagnostics: tuple[CuratedImportDiagnostic, ...] = ()

    @property
    def validation_errors(self) -> tuple[ImportValidationIssue, ...]:
        return self.validation.errors

    def counts_as_dict(self) -> dict[str, dict[str, int]]:
        return {key: value.as_dict() for key, value in self.counts.items()}


@dataclass(frozen=True, slots=True)
class CuratedTrustLabel:
    subject_type: str
    subject_id: str
    trust_tier: str
    trust_label: str
    freshness_label: str
    risk_label: str | None
    ranking_influence_label: str
    ranking_influence_allowed: bool
    imported_data: bool
    source_backed: bool
    data_origin: str
    demonstration_data: bool

    def as_dict(self) -> dict[str, str | bool | None]:
        return {
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "trust_tier": self.trust_tier,
            "trust_label": self.trust_label,
            "freshness_label": self.freshness_label,
            "risk_label": self.risk_label,
            "ranking_influence_label": self.ranking_influence_label,
            "ranking_influence_allowed": self.ranking_influence_allowed,
            "imported_data": self.imported_data,
            "source_backed": self.source_backed,
            "data_origin": self.data_origin,
            "demonstration_data": self.demonstration_data,
        }


@dataclass(frozen=True, slots=True)
class CuratedMarketPostImportResult:
    ok: bool
    status: str
    dataset_path: str
    validation: ImportValidationResult
    counts: Mapping[str, ImportWriteCounts]
    trust_labels: tuple[CuratedTrustLabel, ...] = ()
    diagnostics: tuple[CuratedImportDiagnostic, ...] = ()

    @property
    def validation_errors(self) -> tuple[ImportValidationIssue, ...]:
        return self.validation.errors

    @property
    def warnings(self) -> tuple[CuratedImportDiagnostic, ...]:
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.code.startswith("warning_")
        )

    @property
    def errors(self) -> tuple[CuratedImportDiagnostic, ...]:
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if not diagnostic.code.startswith("warning_")
        )

    def counts_as_dict(self) -> dict[str, dict[str, int]]:
        return {key: value.as_dict() for key, value in self.counts.items()}


@dataclass(frozen=True, slots=True)
class CuratedMarketBatchResult:
    operation: str
    markets_processed: tuple[str, ...]
    markets_succeeded: tuple[str, ...]
    markets_failed: tuple[str, ...]
    per_market_results: Mapping[str, Any]
    total_created: int = 0
    total_updated: int = 0
    total_unchanged: int = 0
    total_skipped: int = 0
    total_failed: int = 0
    total_ranking_allowed: int = 0
    total_ranking_denied: int = 0
    warnings: tuple[CuratedImportDiagnostic, ...] = ()
    errors: tuple[CuratedImportDiagnostic, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.markets_failed and not self.errors

    def totals_as_dict(self) -> dict[str, int]:
        return {
            "created": self.total_created,
            "updated": self.total_updated,
            "unchanged": self.total_unchanged,
            "skipped": self.total_skipped,
            "failed": self.total_failed,
            "ranking_allowed": self.total_ranking_allowed,
            "ranking_denied": self.total_ranking_denied,
        }


def empty_import_counts() -> Mapping[str, ImportWriteCounts]:
    return MappingProxyType({key: ImportWriteCounts() for key in IMPORT_COUNT_KEYS})


def empty_post_import_counts() -> Mapping[str, ImportWriteCounts]:
    return MappingProxyType(
        {key: ImportWriteCounts() for key in POST_IMPORT_COUNT_KEYS}
    )
