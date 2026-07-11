"""Bulk operations for registered curated market datasets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

from sqlalchemy.orm import Session

from backend.imports.post_import import run_curated_market_post_import
from backend.imports.provenance import IMPORT_STALENESS_DAYS
from backend.imports.registry import (
    CuratedMarketRegistryEntry,
    MarketRegistryIssue,
    validate_market_registry,
)
from backend.imports.result import (
    CuratedImportDiagnostic,
    CuratedMarketBatchResult,
    CuratedMarketImportResult,
    CuratedMarketPostImportResult,
    ImportWriteCounts,
)
from backend.imports.service import import_curated_market_dataset
from backend.imports.validation import validate_curated_market_dataset


def validate_all_registered_market_datasets(
    *,
    registry_path: str | Path | None = None,
    as_of: date | datetime | None = None,
    stale_after_days: int = IMPORT_STALENESS_DAYS,
) -> CuratedMarketBatchResult:
    registry_result = validate_market_registry(registry_path)
    if not registry_result.ok:
        return _registry_error_result("validate", registry_result.errors)

    per_market: dict[str, Any] = {}
    succeeded: list[str] = []
    failed: list[str] = []
    errors: list[CuratedImportDiagnostic] = []
    warnings: list[CuratedImportDiagnostic] = []

    for entry in _ready_entries(registry_result.entries):
        result = validate_curated_market_dataset(
            entry.market_key,
            registry_path=registry_path,
            as_of=as_of,
            stale_after_days=stale_after_days,
        )
        per_market[entry.market_key] = result
        if result.ok:
            succeeded.append(entry.market_key)
        else:
            failed.append(entry.market_key)
            errors.extend(
                _validation_diagnostics(entry.market_key, result.errors)
            )

    return CuratedMarketBatchResult(
        operation="validate",
        markets_processed=tuple(per_market),
        markets_succeeded=tuple(succeeded),
        markets_failed=tuple(failed),
        per_market_results=MappingProxyType(per_market),
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def import_all_curated_market_datasets(
    session: Session,
    *,
    registry_path: str | Path | None = None,
    as_of: date | datetime | None = None,
    stale_after_days: int = IMPORT_STALENESS_DAYS,
) -> CuratedMarketBatchResult:
    registry_result = validate_market_registry(registry_path)
    if not registry_result.ok:
        return _registry_error_result("import", registry_result.errors)

    per_market: dict[str, CuratedMarketImportResult] = {}
    for entry in _ready_entries(registry_result.entries):
        per_market[entry.market_key] = import_curated_market_dataset(
            session,
            entry.market_key,
            registry_path=registry_path,
            as_of=as_of,
            stale_after_days=stale_after_days,
        )
    return _batch_result(
        operation="import",
        per_market=per_market,
    )


def run_all_curated_market_post_imports(
    session: Session,
    *,
    registry_path: str | Path | None = None,
    as_of: date | datetime | None = None,
    stale_after_days: int = IMPORT_STALENESS_DAYS,
    comparison_region_ids_by_market: Mapping[str, Sequence[str]] | None = None,
) -> CuratedMarketBatchResult:
    return _run_post_import_batch(
        session,
        operation="post_import",
        registry_path=registry_path,
        as_of=as_of,
        stale_after_days=stale_after_days,
        comparison_region_ids_by_market=comparison_region_ids_by_market,
    )


def rebuild_all_curated_market_outputs(
    session: Session,
    *,
    registry_path: str | Path | None = None,
    as_of: date | datetime | None = None,
    stale_after_days: int = IMPORT_STALENESS_DAYS,
    comparison_region_ids_by_market: Mapping[str, Sequence[str]] | None = None,
) -> CuratedMarketBatchResult:
    return _run_post_import_batch(
        session,
        operation="output_rebuild",
        registry_path=registry_path,
        as_of=as_of,
        stale_after_days=stale_after_days,
        comparison_region_ids_by_market=comparison_region_ids_by_market,
    )


def _run_post_import_batch(
    session: Session,
    *,
    operation: str,
    registry_path: str | Path | None,
    as_of: date | datetime | None,
    stale_after_days: int,
    comparison_region_ids_by_market: Mapping[str, Sequence[str]] | None,
) -> CuratedMarketBatchResult:
    registry_result = validate_market_registry(registry_path)
    if not registry_result.ok:
        return _registry_error_result(operation, registry_result.errors)

    ready_entries = _ready_entries(registry_result.entries)
    default_comparisons = _default_comparison_regions(ready_entries)
    per_market: dict[str, CuratedMarketPostImportResult] = {}
    for entry in ready_entries:
        comparison_ids = (
            comparison_region_ids_by_market.get(entry.market_key, ())
            if comparison_region_ids_by_market is not None
            else default_comparisons[entry.market_key]
        )
        per_market[entry.market_key] = run_curated_market_post_import(
            session,
            entry.market_key,
            registry_path=registry_path,
            as_of=as_of,
            stale_after_days=stale_after_days,
            comparison_region_ids=tuple(comparison_ids),
        )
    return _batch_result(operation=operation, per_market=per_market)


def _ready_entries(
    entries: tuple[CuratedMarketRegistryEntry, ...],
) -> tuple[CuratedMarketRegistryEntry, ...]:
    return tuple(entry for entry in entries if entry.import_status == "ready")


def _default_comparison_regions(
    entries: tuple[CuratedMarketRegistryEntry, ...],
) -> dict[str, tuple[str, ...]]:
    return {
        entry.market_key: tuple(
            peer.region_id for peer in entries if peer.market_key != entry.market_key
        )
        for entry in entries
    }


def _batch_result(
    *,
    operation: str,
    per_market: Mapping[str, CuratedMarketImportResult | CuratedMarketPostImportResult],
) -> CuratedMarketBatchResult:
    succeeded: list[str] = []
    failed: list[str] = []
    warnings: list[CuratedImportDiagnostic] = []
    errors: list[CuratedImportDiagnostic] = []
    totals = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "failed": 0}
    ranking_allowed = 0
    ranking_denied = 0

    for market_key, result in per_market.items():
        if result.ok:
            succeeded.append(market_key)
        else:
            failed.append(market_key)
        for counts in result.counts.values():
            _add_counts(totals, counts)
        diagnostics = getattr(result, "diagnostics", ())
        for diagnostic in diagnostics:
            if diagnostic.code.startswith("warning_"):
                warnings.append(diagnostic)
            else:
                errors.append(diagnostic)
        if not result.ok and getattr(result, "validation_errors", ()):
            errors.extend(
                _validation_diagnostics(market_key, result.validation_errors)
            )
        trust_labels = getattr(result, "trust_labels", ())
        ranking_allowed += sum(
            1 for label in trust_labels if label.ranking_influence_allowed
        )
        ranking_denied += sum(
            1 for label in trust_labels if not label.ranking_influence_allowed
        )

    return CuratedMarketBatchResult(
        operation=operation,
        markets_processed=tuple(per_market),
        markets_succeeded=tuple(succeeded),
        markets_failed=tuple(failed),
        per_market_results=MappingProxyType(dict(per_market)),
        total_created=totals["created"],
        total_updated=totals["updated"],
        total_unchanged=totals["unchanged"],
        total_skipped=totals["skipped"],
        total_failed=totals["failed"],
        total_ranking_allowed=ranking_allowed,
        total_ranking_denied=ranking_denied,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def _add_counts(totals: dict[str, int], counts: ImportWriteCounts) -> None:
    totals["created"] += counts.created
    totals["updated"] += counts.updated
    totals["unchanged"] += counts.unchanged
    totals["skipped"] += counts.skipped
    totals["failed"] += counts.failed


def _registry_error_result(
    operation: str,
    errors: tuple[MarketRegistryIssue, ...],
) -> CuratedMarketBatchResult:
    diagnostics = tuple(
        CuratedImportDiagnostic(
            code=issue.code,
            message=issue.message,
            stage="market_registry",
        )
        for issue in errors
    )
    return CuratedMarketBatchResult(
        operation=operation,
        markets_processed=(),
        markets_succeeded=(),
        markets_failed=(),
        per_market_results=MappingProxyType({}),
        errors=diagnostics,
    )


def _validation_diagnostics(
    market_key: str,
    errors,
) -> tuple[CuratedImportDiagnostic, ...]:
    return tuple(
        CuratedImportDiagnostic(
            code=issue.code,
            message=f"{market_key}: {issue.file}: {issue.message}",
            stage="validation",
        )
        for issue in errors
    )
