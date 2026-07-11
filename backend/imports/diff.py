"""Deterministic read-only import diff preview for curated market files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.imports.operations import (
    EXPIRED_AFTER_DAYS,
    FACT_SUBJECT_TYPES,
    MarketOperationalSnapshot,
    build_market_operational_snapshot,
)
from backend.imports.provenance import (
    ALLOWED_LICENSE_OR_TERMS_CATEGORIES,
    ALLOWED_SOURCE_TYPES,
    IMPORT_STALENESS_DAYS,
    parse_import_date,
)
from backend.imports.schemas import (
    DiffRisk,
    FactArea,
    ImportDiffChange,
    ImportDiffPreview,
    ImportDiffWarning,
    OperationalSourceFreshnessStatus,
)
from backend.imports.service import (
    _aggregate_counts,
    _count_value,
    _entry_level_id,
    _hiring_groups,
    _hiring_id,
    _load_dataset,
    _presence_id,
)
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus
from backend.shared.provenance import (
    FactBindingType,
    LicenseTermsCategory,
    ObservationStatus,
    SourceType,
)
from backend.trust.risk import RiskRoutingService
from backend.trust.schemas import TrustSubjectMetadata
from backend.trust.service import TrustAssessmentService

_OBSERVED_ZERO = ObservationStatus.ZERO_OBSERVED.value
_UNKNOWN_LIKE = {
    ObservationStatus.UNKNOWN.value,
    ObservationStatus.NOT_COLLECTED.value,
    ObservationStatus.NOT_APPLICABLE.value,
}


@dataclass(frozen=True, slots=True)
class _ProposedFact:
    fact_type: str
    fact_id: str
    area: FactArea
    company_id: str | None
    region_id: str | None
    values: dict[str, Any]
    source_ids: tuple[str, ...]


def build_import_diff_preview(
    session: Session,
    market_key: str,
    *,
    registry_path: str | Path | None = None,
    as_of: date | datetime | None = None,
) -> ImportDiffPreview:
    snapshot = build_market_operational_snapshot(
        session,
        market_key,
        registry_path=registry_path,
        as_of=as_of,
    )
    dataset = _safe_load_dataset(snapshot.registry_entry.dataset_path)
    changes: list[ImportDiffChange] = []
    warnings: list[ImportDiffWarning] = []
    blocking: list[ImportDiffWarning] = []
    counts: dict[str, int] = _empty_summary_counts()

    if not snapshot.validation.ok:
        issue = ImportDiffWarning(
            code="validation_failure_in_proposed_files",
            severity=DiffRisk.BLOCKING,
            area=FactArea.MARKET_IDENTITY,
            record_id=snapshot.market_key,
            message="Current curated files do not pass import validation.",
        )
        blocking.append(issue)
        counts["validation_errors"] = len(snapshot.validation.errors)

    if dataset is None:
        blocking.append(
            ImportDiffWarning(
                code="proposed_files_unavailable",
                severity=DiffRisk.BLOCKING,
                area=FactArea.MARKET_IDENTITY,
                record_id=snapshot.market_key,
                message="Current curated files could not be loaded for preview.",
            )
        )
        risk = _overall_risk(blocking, warnings, changes)
        return _preview(snapshot, risk, blocking, warnings, changes, counts)

    proposed_sources = dict(sorted(dataset.source_refs.items()))
    _diff_regions(snapshot, dataset.regions, changes, warnings, blocking, counts)
    _diff_companies(snapshot, dataset.companies, changes, warnings, counts)
    _diff_sources(snapshot, proposed_sources, changes, warnings, blocking, counts, as_of=as_of)
    try:
        proposed_facts = _proposed_facts(dataset)
    except (KeyError, ValueError):
        proposed_facts = {}
        blocking.append(
            ImportDiffWarning(
                code="proposed_fact_parse_failure",
                severity=DiffRisk.BLOCKING,
                area=FactArea.MARKET_IDENTITY,
                record_id=snapshot.market_key,
                message="Proposed fact rows could not be parsed for diff preview.",
            )
        )
    _diff_fact_area(
        snapshot,
        proposed_facts=proposed_facts,
        area=FactArea.PRESENCE,
        changes=changes,
        warnings=warnings,
        blocking=blocking,
        counts=counts,
        source_rows=proposed_sources,
        as_of=as_of,
    )
    _diff_fact_area(
        snapshot,
        proposed_facts=proposed_facts,
        area=FactArea.HIRING,
        changes=changes,
        warnings=warnings,
        blocking=blocking,
        counts=counts,
        source_rows=proposed_sources,
        as_of=as_of,
    )
    _diff_fact_area(
        snapshot,
        proposed_facts=proposed_facts,
        area=FactArea.ENTRY_LEVEL,
        changes=changes,
        warnings=warnings,
        blocking=blocking,
        counts=counts,
        source_rows=proposed_sources,
        as_of=as_of,
    )
    _detect_cross_market_leakage(snapshot, proposed_facts, warnings, blocking)

    changes = sorted(
        changes,
        key=lambda item: (
            item.area.value,
            item.record_id,
            item.field or "",
            item.change_type,
        ),
    )
    warnings = sorted(
        warnings,
        key=lambda item: (item.severity.value, item.code, item.record_id or ""),
    )
    blocking = sorted(blocking, key=lambda item: (item.code, item.record_id or ""))
    risk = _overall_risk(blocking, warnings, changes)
    return _preview(snapshot, risk, blocking, warnings, changes, counts)


def _preview(
    snapshot: MarketOperationalSnapshot,
    risk: DiffRisk,
    blocking: list[ImportDiffWarning],
    warnings: list[ImportDiffWarning],
    changes: list[ImportDiffChange],
    counts: dict[str, int],
) -> ImportDiffPreview:
    risk_reasons = tuple(sorted({issue.code for issue in (*blocking, *warnings)}))
    return ImportDiffPreview(
        market_key=snapshot.market_key,
        validation_ok=snapshot.validation.ok,
        overall_diff_risk=risk,
        risk_reasons=risk_reasons,
        blocking_issues=tuple(blocking),
        warnings=tuple(warnings),
        summary_counts=dict(sorted(counts.items())),
        narrative_summary=_narrative(counts, risk),
        changes=tuple(changes),
    )


def _safe_load_dataset(dataset_path: Path) -> Any | None:
    try:
        return _load_dataset(dataset_path)
    except (OSError, UnicodeError, ValueError, KeyError):
        return None


def _diff_regions(
    snapshot: MarketOperationalSnapshot,
    proposed_regions: tuple[dict[str, Any], ...],
    changes: list[ImportDiffChange],
    warnings: list[ImportDiffWarning],
    blocking: list[ImportDiffWarning],
    counts: dict[str, int],
) -> None:
    proposed_by_id = {
        _text(row.get("region_id")): row for row in proposed_regions if _text(row.get("region_id"))
    }
    if set(proposed_by_id) != {snapshot.region_id}:
        blocking.append(
            ImportDiffWarning(
                code="region_id_mismatch",
                severity=DiffRisk.BLOCKING,
                area=FactArea.REGION,
                record_id=snapshot.region_id,
                message="Proposed region IDs do not match the registered market region.",
            )
        )
    proposed = proposed_by_id.get(snapshot.region_id)
    if snapshot.region is None or proposed is None:
        return
    current = {
        "region_name": snapshot.region.region_name,
        "region_type": snapshot.region.region_type,
    }
    proposed_values = {
        "region_name": _text(proposed.get("region_name")),
        "region_type": _text(proposed.get("region_type")),
    }
    for field, before in current.items():
        after = proposed_values[field]
        if before != after:
            counts["region_changes"] += 1
            changes.append(
                _change(
                    FactArea.REGION,
                    "changed",
                    snapshot.region_id,
                    field,
                    before,
                    after,
                    f"Region {field} would change.",
                )
            )
    if any(
        _text(row.get("source_ref"))
        and not _text(row.get("source_ref")).startswith(f"src_{snapshot.market_key}_")
        for row in proposed_regions
    ):
        warnings.append(
            ImportDiffWarning(
                code="market_key_mismatch",
                severity=DiffRisk.BLOCKING,
                area=FactArea.MARKET_IDENTITY,
                record_id=snapshot.market_key,
                message="One or more region source references do not match the market key.",
            )
        )


def _diff_companies(
    snapshot: MarketOperationalSnapshot,
    proposed_companies: tuple[dict[str, str], ...],
    changes: list[ImportDiffChange],
    warnings: list[ImportDiffWarning],
    counts: dict[str, int],
) -> None:
    current_by_id = {company.company_id: company for company in snapshot.companies}
    proposed_by_id = {
        _text(row.get("company_id")): row
        for row in proposed_companies
        if _text(row.get("company_id"))
    }
    for company_id in sorted(set(proposed_by_id) - set(current_by_id)):
        counts["companies_added"] += 1
        changes.append(
            _change(
                FactArea.COMPANY,
                "added",
                company_id,
                None,
                None,
                _company_public(proposed_by_id[company_id]),
                "Company would be added.",
            )
        )
    for company_id in sorted(set(current_by_id) - set(proposed_by_id)):
        counts["companies_missing_from_source"] += 1
        changes.append(
            _change(
                FactArea.COMPANY,
                "missing_from_source",
                company_id,
                None,
                _company_current_public(current_by_id[company_id]),
                None,
                "Canonical company is absent from current source files.",
            )
        )
    current_names = {
        company.normalized_company_name: company.company_id for company in snapshot.companies
    }
    for proposed_id, row in sorted(proposed_by_id.items()):
        normalized = _text(row.get("company_name")).lower()
        existing_id = current_names.get(normalized)
        if existing_id and existing_id != proposed_id:
            warnings.append(
                ImportDiffWarning(
                    code="company_id_identity_mismatch",
                    severity=DiffRisk.HIGH,
                    area=FactArea.COMPANY,
                    record_id=proposed_id,
                    message=(
                        "Proposed company name matches an existing company with a different ID."
                    ),
                )
            )
    for company_id in sorted(set(current_by_id) & set(proposed_by_id)):
        current = _company_current_public(current_by_id[company_id])
        proposed = _company_public(proposed_by_id[company_id])
        if current == proposed:
            counts["companies_unchanged"] += 1
            continue
        counts["companies_changed"] += 1
        for field in sorted(current):
            if current[field] != proposed[field]:
                changes.append(
                    _change(
                        FactArea.COMPANY,
                        "changed",
                        company_id,
                        field,
                        current[field],
                        proposed[field],
                        f"Company {field} would change.",
                    )
                )


def _diff_sources(
    snapshot: MarketOperationalSnapshot,
    proposed_sources: dict[str, dict[str, str]],
    changes: list[ImportDiffChange],
    warnings: list[ImportDiffWarning],
    blocking: list[ImportDiffWarning],
    counts: dict[str, int],
    *,
    as_of: date | datetime | None,
) -> None:
    current_by_id = snapshot.source_by_id
    for source_id in sorted(set(proposed_sources) - set(current_by_id)):
        counts["source_references_added"] += 1
        changes.append(
            _change(
                FactArea.SOURCE,
                "added",
                source_id,
                None,
                None,
                _source_public(proposed_sources[source_id]),
                "Source reference would be added.",
            )
        )
    for source_id in sorted(set(current_by_id) - set(proposed_sources)):
        counts["source_references_absent_from_files"] += 1
        source = current_by_id[source_id]
        changes.append(
            _change(
                FactArea.SOURCE,
                "absent_from_files",
                source_id,
                None,
                _source_current_public(source),
                None,
                "Canonical source reference is absent from current source files.",
            )
        )
        if source.fact_refs:
            warnings.append(
                ImportDiffWarning(
                    code="source_removed_still_used",
                    severity=DiffRisk.HIGH,
                    area=FactArea.SOURCE,
                    record_id=source_id,
                    message="A source absent from files is still used by canonical facts.",
                )
            )
            counts["removed_sources_still_used"] += 1
    for source_id in sorted(set(current_by_id) & set(proposed_sources)):
        current = _source_current_public(current_by_id[source_id])
        proposed = _source_public(proposed_sources[source_id])
        if current == proposed:
            counts["source_references_unchanged"] += 1
        else:
            counts["source_references_changed"] += 1
            for field in sorted(current):
                if current[field] != proposed[field]:
                    changes.append(
                        _change(
                            FactArea.SOURCE,
                            "changed",
                            source_id,
                            field,
                            current[field],
                            proposed[field],
                            f"Source {field} would change.",
                        )
                    )
        proposed_status = _proposed_source_status(proposed_sources[source_id], as_of=as_of)
        current_status = current_by_id[source_id].freshness_status
        if current_status in {
            OperationalSourceFreshnessStatus.CURRENT,
            OperationalSourceFreshnessStatus.AGING,
        } and proposed_status in {
            OperationalSourceFreshnessStatus.STALE,
            OperationalSourceFreshnessStatus.EXPIRED,
        }:
            warnings.append(
                ImportDiffWarning(
                    code="fresh_source_becoming_stale",
                    severity=DiffRisk.HIGH,
                    area=FactArea.SOURCE,
                    record_id=source_id,
                    message="A current source would become stale or expired.",
                )
            )
            counts["freshness_degradations"] += 1
    if any(
        _text(row.get("source_ref"))
        and not _text(row.get("source_ref")).startswith(f"src_{snapshot.market_key}_")
        for row in proposed_sources.values()
    ):
        blocking.append(
            ImportDiffWarning(
                code="market_key_mismatch",
                severity=DiffRisk.BLOCKING,
                area=FactArea.MARKET_IDENTITY,
                record_id=snapshot.market_key,
                message="One or more source references do not belong to the market key.",
            )
        )


def _diff_fact_area(
    snapshot: MarketOperationalSnapshot,
    *,
    proposed_facts: dict[tuple[str, str], _ProposedFact],
    area: FactArea,
    changes: list[ImportDiffChange],
    warnings: list[ImportDiffWarning],
    blocking: list[ImportDiffWarning],
    counts: dict[str, int],
    source_rows: dict[str, dict[str, str]],
    as_of: date | datetime | None,
) -> None:
    current = {(fact.fact_type, fact.fact_id): fact for fact in snapshot.facts if fact.area is area}
    current_values = _current_fact_values(snapshot, area)
    proposed = {key: fact for key, fact in proposed_facts.items() if fact.area is area}
    prefix = {
        FactArea.PRESENCE: "presence_facts",
        FactArea.HIRING: "hiring_facts",
        FactArea.ENTRY_LEVEL: "entry_level_facts",
    }[area]
    for key in sorted(set(proposed) - set(current)):
        counts[f"{prefix}_added"] += 1
        changes.append(
            _change(area, "added", key[1], None, None, proposed[key].values, "Fact would be added.")
        )
    for key in sorted(set(current) - set(proposed)):
        counts[f"{prefix}_absent_from_source"] += 1
        changes.append(
            _change(
                area,
                "absent_from_source",
                key[1],
                None,
                current_values.get(key, _fact_current_public(current[key])),
                None,
                "Canonical fact is absent from current source files.",
            )
        )
    for key in sorted(set(current) & set(proposed)):
        before = current_values.get(key, _fact_current_public(current[key]))
        after = proposed[key].values
        before_sources = tuple(current[key].source_ids)
        after_sources = proposed[key].source_ids
        comparable_before = {k: v for k, v in before.items() if k in after}
        if comparable_before == after and before_sources == after_sources:
            counts[f"{prefix}_unchanged"] += 1
        else:
            counts[f"{prefix}_changed"] += 1
            for field in sorted(after):
                if comparable_before.get(field) != after[field]:
                    changes.append(
                        _change(
                            area,
                            "changed",
                            key[1],
                            field,
                            comparable_before.get(field),
                            after[field],
                            f"{area.value} fact {field} would change.",
                        )
                    )
                    _semantic_count_warning(
                        area,
                        key[1],
                        field,
                        comparable_before.get(field),
                        after[field],
                        warnings,
                        counts,
                    )
            if before_sources != after_sources:
                counts["source_association_changes"] += 1
                changes.append(
                    _change(
                        area,
                        "source_association_changed",
                        key[1],
                        "source_ids",
                        before_sources,
                        after_sources,
                        "Fact source association would change.",
                    )
                )
        proposed_allowed = _proposed_ranking_allowed(
            proposed[key],
            source_rows=source_rows,
            as_of=as_of,
        )
        if current[key].ranking_eligible and not proposed_allowed:
            counts["ranking_eligible_to_excluded"] += 1
            warnings.append(
                ImportDiffWarning(
                    code="ranking_eligible_becoming_excluded",
                    severity=DiffRisk.HIGH,
                    area=area,
                    record_id=key[1],
                    message="A currently ranking-eligible fact would become ranking-excluded.",
                )
            )
        if current[key].ranking_excluded and proposed_allowed:
            counts["ranking_excluded_to_eligible"] += 1
            warnings.append(
                ImportDiffWarning(
                    code="ranking_excluded_becoming_eligible",
                    severity=DiffRisk.MEDIUM,
                    area=area,
                    record_id=key[1],
                    message="A currently ranking-excluded fact would become ranking-eligible.",
                )
            )


def _detect_cross_market_leakage(
    snapshot: MarketOperationalSnapshot,
    proposed_facts: dict[tuple[str, str], _ProposedFact],
    warnings: list[ImportDiffWarning],
    blocking: list[ImportDiffWarning],
) -> None:
    for fact in proposed_facts.values():
        if fact.region_id and fact.region_id != snapshot.region_id:
            blocking.append(
                ImportDiffWarning(
                    code="fact_moving_across_market_scope",
                    severity=DiffRisk.BLOCKING,
                    area=fact.area,
                    record_id=fact.fact_id,
                    message=(
                        "A proposed fact is scoped to a different region than the "
                        "registered market."
                    ),
                )
            )
        if any(
            source_id and not source_id.startswith(f"src_{snapshot.market_key}_")
            for source_id in fact.source_ids
        ):
            warnings.append(
                ImportDiffWarning(
                    code="cross_market_fact_leakage",
                    severity=DiffRisk.BLOCKING,
                    area=fact.area,
                    record_id=fact.fact_id,
                    message="A proposed fact uses a source reference from another market.",
                )
            )


def _proposed_facts(dataset: Any) -> dict[tuple[str, str], _ProposedFact]:
    facts: dict[tuple[str, str], _ProposedFact] = {}
    for row in dataset.presence:
        company_id = _text(row.get("company_id"))
        region_id = _text(row.get("region_id"))
        fact_id = _presence_id(company_id, region_id)
        facts[(FactBindingType.COMPANY_REGION_PRESENCE.value, fact_id)] = _ProposedFact(
            fact_type=FactBindingType.COMPANY_REGION_PRESENCE.value,
            fact_id=fact_id,
            area=FactArea.PRESENCE,
            company_id=company_id,
            region_id=region_id,
            values={
                "presence_status": _text(row.get("presence_status")),
                "presence_basis": _text(row.get("presence_basis")),
            },
            source_ids=(_text(row.get("source_ref")),),
        )
    for group in _hiring_groups(dataset.hiring):
        counts = [
            _count_value(row, "active_posting_count", "active_posting_count_status")
            for row in group.rows
        ]
        active = _aggregate_counts(counts)
        fact_id = _hiring_id(group.company_id, group.region_id)
        facts[(FactBindingType.COMPANY_REGION_HIRING.value, fact_id)] = _ProposedFact(
            fact_type=FactBindingType.COMPANY_REGION_HIRING.value,
            fact_id=fact_id,
            area=FactArea.HIRING,
            company_id=group.company_id,
            region_id=group.region_id,
            values={
                "active_posting_count_now": active.value,
                "active_posting_count_now_status": active.status.value,
                "annualized_trend_signal": _single_or_unknown(
                    tuple(row["annualized_trend_signal"] for row in group.rows)
                ),
                "seasonal_student_hiring_signal": _single_or_unknown(
                    tuple(row["seasonal_student_hiring_signal"] for row in group.rows)
                ),
            },
            source_ids=tuple(sorted({row["source_ref"] for row in group.rows})),
        )
    for row in dataset.entry_level:
        company_id = _text(row.get("company_id"))
        region_id = _text(row.get("region_id"))
        fact_id = _entry_level_id(company_id, region_id)
        facts[(FactBindingType.COMPANY_REGION_ENTRY_LEVEL.value, fact_id)] = _ProposedFact(
            fact_type=FactBindingType.COMPANY_REGION_ENTRY_LEVEL.value,
            fact_id=fact_id,
            area=FactArea.ENTRY_LEVEL,
            company_id=company_id,
            region_id=region_id,
            values={
                "internship_count": _count_value(
                    row,
                    "internship_count",
                    "internship_count_status",
                ).value,
                "internship_count_status": _text(row.get("internship_count_status")),
                "coop_count": _count_value(row, "coop_count", "coop_count_status").value,
                "coop_count_status": _text(row.get("coop_count_status")),
                "entry_level_full_time_count": _count_value(
                    row,
                    "entry_level_full_time_count",
                    "entry_level_full_time_count_status",
                ).value,
                "entry_level_full_time_count_status": _text(
                    row.get("entry_level_full_time_count_status")
                ),
                "formal_early_career_program_flag": _text(
                    row.get("formal_early_career_program_flag")
                )
                == "true",
                "student_season_recurrence_signal": _text(
                    row.get("student_season_recurrence_signal")
                ),
            },
            source_ids=(_text(row.get("source_ref")),),
        )
    return dict(sorted(facts.items()))


def _fact_current_public(fact) -> dict[str, Any]:
    if fact.area is FactArea.PRESENCE:
        return {
            "presence_status": fact.observation_status,
        }
    if fact.area is FactArea.HIRING:
        return {
            "active_posting_count_now_status": fact.observation_status,
        }
    if fact.area is FactArea.ENTRY_LEVEL:
        return {
            "observation_status": fact.observation_status,
        }
    return {"observation_status": fact.observation_status}


def _current_fact_values(
    snapshot: MarketOperationalSnapshot,
    area: FactArea,
) -> dict[tuple[str, str], dict[str, Any]]:
    if area is FactArea.PRESENCE:
        return {
            (FactBindingType.COMPANY_REGION_PRESENCE.value, row.presence_id): {
                "presence_status": row.presence_status,
                "presence_basis": row.presence_basis,
            }
            for row in snapshot.presence_facts
        }
    if area is FactArea.HIRING:
        return {
            (FactBindingType.COMPANY_REGION_HIRING.value, row.hiring_id): {
                "active_posting_count_now": row.active_posting_count_now,
                "active_posting_count_now_status": row.active_posting_count_now_status,
                "annualized_trend_signal": row.annualized_trend_signal,
                "seasonal_student_hiring_signal": row.seasonal_student_hiring_signal,
                "posting_count_30d": row.posting_count_30d,
                "posting_count_30d_status": row.posting_count_30d_status,
                "posting_count_90d": row.posting_count_90d,
                "posting_count_90d_status": row.posting_count_90d_status,
            }
            for row in snapshot.hiring_facts
        }
    if area is FactArea.ENTRY_LEVEL:
        return {
            (FactBindingType.COMPANY_REGION_ENTRY_LEVEL.value, row.entry_level_id): {
                "internship_count": row.internship_count,
                "internship_count_status": row.internship_count_status,
                "coop_count": row.coop_count,
                "coop_count_status": row.coop_count_status,
                "entry_level_full_time_count": row.entry_level_full_time_count,
                "entry_level_full_time_count_status": (row.entry_level_full_time_count_status),
                "formal_early_career_program_flag": (row.formal_early_career_program_flag),
                "student_season_recurrence_signal": (row.student_season_recurrence_signal),
            }
            for row in snapshot.entry_level_facts
        }
    return {}


def _company_public(row: dict[str, str]) -> dict[str, Any]:
    return {
        "company_name": _text(row.get("company_name")),
        "sector_primary": _text(row.get("sector")).lower(),
        "public_or_private": _text(row.get("public_or_private")),
    }


def _company_current_public(company) -> dict[str, Any]:
    return {
        "company_name": company.company_name,
        "sector_primary": company.sector_primary,
        "public_or_private": company.public_or_private,
    }


def _source_public(row: dict[str, str]) -> dict[str, Any]:
    return {
        "source_label": _text(row.get("source_name")),
        "source_type": _text(row.get("source_type")),
        "observed_date": _text(row.get("observed_at")) or None,
        "collected_date": _text(row.get("collected_at")) or None,
        "confidence": _text(row.get("confidence")),
        "license_or_terms_category": _text(row.get("license_or_terms_category")),
        "freshness_status": _text(row.get("freshness_status")),
    }


def _source_current_public(source) -> dict[str, Any]:
    return {
        "source_label": source.source_label,
        "source_type": source.source_type,
        "observed_date": source.observed_date.isoformat() if source.observed_date else None,
        "collected_date": source.collected_date.isoformat() if source.collected_date else None,
        "confidence": source.confidence,
        "license_or_terms_category": source.license_or_terms_category,
        "freshness_status": source.stored_freshness_status,
    }


def _semantic_count_warning(
    area: FactArea,
    fact_id: str,
    field: str,
    before: Any,
    after: Any,
    warnings: list[ImportDiffWarning],
    counts: dict[str, int],
) -> None:
    if not field.endswith("_status") and field != "active_posting_count_now_status":
        return
    if before in _UNKNOWN_LIKE and after == _OBSERVED_ZERO:
        counts["unknown_to_zero_changes"] += 1
        warnings.append(
            ImportDiffWarning(
                code="unknown_becoming_observed_zero",
                severity=DiffRisk.HIGH,
                area=area,
                record_id=fact_id,
                message="An unknown or uncollected value would become observed zero.",
            )
        )
    if before == _OBSERVED_ZERO and after in _UNKNOWN_LIKE:
        counts["zero_to_unknown_changes"] += 1
        warnings.append(
            ImportDiffWarning(
                code="observed_zero_becoming_unknown",
                severity=DiffRisk.HIGH,
                area=area,
                record_id=fact_id,
                message="An observed zero value would become unknown or uncollected.",
            )
        )


def _proposed_ranking_allowed(
    fact: _ProposedFact,
    *,
    source_rows: dict[str, dict[str, str]],
    as_of: date | datetime | None,
) -> bool:
    subject_type = FACT_SUBJECT_TYPES.get(fact.fact_type)
    if subject_type is None:
        return False
    now = _coerce_datetime(as_of)
    rows = tuple(
        source_rows[source_id] for source_id in fact.source_ids if source_id in source_rows
    )
    if not rows:
        metadata = _trust_metadata(fact, rows, source_allowed=False, freshness="unknown")
    else:
        try:
            source_allowed = all(_source_allowed(row) for row in rows)
            freshness = _aggregate_source_freshness(rows)
            metadata = _trust_metadata(
                fact,
                rows,
                source_allowed=source_allowed,
                freshness=freshness,
            )
        except ValueError:
            return False
    assessment = TrustAssessmentService(clock=lambda: now).assess(metadata)
    routing = RiskRoutingService(clock=lambda: now).decide(assessment, metadata)
    return routing.ranking_influence_allowed


def _trust_metadata(
    fact: _ProposedFact,
    rows: tuple[dict[str, str], ...],
    *,
    source_allowed: bool,
    freshness: str,
) -> TrustSubjectMetadata:
    confidence = _aggregate_source_confidence(rows)
    observation_date_valid = bool(rows) and all(_text(row.get("observed_at")) for row in rows)
    independently_verified = (
        source_allowed
        and observation_date_valid
        and freshness == FreshnessStatus.FRESH.value
        and confidence in {"high", "medium"}
    )
    warnings = ["curated_import_source_backed"] if rows else ["curated_import_unsourced"]
    if freshness == FreshnessStatus.STALE.value:
        warnings.append("curated_import_source_stale")
    return TrustSubjectMetadata(
        subject_type=FACT_SUBJECT_TYPES[fact.fact_type],
        subject_id=fact.fact_id,
        valid_fields=True,
        source_count=len(rows),
        source_present=bool(rows),
        source_allowed=source_allowed,
        freshness_status=freshness,
        observation_date_valid=observation_date_valid,
        confidence_label=confidence,
        duplicate_detected=False,
        conflict_detected=False,
        independent_verification=independently_verified,
        self_promotional=False,
        corroboration_count=None,
        claim_type_allowed=True,
        ranking_influence_allowed=False,
        stale=freshness == FreshnessStatus.STALE.value,
        verification_status="verified" if independently_verified else None,
        quality_label="public_source_verified" if independently_verified else None,
        trust_label="verified" if independently_verified else None,
        warnings=tuple(warnings),
        metadata={
            "import_layer": "33A",
            "imported_data": True,
            "source_backed": bool(rows),
            "fact_type": fact.fact_type,
        },
    )


def _source_allowed(row: dict[str, str]) -> bool:
    return (
        SourceType(row["source_type"]) in ALLOWED_SOURCE_TYPES
        and LicenseTermsCategory(row["license_or_terms_category"])
        in ALLOWED_LICENSE_OR_TERMS_CATEGORIES
    )


def _aggregate_source_freshness(rows: tuple[dict[str, str], ...]) -> str:
    if not rows:
        return FreshnessStatus.UNKNOWN.value
    statuses = {
        _text(row.get("freshness_status")) for row in rows if _text(row.get("freshness_status"))
    }
    if FreshnessStatus.STALE.value in statuses:
        return FreshnessStatus.STALE.value
    if statuses == {FreshnessStatus.FRESH.value}:
        return FreshnessStatus.FRESH.value
    return FreshnessStatus.UNKNOWN.value


def _aggregate_source_confidence(rows: tuple[dict[str, str], ...]) -> str:
    if not rows:
        return "unknown"
    values = {_text(row.get("confidence")) for row in rows if _text(row.get("confidence"))}
    if Confidence.LOW.value in values:
        return Confidence.LOW.value
    if values == {Confidence.HIGH.value}:
        return Confidence.HIGH.value
    if Confidence.MEDIUM.value in values:
        return Confidence.MEDIUM.value
    return "unknown"


def _proposed_source_status(
    row: dict[str, str],
    *,
    as_of: date | datetime | None,
) -> OperationalSourceFreshnessStatus:
    reference_date = _coerce_date(as_of)
    try:
        observed = parse_import_date(row["observed_at"])
    except (KeyError, ValueError):
        return OperationalSourceFreshnessStatus.NEEDS_REVIEW
    age_days = (reference_date - observed).days
    if _text(row.get("freshness_status")) == FreshnessStatus.STALE.value:
        return OperationalSourceFreshnessStatus.STALE
    if age_days > EXPIRED_AFTER_DAYS:
        return OperationalSourceFreshnessStatus.EXPIRED
    if age_days > IMPORT_STALENESS_DAYS:
        return OperationalSourceFreshnessStatus.STALE
    return OperationalSourceFreshnessStatus.CURRENT


def _overall_risk(
    blocking: list[ImportDiffWarning],
    warnings: list[ImportDiffWarning],
    changes: list[ImportDiffChange],
) -> DiffRisk:
    if blocking:
        return DiffRisk.BLOCKING
    severities = {warning.severity for warning in warnings}
    if DiffRisk.BLOCKING in severities:
        return DiffRisk.BLOCKING
    if DiffRisk.HIGH in severities:
        return DiffRisk.HIGH
    if DiffRisk.MEDIUM in severities:
        return DiffRisk.MEDIUM
    if changes:
        return DiffRisk.LOW
    return DiffRisk.NONE


def _narrative(counts: dict[str, int], risk: DiffRisk) -> str:
    fact_changes = sum(
        counts[key]
        for key in counts
        if key.endswith("_changed") and key.startswith(("presence", "hiring", "entry"))
    )
    absent_sources = counts.get("source_references_absent_from_files", 0)
    ranking_excluded = counts.get("ranking_eligible_to_excluded", 0)
    return (
        f"{fact_changes} facts changed, {absent_sources} source references are absent "
        f"from the curated files, and {ranking_excluded} facts would become "
        f"ranking-excluded. Overall import risk: {risk.value}."
    )


def _empty_summary_counts() -> dict[str, int]:
    keys = (
        "validation_errors",
        "region_changes",
        "companies_added",
        "companies_changed",
        "companies_unchanged",
        "companies_missing_from_source",
        "source_references_added",
        "source_references_changed",
        "source_references_unchanged",
        "source_references_absent_from_files",
        "removed_sources_still_used",
        "freshness_degradations",
        "presence_facts_added",
        "presence_facts_changed",
        "presence_facts_unchanged",
        "presence_facts_absent_from_source",
        "hiring_facts_added",
        "hiring_facts_changed",
        "hiring_facts_unchanged",
        "hiring_facts_absent_from_source",
        "entry_level_facts_added",
        "entry_level_facts_changed",
        "entry_level_facts_unchanged",
        "entry_level_facts_absent_from_source",
        "source_association_changes",
        "unknown_to_zero_changes",
        "zero_to_unknown_changes",
        "ranking_eligible_to_excluded",
        "ranking_excluded_to_eligible",
    )
    return {key: 0 for key in keys}


def _change(
    area: FactArea,
    change_type: str,
    record_id: str,
    field: str | None,
    before: Any,
    after: Any,
    message: str,
) -> ImportDiffChange:
    return ImportDiffChange(
        area=area,
        change_type=change_type,
        record_id=record_id,
        field=field,
        before=before,
        after=after,
        message=message,
    )


def _single_or_unknown(values: tuple[str, ...]) -> str:
    distinct = {value for value in values if value}
    if len(distinct) == 1:
        return next(iter(distinct))
    return "unknown"


def _coerce_date(value: date | datetime | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    return value


def _coerce_datetime(value: date | datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
