"""Canonical write path for validated curated market import datasets."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from backend.companies.repository import CompanyRepository
from backend.companies.service import CompanyDefinition, CompanyService
from backend.companies.types import PublicOrPrivate
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.entry_level.repository import EntryLevelRepository
from backend.entry_level.types import EntryLevelConfidence
from backend.geography.repository import RegionRepository
from backend.geography.service import GeographyService, RegionDefinition
from backend.geography.types import RegionType
from backend.hiring.repository import HiringRepository
from backend.hiring.service import HiringDefinition, HiringService, HiringSnapshot
from backend.hiring.types import (
    AnnualizedTrendSignal,
    HiringConfidence,
    SeasonalStudentHiringSignal,
)
from backend.imports.contracts import (
    COMPANIES_FILE,
    ENTRY_LEVEL_FILE,
    HIRING_FILE,
    OBSERVED_COUNT_STATUSES,
    PRESENCE_FILE,
    REGIONS_FILE,
    SOURCE_REFS_FILE,
)
from backend.imports.provenance import IMPORT_STALENESS_DAYS, parse_import_date
from backend.imports.registry import resolve_market_registry_entry
from backend.imports.result import (
    CuratedImportDiagnostic,
    CuratedMarketImportResult,
    ImportWriteCounts,
    empty_import_counts,
)
from backend.imports.validation import (
    validate_curated_market_dataset,
    validate_import_dataset,
)
from backend.presence.evidence import PresenceEvidence
from backend.presence.repository import PresenceRepository
from backend.presence.service import PresenceDefinition, PresenceService
from backend.presence.types import PresenceBasis, PresenceStatus
from backend.provenance.repository import ProvenanceRepository
from backend.provenance.service import (
    FactSourceLinkDefinition,
    ProvenanceService,
    SourceObservationDefinition,
    SourceRefDefinition,
)
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus
from backend.shared.provenance import (
    DataOrigin,
    FactBindingType,
    LicenseTermsCategory,
    ObservationStatus,
    SourceType,
)
from backend.shared.state import ObjectState, validate_transition
from backend.shared.versioning import next_version

_Outcome = Literal["created", "updated", "unchanged", "skipped", "failed"]
_COUNT_NOT_COLLECTED = ObservationStatus.NOT_COLLECTED


@dataclass(frozen=True, slots=True)
class _CuratedDataset:
    regions: tuple[dict[str, Any], ...]
    companies: tuple[dict[str, str], ...]
    presence: tuple[dict[str, str], ...]
    hiring: tuple[dict[str, str], ...]
    entry_level: tuple[dict[str, str], ...]
    source_refs: dict[str, dict[str, str]]


@dataclass(frozen=True, slots=True)
class _CountValue:
    value: int | None
    status: ObservationStatus


@dataclass(frozen=True, slots=True)
class _HiringGroup:
    company_id: str
    region_id: str
    rows: tuple[dict[str, str], ...]


def import_curated_market_dataset(
    session: Session,
    market_key_or_dataset_dir: str | Path,
    *,
    registry_path: str | Path | None = None,
    as_of: date | datetime | None = None,
    stale_after_days: int = IMPORT_STALENESS_DAYS,
) -> CuratedMarketImportResult:
    """Validate and idempotently import a curated market dataset.

    String market keys are resolved through the curated market registry.
    Direct paths are still accepted for fixture-level Layer 31 tests. The
    validation gate runs before any canonical write; validation failure returns
    a structured result and does not touch the database.
    """

    dataset_path, validation = _resolve_dataset_and_validate(
        market_key_or_dataset_dir,
        registry_path=registry_path,
        as_of=as_of,
        stale_after_days=stale_after_days,
    )
    if not validation.ok:
        return CuratedMarketImportResult(
            ok=False,
            status="validation_failed",
            dataset_path=str(dataset_path),
            validation=validation,
            counts=empty_import_counts(),
        )

    mutable_counts = _mutable_counts()
    try:
        dataset = _load_dataset(dataset_path)
        with session.begin_nested():
            _run_import(session, dataset, mutable_counts)
    except Exception as exc:
        return CuratedMarketImportResult(
            ok=False,
            status="failed",
            dataset_path=str(dataset_path),
            validation=validation,
            counts=_freeze_counts(mutable_counts),
            diagnostics=(
                CuratedImportDiagnostic(
                    code="canonical_import_failed",
                    message=str(exc),
                    stage="canonical_write",
                ),
            ),
        )

    return CuratedMarketImportResult(
        ok=True,
        status="imported",
        dataset_path=str(dataset_path),
        validation=validation,
        counts=_freeze_counts(mutable_counts),
        )


def _resolve_dataset_and_validate(
    market_key_or_dataset_dir: str | Path,
    *,
    registry_path: str | Path | None,
    as_of: date | datetime | None,
    stale_after_days: int,
) -> tuple[Path, Any]:
    if _is_market_key_target(market_key_or_dataset_dir):
        market_key = str(market_key_or_dataset_dir).strip()
        validation = validate_curated_market_dataset(
            market_key,
            registry_path=registry_path,
            as_of=as_of,
            stale_after_days=stale_after_days,
        )
        if not validation.ok:
            return Path(market_key), validation
        entry = resolve_market_registry_entry(market_key, registry_path)
        return entry.dataset_path, validation

    dataset_path = Path(market_key_or_dataset_dir)
    validation = validate_import_dataset(
        dataset_path,
        as_of=as_of,
        stale_after_days=stale_after_days,
    )
    return dataset_path, validation


def _is_market_key_target(value: str | Path) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped:
        return False
    return "/" not in stripped and "\\" not in stripped and not Path(stripped).exists()


def _run_import(
    session: Session,
    dataset: _CuratedDataset,
    counts: dict[str, dict[str, int]],
) -> None:
    region_repo = RegionRepository(session)
    company_repo = CompanyRepository(session)
    presence_repo = PresenceRepository(session)
    hiring_repo = HiringRepository(session)
    provenance_service = ProvenanceService(ProvenanceRepository(session))

    geography_service = GeographyService(region_repo)
    company_service = CompanyService(company_repo)
    presence_service = PresenceService(
        presence_repo,
        company_repo=company_repo,
        region_repo=region_repo,
    )
    hiring_service = HiringService(hiring_repo, presence_repo=presence_repo)

    for source_ref in dataset.source_refs.values():
        _upsert_source_ref_and_observation(provenance_service, source_ref, counts)

    for region in dataset.regions:
        row, outcome = geography_service.upsert_for_build(_region_definition(region))
        _record(counts, "regions", outcome)
        _link_fact(
            provenance_service,
            fact_type=FactBindingType.REGION,
            fact_id=row.region_id,
            source_ref=dataset.source_refs[_required_text(region, "source_ref")],
            observation_status=ObservationStatus.POSITIVE_OBSERVED,
            counts=counts,
        )

    for company in dataset.companies:
        row, outcome = company_service.upsert_for_classify(
            _company_definition(company)
        )
        _record(counts, "companies", outcome)
        _link_fact(
            provenance_service,
            fact_type=FactBindingType.COMPANY,
            fact_id=row.company_id,
            source_ref=dataset.source_refs[_required_text(company, "source_ref")],
            observation_status=ObservationStatus.POSITIVE_OBSERVED,
            counts=counts,
        )

    for presence in dataset.presence:
        presence_id = _presence_id(presence["company_id"], presence["region_id"])
        source_ref = dataset.source_refs[presence["source_ref"]]
        link_id = _link_id(
            FactBindingType.COMPANY_REGION_PRESENCE,
            presence_id,
            source_ref["source_ref"],
        )
        row, outcome = presence_service.upsert_for_mapping(
            PresenceDefinition(
                presence_id=presence_id,
                company_id=presence["company_id"],
                region_id=presence["region_id"],
                evidence=_presence_evidence(presence, source_ref, link_id),
            )
        )
        _record(counts, "presence", outcome)
        _link_fact(
            provenance_service,
            fact_type=FactBindingType.COMPANY_REGION_PRESENCE,
            fact_id=row.presence_id,
            source_ref=source_ref,
            observation_status=_presence_observation_status(row.presence_status),
            counts=counts,
        )

    for group in _hiring_groups(dataset.hiring):
        source_ref = dataset.source_refs[group.rows[0]["source_ref"]]
        hiring_id = _hiring_id(group.company_id, group.region_id)
        link_id = _link_id(
            FactBindingType.COMPANY_REGION_HIRING,
            hiring_id,
            source_ref["source_ref"],
        )
        snapshot = _hiring_snapshot(group, source_ref, link_id)
        row, outcome = hiring_service.upsert_for_refresh(
            HiringDefinition(
                hiring_id=hiring_id,
                company_id=group.company_id,
                region_id=group.region_id,
                snapshot=snapshot,
            )
        )
        _record(counts, "hiring", outcome)
        _link_fact(
            provenance_service,
            fact_type=FactBindingType.COMPANY_REGION_HIRING,
            fact_id=row.hiring_id,
            source_ref=source_ref,
            observation_status=(
                snapshot.active_posting_count_now_status or ObservationStatus.UNKNOWN
            ),
            counts=counts,
        )

    for entry in dataset.entry_level:
        source_ref = dataset.source_refs[entry["source_ref"]]
        entry_level_id = _entry_level_id(entry["company_id"], entry["region_id"])
        link_id = _link_id(
            FactBindingType.COMPANY_REGION_ENTRY_LEVEL,
            entry_level_id,
            source_ref["source_ref"],
        )
        outcome = _upsert_entry_level_fact(
            session,
            entry,
            source_ref=source_ref,
            link_id=link_id,
        )
        _record(counts, "entry_level", outcome)
        _link_fact(
            provenance_service,
            fact_type=FactBindingType.COMPANY_REGION_ENTRY_LEVEL,
            fact_id=entry_level_id,
            source_ref=source_ref,
            observation_status=_entry_level_observation_status(entry),
            counts=counts,
        )


def _upsert_source_ref_and_observation(
    provenance_service: ProvenanceService,
    source_ref: dict[str, str],
    counts: dict[str, dict[str, int]],
) -> None:
    source_id = source_ref["source_ref"]
    source_definition = SourceRefDefinition(
        source_id=source_id,
        source_type=SourceType(source_ref["source_type"]),
        source_name=source_ref["source_name"],
        url_or_provider=source_ref["source_url_or_reference"],
        collected_at=_date_to_datetime(source_ref["collected_at"]),
        observed_at=_date_to_datetime(source_ref["observed_at"]),
        license_or_terms_category=LicenseTermsCategory(
            source_ref["license_or_terms_category"]
        ),
        confidence=Confidence(source_ref["confidence"]),
        freshness_status=FreshnessStatus(source_ref["freshness_status"]),
        data_origin=DataOrigin.MANUAL_REVIEWED,
        notes="Layer 31B curated deterministic import source.",
    )
    _, source_outcome = provenance_service.upsert_source_ref(source_definition)
    _record(counts, "source_refs", source_outcome)

    _, observation_outcome = provenance_service.upsert_observation(
        SourceObservationDefinition(
            observation_id=_observation_id(source_id),
            source_id=source_id,
            collected_at=_date_to_datetime(source_ref["collected_at"]),
            observed_at=_date_to_datetime(source_ref["observed_at"]),
            data_origin=DataOrigin.MANUAL_REVIEWED,
            observation_status=ObservationStatus.UNKNOWN,
            confidence=Confidence(source_ref["confidence"]),
            freshness_status=FreshnessStatus(source_ref["freshness_status"]),
            notes="Layer 31B curated deterministic import observation.",
        )
    )
    _record(counts, "source_observations", observation_outcome)


def _link_fact(
    provenance_service: ProvenanceService,
    *,
    fact_type: FactBindingType,
    fact_id: str,
    source_ref: dict[str, str],
    observation_status: ObservationStatus,
    counts: dict[str, dict[str, int]],
) -> str:
    source_id = source_ref["source_ref"]
    link_id = _link_id(fact_type, fact_id, source_id)
    _, outcome = provenance_service.upsert_fact_source_link(
        FactSourceLinkDefinition(
            link_id=link_id,
            observation_id=_observation_id(source_id),
            fact_type=fact_type,
            fact_id=fact_id,
            data_origin=DataOrigin.MANUAL_REVIEWED,
            observation_status=observation_status,
            confidence=Confidence(source_ref["confidence"]),
            freshness_status=FreshnessStatus(source_ref["freshness_status"]),
            notes="Layer 31B curated deterministic import fact link.",
        )
    )
    _record(counts, "fact_source_links", outcome)
    return link_id


def _region_definition(region: dict[str, Any]) -> RegionDefinition:
    return RegionDefinition(
        region_id=_required_text(region, "region_id"),
        region_name=_required_text(region, "region_name"),
        display_name=_required_text(region, "region_name"),
        region_type=RegionType(_required_text(region, "region_type")),
        labor_market_group=_required_text(region, "region_id"),
        normalization_profile_id=None,
    )


def _company_definition(company: dict[str, str]) -> CompanyDefinition:
    name = company["company_name"].strip()
    return CompanyDefinition(
        company_id=company["company_id"],
        company_name=name,
        normalized_company_name=name.lower(),
        sector_primary=company["sector"].strip().lower(),
        public_or_private=PublicOrPrivate(company["public_or_private"]),
    )


def _presence_evidence(
    row: dict[str, str],
    source_ref: dict[str, str],
    link_id: str,
) -> PresenceEvidence:
    basis = PresenceBasis(row["presence_basis"])
    status = PresenceStatus(row["presence_status"])
    office = basis in {
        PresenceBasis.OFFICE_PLUS_HIRING,
        PresenceBasis.OFFICE_PLUS_OPERATIONS,
        PresenceBasis.SATELLITE_OFFICE_ONLY,
    }
    operations = basis is PresenceBasis.OFFICE_PLUS_OPERATIONS
    hiring = basis is PresenceBasis.OFFICE_PLUS_HIRING
    if status is PresenceStatus.NOT_PRESENT:
        office = operations = hiring = False
    elif status is PresenceStatus.UNCERTAIN and basis is PresenceBasis.INSUFFICIENT_EVIDENCE:
        office = False
        operations = False
        hiring = True
    return PresenceEvidence(
        office_evidence_flag=office,
        operations_evidence_flag=operations,
        hiring_evidence_flag=hiring,
        source_refs=[
            _source_payload(
                source_ref,
                link_id=link_id,
                fact_notes={"presence_status": row["presence_status"]},
            )
        ],
    )


def _hiring_snapshot(
    group: _HiringGroup,
    source_ref: dict[str, str],
    link_id: str,
) -> HiringSnapshot:
    counts = [
        _count_value(row, "active_posting_count", "active_posting_count_status")
        for row in group.rows
    ]
    active = _aggregate_counts(counts)
    role_family_summary = {
        row["role_family"]: count.value
        for row, count in zip(group.rows, counts, strict=True)
        if count.status in OBSERVED_COUNT_STATUSES and count.value is not None
    }
    annualized = _single_or_unknown(
        tuple(row["annualized_trend_signal"] for row in group.rows)
    )
    seasonal = _single_or_unknown(
        tuple(row["seasonal_student_hiring_signal"] for row in group.rows)
    )
    return HiringSnapshot(
        currently_hiring_flag=any(
            count.value is not None and count.value > 0 for count in counts
        ),
        active_posting_count_now=active.value,
        active_posting_count_now_status=active.status,
        posting_count_30d=None,
        posting_count_30d_status=_COUNT_NOT_COLLECTED,
        posting_count_90d=None,
        posting_count_90d_status=_COUNT_NOT_COLLECTED,
        annualized_trend_signal=AnnualizedTrendSignal(annualized),
        seasonal_student_hiring_signal=SeasonalStudentHiringSignal(seasonal),
        hiring_program_count=None,
        hiring_program_count_status=_COUNT_NOT_COLLECTED,
        role_family_summary=role_family_summary,
        hiring_confidence=_hiring_confidence(source_ref["confidence"]),
        freshness_expires_at=_freshness_expires_at(source_ref),
        source_refs=[
            _source_payload(
                source_ref,
                link_id=link_id,
                fact_notes={
                    "active_posting_count_status": active.status.value,
                    "role_family_count_statuses": {
                        row["role_family"]: count.status.value
                        for row, count in zip(group.rows, counts, strict=True)
                    },
                },
            )
        ],
    )


def _upsert_entry_level_fact(
    session: Session,
    row: dict[str, str],
    *,
    source_ref: dict[str, str],
    link_id: str,
) -> _Outcome:
    repo = EntryLevelRepository(session)
    hiring_repo = HiringRepository(session)
    company_id = row["company_id"]
    region_id = row["region_id"]
    if hiring_repo.get_by_pair(company_id, region_id) is None:
        raise ValueError(f"entry-level import requires hiring fact: {company_id}/{region_id}")

    entry_level_id = _entry_level_id(company_id, region_id)
    existing = repo.get_by_pair(company_id, region_id)
    payload = _entry_level_payload(row, source_ref=source_ref, link_id=link_id)
    if existing is None:
        created = CompanyRegionEntryLevel(
            entry_level_id=entry_level_id,
            company_id=company_id,
            region_id=region_id,
        )
        _apply_entry_level_payload(created, payload)
        repo.add(created)
        repo.flush()
        _set_fresh(created)
        repo.flush()
        return "created"

    if _entry_level_matches(existing, payload):
        return "unchanged"
    _apply_entry_level_payload(existing, payload)
    existing.version = next_version(existing.version)
    if existing.state == ObjectState.NEW.value:
        _set_fresh(existing)
    elif existing.state == ObjectState.BUILDING.value:
        validate_transition(existing.state, ObjectState.FRESH)
        existing.state = ObjectState.FRESH.value
    repo.flush()
    return "updated"


def _entry_level_payload(
    row: dict[str, str],
    *,
    source_ref: dict[str, str],
    link_id: str,
) -> dict[str, Any]:
    internship = _count_value(row, "internship_count", "internship_count_status")
    coop = _count_value(row, "coop_count", "coop_count_status")
    full_time = _count_value(
        row,
        "entry_level_full_time_count",
        "entry_level_full_time_count_status",
    )
    flag = row["formal_early_career_program_flag"]
    formal_flag = flag == "true"
    return {
        "internship_count": internship.value,
        "internship_count_status": internship.status.value,
        "coop_count": coop.value,
        "coop_count_status": coop.status.value,
        "entry_level_full_time_count": full_time.value,
        "entry_level_full_time_count_status": full_time.status.value,
        "formal_early_career_program_flag": formal_flag,
        "student_season_recurrence_signal": row["student_season_recurrence_signal"],
        "entry_level_confidence": _entry_level_confidence(source_ref["confidence"]).value,
        "freshness_expires_at": _freshness_expires_at(source_ref),
        "source_refs": [
            _source_payload(
                source_ref,
                link_id=link_id,
                fact_notes={
                    "internship_count_status": internship.status.value,
                    "coop_count_status": coop.status.value,
                    "entry_level_full_time_count_status": full_time.status.value,
                    "formal_early_career_program_flag_status": (
                        "unknown" if flag == "unknown" else "observed"
                    ),
                },
            )
        ],
    }


def _apply_entry_level_payload(
    target: CompanyRegionEntryLevel,
    payload: dict[str, Any],
) -> None:
    target.internship_count = payload["internship_count"]
    target.internship_count_status = payload["internship_count_status"]
    target.coop_count = payload["coop_count"]
    target.coop_count_status = payload["coop_count_status"]
    target.entry_level_full_time_count = payload["entry_level_full_time_count"]
    target.entry_level_full_time_count_status = payload[
        "entry_level_full_time_count_status"
    ]
    target.formal_early_career_program_flag = payload[
        "formal_early_career_program_flag"
    ]
    target.student_season_recurrence_signal = payload[
        "student_season_recurrence_signal"
    ]
    target.entry_level_confidence = payload["entry_level_confidence"]
    target.freshness_expires_at = payload["freshness_expires_at"]
    target.source_refs = payload["source_refs"]


def _entry_level_matches(
    row: CompanyRegionEntryLevel,
    payload: dict[str, Any],
) -> bool:
    return (
        row.internship_count == payload["internship_count"]
        and row.internship_count_status == payload["internship_count_status"]
        and row.coop_count == payload["coop_count"]
        and row.coop_count_status == payload["coop_count_status"]
        and row.entry_level_full_time_count == payload["entry_level_full_time_count"]
        and row.entry_level_full_time_count_status
        == payload["entry_level_full_time_count_status"]
        and row.formal_early_career_program_flag
        == payload["formal_early_career_program_flag"]
        and row.student_season_recurrence_signal
        == payload["student_season_recurrence_signal"]
        and row.entry_level_confidence == payload["entry_level_confidence"]
        and row.source_refs == payload["source_refs"]
    )


def _source_payload(
    source_ref: dict[str, str],
    *,
    link_id: str,
    fact_notes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source_ref": source_ref["source_ref"],
        "source_id": source_ref["source_ref"],
        "observation_id": _observation_id(source_ref["source_ref"]),
        "fact_source_link_id": link_id,
        "source_type": source_ref["source_type"],
        "source_name": source_ref["source_name"],
        "source_url_or_reference": source_ref["source_url_or_reference"],
        "collected_at": source_ref["collected_at"],
        "observed_at": source_ref["observed_at"],
        "confidence": source_ref["confidence"],
        "license_or_terms_category": source_ref["license_or_terms_category"],
        "freshness_status": source_ref["freshness_status"],
    }
    if fact_notes:
        payload["fact_notes"] = fact_notes
    return payload


def _count_value(row: dict[str, str], count_field: str, status_field: str) -> _CountValue:
    status = ObservationStatus(row[status_field])
    if status not in OBSERVED_COUNT_STATUSES:
        return _CountValue(value=None, status=status)
    return _CountValue(value=int(row[count_field]), status=status)


def _aggregate_counts(counts: list[_CountValue]) -> _CountValue:
    if not counts:
        return _CountValue(value=None, status=ObservationStatus.NOT_COLLECTED)
    for status in (
        ObservationStatus.UNKNOWN,
        ObservationStatus.NOT_COLLECTED,
        ObservationStatus.NOT_APPLICABLE,
    ):
        if any(count.status is status for count in counts):
            return _CountValue(value=None, status=status)
    total = sum(count.value for count in counts if count.value is not None)
    status = (
        ObservationStatus.POSITIVE_OBSERVED
        if total > 0
        else ObservationStatus.ZERO_OBSERVED
    )
    return _CountValue(value=total, status=status)


def _entry_level_observation_status(row: dict[str, str]) -> ObservationStatus:
    counts = [
        _count_value(row, "internship_count", "internship_count_status"),
        _count_value(row, "coop_count", "coop_count_status"),
        _count_value(
            row,
            "entry_level_full_time_count",
            "entry_level_full_time_count_status",
        ),
    ]
    return _aggregate_counts(counts).status


def _presence_observation_status(status: str) -> ObservationStatus:
    if status == PresenceStatus.PRESENT.value:
        return ObservationStatus.POSITIVE_OBSERVED
    if status == PresenceStatus.NOT_PRESENT.value:
        return ObservationStatus.ZERO_OBSERVED
    return ObservationStatus.UNKNOWN


def _hiring_confidence(value: str) -> HiringConfidence:
    if value == Confidence.HIGH.value:
        return HiringConfidence.HIGH_CONFIDENCE
    if value == Confidence.MEDIUM.value:
        return HiringConfidence.MODERATE_CONFIDENCE
    if value == Confidence.LOW.value:
        return HiringConfidence.LOW_CONFIDENCE
    return HiringConfidence.UNKNOWN


def _entry_level_confidence(value: str) -> EntryLevelConfidence:
    if value == Confidence.HIGH.value:
        return EntryLevelConfidence.HIGH_CONFIDENCE
    if value == Confidence.MEDIUM.value:
        return EntryLevelConfidence.MODERATE_CONFIDENCE
    if value == Confidence.LOW.value:
        return EntryLevelConfidence.LOW_CONFIDENCE
    return EntryLevelConfidence.UNKNOWN


def _freshness_expires_at(source_ref: dict[str, str]) -> datetime:
    return _date_to_datetime(source_ref["observed_at"]) + timedelta(days=IMPORT_STALENESS_DAYS)


def _hiring_groups(rows: tuple[dict[str, str], ...]) -> tuple[_HiringGroup, ...]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault((row["company_id"], row["region_id"]), []).append(row)
    return tuple(
        _HiringGroup(company_id=company_id, region_id=region_id, rows=tuple(items))
        for (company_id, region_id), items in sorted(grouped.items())
    )


def _single_or_unknown(values: tuple[str, ...]) -> str:
    distinct = {value for value in values if value}
    if len(distinct) == 1:
        return next(iter(distinct))
    return "unknown"


def _load_dataset(dataset_path: Path) -> _CuratedDataset:
    source_refs = {
        row["source_ref"]: row
        for row in _read_csv(dataset_path / SOURCE_REFS_FILE)
    }
    return _CuratedDataset(
        regions=tuple(json.loads((dataset_path / REGIONS_FILE).read_text(encoding="utf-8"))),
        companies=tuple(_read_csv(dataset_path / COMPANIES_FILE)),
        presence=tuple(_read_csv(dataset_path / PRESENCE_FILE)),
        hiring=tuple(_read_csv(dataset_path / HIRING_FILE)),
        entry_level=tuple(_read_csv(dataset_path / ENTRY_LEVEL_FILE)),
        source_refs=source_refs,
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _date_to_datetime(value: str) -> datetime:
    parsed = parse_import_date(value)
    return datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC)


def _observation_id(source_id: str) -> str:
    candidate = f"obs_{source_id}"
    if len(candidate) <= 64:
        return candidate
    return f"obs_{_digest(source_id)}"


def _presence_id(company_id: str, region_id: str) -> str:
    return _bounded_id("presence", company_id, region_id)


def _hiring_id(company_id: str, region_id: str) -> str:
    return _bounded_id("hiring", company_id, region_id)


def _entry_level_id(company_id: str, region_id: str) -> str:
    return _bounded_id("entry", company_id, region_id)


def _bounded_id(prefix: str, *parts: str, max_length: int = 64) -> str:
    candidate = "_".join((prefix, *parts))
    if len(candidate) <= max_length:
        return candidate
    return f"{prefix}_{_digest(candidate)}"


def _link_id(
    fact_type: FactBindingType,
    fact_id: str,
    source_id: str,
    fact_field: str | None = None,
) -> str:
    del fact_field
    return f"l31b_{_digest(f'{fact_type.value}:{fact_id}:{source_id}')}"


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:24]


def _required_text(record: dict[str, Any], field: str) -> str:
    return str(record[field]).strip()


def _set_fresh(row: CompanyRegionEntryLevel) -> None:
    validate_transition(row.state, ObjectState.BUILDING)
    row.state = ObjectState.BUILDING.value
    validate_transition(row.state, ObjectState.FRESH)
    row.state = ObjectState.FRESH.value


def _mutable_counts() -> dict[str, dict[str, int]]:
    return {
        key: {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "failed": 0}
        for key in empty_import_counts()
    }


def _record(counts: dict[str, dict[str, int]], key: str, outcome: _Outcome) -> None:
    counts[key][outcome] += 1


def _freeze_counts(counts: dict[str, dict[str, int]]) -> dict[str, ImportWriteCounts]:
    return {
        key: ImportWriteCounts(
            created=value["created"],
            updated=value["updated"],
            unchanged=value["unchanged"],
            skipped=value["skipped"],
            failed=value["failed"],
        )
        for key, value in counts.items()
    }
