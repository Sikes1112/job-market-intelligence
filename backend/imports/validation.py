"""Validation engine for Layer 31A deterministic curated imports."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from backend.companies.types import PublicOrPrivate
from backend.entry_level.types import StudentSeasonRecurrenceSignal
from backend.geography.types import RegionType
from backend.hiring.role_families import DOCUMENTED_ROLE_FAMILIES
from backend.hiring.types import AnnualizedTrendSignal, SeasonalStudentHiringSignal
from backend.imports.contracts import (
    AMBIGUOUS_UNKNOWN_COUNT_VALUES,
    COMPANIES_FILE,
    COUNT_FIELDS_BY_FILE,
    CSV_REQUIRED_FIELDS,
    ENTRY_LEVEL_FILE,
    HIRING_FILE,
    IMPORT_COUNT_STATUSES,
    OBSERVED_COUNT_STATUSES,
    PRESENCE_FILE,
    REGION_REQUIRED_FIELDS,
    REGIONS_FILE,
    REQUIRED_DATASET_FILES,
    SOURCE_REFS_FILE,
    UNOBSERVED_COUNT_STATUSES,
    ImportDatasetSummary,
)
from backend.imports.provenance import (
    ALLOWED_FRESHNESS_STATUSES,
    ALLOWED_LICENSE_OR_TERMS_CATEGORIES,
    ALLOWED_SOURCE_TYPES,
    IMPORT_STALENESS_DAYS,
    coerce_import_as_of,
    is_stale_observed_at,
    parse_import_date,
)
from backend.imports.registry import (
    MARKET_REGISTRY_FILE,
    CuratedMarketRegistryEntry,
    MarketRegistryIssue,
    validate_market_registry,
)
from backend.presence.types import PresenceBasis, PresenceStatus
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus
from backend.shared.provenance import LicenseTermsCategory, ObservationStatus, SourceType

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,127}$")


@dataclass(frozen=True, slots=True)
class ImportValidationIssue:
    file: str
    code: str
    message: str
    row_number: int | None = None
    record_id: str | None = None
    field: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "row_number": self.row_number,
            "record_id": self.record_id,
            "field": self.field,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class ImportValidationResult:
    errors: tuple[ImportValidationIssue, ...]
    warnings: tuple[ImportValidationIssue, ...]
    summary: ImportDatasetSummary

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True, slots=True)
class _CsvData:
    rows: tuple[tuple[int, dict[str, str]], ...] = ()
    fieldnames: tuple[str, ...] = ()


def validate_import_dataset(
    dataset_dir: str | Path,
    *,
    as_of: date | datetime | None = None,
    stale_after_days: int = IMPORT_STALENESS_DAYS,
) -> ImportValidationResult:
    """Load and validate a Layer 31A curated import dataset.

    Ordinary data failures are returned as structured errors. This function
    does not create canonical records, recompute scores, or call external
    systems.
    """

    base_path = Path(dataset_dir)
    validation_date = coerce_import_as_of(as_of)
    errors: list[ImportValidationIssue] = []
    warnings: list[ImportValidationIssue] = []

    _validate_required_files(base_path, errors)

    source_refs = _load_csv(base_path, SOURCE_REFS_FILE, errors)
    companies = _load_csv(base_path, COMPANIES_FILE, errors)
    presence = _load_csv(base_path, PRESENCE_FILE, errors)
    hiring = _load_csv(base_path, HIRING_FILE, errors)
    entry_level = _load_csv(base_path, ENTRY_LEVEL_FILE, errors)
    regions = _load_regions(base_path, errors)

    source_ref_ids, valid_source_ref_ids = _validate_source_refs(
        source_refs,
        errors,
        as_of=validation_date,
        stale_after_days=stale_after_days,
    )
    region_ids = _validate_regions(regions, source_ref_ids, valid_source_ref_ids, errors)
    company_ids = _validate_companies(
        companies,
        source_ref_ids,
        valid_source_ref_ids,
        errors,
    )
    _validate_presence(
        presence,
        company_ids,
        region_ids,
        source_ref_ids,
        valid_source_ref_ids,
        errors,
    )
    _validate_hiring(
        hiring,
        company_ids,
        region_ids,
        source_ref_ids,
        valid_source_ref_ids,
        errors,
    )
    _validate_entry_level(
        entry_level,
        company_ids,
        region_ids,
        source_ref_ids,
        valid_source_ref_ids,
        errors,
    )

    summary = ImportDatasetSummary(
        region_count=len(regions),
        company_count=len(companies.rows),
        presence_fact_count=len(presence.rows),
        hiring_fact_count=len(hiring.rows),
        entry_level_fact_count=len(entry_level.rows),
        source_ref_count=len(source_refs.rows),
    )
    return ImportValidationResult(
        errors=tuple(errors),
        warnings=tuple(warnings),
        summary=summary,
    )


def validate_curated_market_dataset(
    market_key: str,
    *,
    registry_path: str | Path | None = None,
    as_of: date | datetime | None = None,
    stale_after_days: int = IMPORT_STALENESS_DAYS,
) -> ImportValidationResult:
    """Validate a registered curated market dataset by market key."""

    registry_result = validate_market_registry(registry_path)
    registry_errors = [
        _registry_issue_as_import_issue(issue) for issue in registry_result.errors
    ]
    registry_warnings = [
        _registry_issue_as_import_issue(issue) for issue in registry_result.warnings
    ]
    if registry_errors:
        return ImportValidationResult(
            errors=tuple(registry_errors),
            warnings=tuple(registry_warnings),
            summary=ImportDatasetSummary(),
        )

    entry = registry_result.by_market_key.get(market_key)
    if entry is None:
        return ImportValidationResult(
            errors=(
                ImportValidationIssue(
                    file=MARKET_REGISTRY_FILE,
                    code="invalid_market_key",
                    message=f"market_key is not registered: {market_key}",
                    record_id=market_key,
                    field="market_key",
                ),
            ),
            warnings=tuple(registry_warnings),
            summary=ImportDatasetSummary(),
        )

    result = validate_import_dataset(
        entry.dataset_path,
        as_of=as_of,
        stale_after_days=stale_after_days,
    )
    errors = list(result.errors)
    warnings = list(result.warnings) + registry_warnings
    if result.ok:
        errors.extend(_validate_registered_market_dataset_contract(entry))
    return ImportValidationResult(
        errors=tuple(errors),
        warnings=tuple(warnings),
        summary=result.summary,
    )


def _validate_required_files(base_path: Path, errors: list[ImportValidationIssue]) -> None:
    for file_name in REQUIRED_DATASET_FILES:
        if not (base_path / file_name).is_file():
            errors.append(
                ImportValidationIssue(
                    file=file_name,
                    code="missing_required_file",
                    message=f"required import file is missing: {file_name}",
                )
            )


def _load_csv(
    base_path: Path,
    file_name: str,
    errors: list[ImportValidationIssue],
) -> _CsvData:
    path = base_path / file_name
    if not path.is_file():
        return _CsvData()
    try:
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = tuple(reader.fieldnames or ())
            rows = tuple((index, dict(row)) for index, row in enumerate(reader, start=2))
    except (OSError, UnicodeError, csv.Error) as exc:
        errors.append(
            ImportValidationIssue(
                file=file_name,
                code="file_read_error",
                message=f"could not read import file: {exc}",
            )
        )
        return _CsvData()

    required_fields = CSV_REQUIRED_FIELDS.get(file_name, ())
    for field in required_fields:
        if field not in fieldnames:
            errors.append(
                ImportValidationIssue(
                    file=file_name,
                    code="missing_required_field",
                    field=field,
                    message=f"required field is missing from {file_name}: {field}",
                )
            )
    return _CsvData(rows=rows, fieldnames=fieldnames)


def _registry_issue_as_import_issue(
    issue: MarketRegistryIssue,
) -> ImportValidationIssue:
    return ImportValidationIssue(
        file=issue.file,
        code=issue.code,
        message=issue.message,
        row_number=issue.row_number,
        record_id=issue.record_id,
        field=issue.field,
    )


def _validate_registered_market_dataset_contract(
    entry: CuratedMarketRegistryEntry,
) -> tuple[ImportValidationIssue, ...]:
    errors: list[ImportValidationIssue] = []
    market_prefix = f"src_{entry.market_key}_"

    regions = _load_regions(entry.dataset_path, [])
    region_ids = {
        _text(record.get("region_id"))
        for _row_number, record in regions
        if _text(record.get("region_id"))
    }
    if region_ids != {entry.region_id}:
        errors.append(
            ImportValidationIssue(
                file=REGIONS_FILE,
                code="registered_region_id_mismatch",
                message=(
                    f"registered region_id {entry.region_id!r} does not match "
                    f"dataset regions {sorted(region_ids)!r}"
                ),
                record_id=entry.market_key,
                field="region_id",
            )
        )

    for row_number, record in regions:
        _validate_registered_row_region(
            REGIONS_FILE,
            record,
            row_number=row_number,
            record_id=_text(record.get("region_id")) or f"record:{row_number}",
            region_id=entry.region_id,
            errors=errors,
        )
        _validate_registered_source_ref_market(
            REGIONS_FILE,
            record,
            row_number=row_number,
            record_id=_text(record.get("region_id")) or f"record:{row_number}",
            market_prefix=market_prefix,
            errors=errors,
        )

    for file_name in (
        SOURCE_REFS_FILE,
        COMPANIES_FILE,
        PRESENCE_FILE,
        HIRING_FILE,
        ENTRY_LEVEL_FILE,
    ):
        csv_data = _load_csv(entry.dataset_path, file_name, [])
        for row_number, row in csv_data.rows:
            record_id = _registered_record_id(row, row_number)
            _validate_registered_source_ref_market(
                file_name,
                row,
                row_number=row_number,
                record_id=record_id,
                market_prefix=market_prefix,
                errors=errors,
            )
            if file_name in {PRESENCE_FILE, HIRING_FILE, ENTRY_LEVEL_FILE}:
                _validate_registered_row_region(
                    file_name,
                    row,
                    row_number=row_number,
                    record_id=record_id,
                    region_id=entry.region_id,
                    errors=errors,
                )

    return tuple(errors)


def _validate_registered_row_region(
    file_name: str,
    row: dict[str, Any],
    *,
    row_number: int,
    record_id: str,
    region_id: str,
    errors: list[ImportValidationIssue],
) -> None:
    row_region_id = _text(row.get("region_id"))
    if row_region_id and row_region_id != region_id:
        _add_error(
            errors,
            file_name,
            "registered_region_id_mismatch",
            f"row region_id {row_region_id!r} does not match registered {region_id!r}",
            row_number=row_number,
            record_id=record_id,
            field="region_id",
        )


def _validate_registered_source_ref_market(
    file_name: str,
    row: dict[str, Any],
    *,
    row_number: int,
    record_id: str,
    market_prefix: str,
    errors: list[ImportValidationIssue],
) -> None:
    source_ref = _text(row.get("source_ref"))
    if source_ref and not source_ref.startswith(market_prefix):
        _add_error(
            errors,
            file_name,
            "source_ref_market_mismatch",
            f"source_ref {source_ref!r} does not belong to registered market",
            row_number=row_number,
            record_id=record_id,
            field="source_ref",
        )


def _registered_record_id(row: dict[str, str], row_number: int) -> str:
    return (
        _text(row.get("source_ref"))
        or _text(row.get("company_id"))
        or _company_region_record_id(row, row_number)
    )


def _load_regions(
    base_path: Path,
    errors: list[ImportValidationIssue],
) -> tuple[tuple[int, dict[str, Any]], ...]:
    file_name = REGIONS_FILE
    path = base_path / file_name
    if not path.is_file():
        return ()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(
            ImportValidationIssue(
                file=file_name,
                code="file_read_error",
                message=f"could not read import file: {exc}",
            )
        )
        return ()
    if not isinstance(raw, list):
        errors.append(
            ImportValidationIssue(
                file=file_name,
                code="invalid_json_shape",
                message="regions.json must contain a JSON array of region records",
            )
        )
        return ()

    records: list[tuple[int, dict[str, Any]]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            errors.append(
                ImportValidationIssue(
                    file=file_name,
                    row_number=index,
                    code="invalid_json_record",
                    message="region records must be JSON objects",
                )
            )
            continue
        records.append((index, item))
    return tuple(records)


def _validate_source_refs(
    csv_data: _CsvData,
    errors: list[ImportValidationIssue],
    *,
    as_of: date,
    stale_after_days: int,
) -> tuple[set[str], set[str]]:
    source_refs: set[str] = set()
    invalid_source_refs: set[str] = set()

    for row_number, row in csv_data.rows:
        source_ref = _text(row.get("source_ref"))
        record_id = source_ref or f"row:{row_number}"
        before = len(errors)

        if not source_ref:
            _add_error(
                errors,
                SOURCE_REFS_FILE,
                "missing_required_field",
                "source_ref is required for every source reference",
                row_number=row_number,
                record_id=record_id,
                field="source_ref",
            )
        elif source_ref in source_refs:
            invalid_source_refs.add(source_ref)
            _add_error(
                errors,
                SOURCE_REFS_FILE,
                "duplicate_source_ref",
                f"duplicate source_ref: {source_ref}",
                row_number=row_number,
                record_id=record_id,
                field="source_ref",
            )
        else:
            source_refs.add(source_ref)

        for field in CSV_REQUIRED_FIELDS[SOURCE_REFS_FILE]:
            if field == "source_ref":
                continue
            if field not in csv_data.fieldnames:
                continue
            if _is_blank(row.get(field)):
                _add_error(
                    errors,
                    SOURCE_REFS_FILE,
                    "missing_provenance_field",
                    f"source_ref {record_id} is missing provenance field {field}",
                    row_number=row_number,
                    record_id=record_id,
                    field=field,
                )

        _validate_source_type(row, row_number, record_id, errors)
        _validate_license_or_terms(row, row_number, record_id, errors)
        _validate_confidence(row, row_number, record_id, errors)
        observed_at = _validate_source_date(row, "observed_at", row_number, record_id, errors)
        _validate_source_date(row, "collected_at", row_number, record_id, errors)
        _validate_freshness_status(row, row_number, record_id, errors)

        if observed_at is not None and is_stale_observed_at(
            observed_at,
            as_of=as_of,
            stale_after_days=stale_after_days,
        ):
            _add_error(
                errors,
                SOURCE_REFS_FILE,
                "stale_source_date",
                (
                    f"source_ref {record_id} observed_at is older than "
                    f"{stale_after_days} days"
                ),
                row_number=row_number,
                record_id=record_id,
                field="observed_at",
            )

        if len(errors) > before and source_ref:
            invalid_source_refs.add(source_ref)

    return source_refs, source_refs - invalid_source_refs


def _validate_regions(
    records: tuple[tuple[int, dict[str, Any]], ...],
    source_refs: set[str],
    valid_source_refs: set[str],
    errors: list[ImportValidationIssue],
) -> set[str]:
    region_ids: set[str] = set()

    for row_number, record in records:
        region_id = _text(record.get("region_id"))
        record_id = region_id or f"record:{row_number}"
        for field in REGION_REQUIRED_FIELDS:
            if _json_blank(record.get(field)):
                _add_error(
                    errors,
                    REGIONS_FILE,
                    "missing_required_field",
                    f"region record {record_id} is missing required field {field}",
                    row_number=row_number,
                    record_id=record_id,
                    field=field,
                )

        if region_id and _validate_identifier(
            region_id,
            file_name=REGIONS_FILE,
            field="region_id",
            row_number=row_number,
            record_id=record_id,
            code="invalid_region_id",
            errors=errors,
        ):
            if region_id in region_ids:
                _add_error(
                    errors,
                    REGIONS_FILE,
                    "duplicate_region_id",
                    f"duplicate region_id: {region_id}",
                    row_number=row_number,
                    record_id=record_id,
                    field="region_id",
                )
            else:
                region_ids.add(region_id)

        region_type = _text(record.get("region_type"))
        if region_type and region_type not in RegionType.values():
            _add_error(
                errors,
                REGIONS_FILE,
                "invalid_field_value",
                f"unsupported region_type: {region_type}",
                row_number=row_number,
                record_id=record_id,
                field="region_type",
            )
        state_codes = record.get("state_codes")
        if state_codes is not None and (
            not isinstance(state_codes, list)
            or not state_codes
            or any(not isinstance(code, str) or not code.strip() for code in state_codes)
        ):
            _add_error(
                errors,
                REGIONS_FILE,
                "invalid_field_value",
                "state_codes must be a non-empty list of state code strings",
                row_number=row_number,
                record_id=record_id,
                field="state_codes",
            )
        _validate_row_source_ref(
            REGIONS_FILE,
            record,
            row_number=row_number,
            record_id=record_id,
            source_refs=source_refs,
            valid_source_refs=valid_source_refs,
            errors=errors,
        )

    return region_ids


def _validate_companies(
    csv_data: _CsvData,
    source_refs: set[str],
    valid_source_refs: set[str],
    errors: list[ImportValidationIssue],
) -> set[str]:
    company_ids: set[str] = set()

    for row_number, row in csv_data.rows:
        company_id = _text(row.get("company_id"))
        record_id = company_id or f"row:{row_number}"
        _validate_csv_row_required_fields(
            COMPANIES_FILE,
            csv_data,
            row,
            row_number,
            record_id,
            errors,
        )
        if company_id and _validate_identifier(
            company_id,
            file_name=COMPANIES_FILE,
            field="company_id",
            row_number=row_number,
            record_id=record_id,
            code="invalid_company_id",
            errors=errors,
        ):
            if company_id in company_ids:
                _add_error(
                    errors,
                    COMPANIES_FILE,
                    "duplicate_company_id",
                    f"duplicate company_id: {company_id}",
                    row_number=row_number,
                    record_id=record_id,
                    field="company_id",
                )
            else:
                company_ids.add(company_id)

        public_or_private = _text(row.get("public_or_private"))
        if public_or_private and public_or_private not in PublicOrPrivate.values():
            _add_error(
                errors,
                COMPANIES_FILE,
                "invalid_field_value",
                f"unsupported public_or_private: {public_or_private}",
                row_number=row_number,
                record_id=record_id,
                field="public_or_private",
            )
        _validate_row_source_ref(
            COMPANIES_FILE,
            row,
            row_number=row_number,
            record_id=record_id,
            source_refs=source_refs,
            valid_source_refs=valid_source_refs,
            errors=errors,
        )

    return company_ids


def _validate_presence(
    csv_data: _CsvData,
    company_ids: set[str],
    region_ids: set[str],
    source_refs: set[str],
    valid_source_refs: set[str],
    errors: list[ImportValidationIssue],
) -> None:
    seen: set[tuple[str, str]] = set()
    for row_number, row in csv_data.rows:
        record_id = _company_region_record_id(row, row_number)
        _validate_csv_row_required_fields(
            PRESENCE_FILE,
            csv_data,
            row,
            row_number,
            record_id,
            errors,
        )
        _validate_company_region_refs(
            PRESENCE_FILE,
            row,
            row_number,
            record_id,
            company_ids,
            region_ids,
            errors,
        )
        _validate_enum_field(
            PRESENCE_FILE,
            row,
            "presence_status",
            PresenceStatus.values(),
            row_number,
            record_id,
            errors,
        )
        _validate_enum_field(
            PRESENCE_FILE,
            row,
            "presence_basis",
            PresenceBasis.values(),
            row_number,
            record_id,
            errors,
        )
        _validate_duplicate_fact(
            file_name=PRESENCE_FILE,
            code="duplicate_presence_fact",
            key=(_text(row.get("company_id")), _text(row.get("region_id"))),
            seen=seen,
            row_number=row_number,
            record_id=record_id,
            errors=errors,
        )
        _validate_row_source_ref(
            PRESENCE_FILE,
            row,
            row_number=row_number,
            record_id=record_id,
            source_refs=source_refs,
            valid_source_refs=valid_source_refs,
            errors=errors,
        )


def _validate_hiring(
    csv_data: _CsvData,
    company_ids: set[str],
    region_ids: set[str],
    source_refs: set[str],
    valid_source_refs: set[str],
    errors: list[ImportValidationIssue],
) -> None:
    seen: set[tuple[str, str, str]] = set()
    for row_number, row in csv_data.rows:
        record_id = _company_region_record_id(row, row_number, extra_field="role_family")
        _validate_csv_row_required_fields(HIRING_FILE, csv_data, row, row_number, record_id, errors)
        _validate_company_region_refs(
            HIRING_FILE,
            row,
            row_number,
            record_id,
            company_ids,
            region_ids,
            errors,
        )
        _validate_enum_field(
            HIRING_FILE,
            row,
            "annualized_trend_signal",
            AnnualizedTrendSignal.values(),
            row_number,
            record_id,
            errors,
        )
        _validate_enum_field(
            HIRING_FILE,
            row,
            "seasonal_student_hiring_signal",
            SeasonalStudentHiringSignal.values(),
            row_number,
            record_id,
            errors,
        )
        role_family = _text(row.get("role_family"))
        if role_family and role_family not in DOCUMENTED_ROLE_FAMILIES:
            _add_error(
                errors,
                HIRING_FILE,
                "invalid_field_value",
                f"unsupported role_family: {role_family}",
                row_number=row_number,
                record_id=record_id,
                field="role_family",
            )
        _validate_duplicate_fact(
            file_name=HIRING_FILE,
            code="duplicate_hiring_fact",
            key=(
                _text(row.get("company_id")),
                _text(row.get("region_id")),
                _text(row.get("role_family")),
            ),
            seen=seen,
            row_number=row_number,
            record_id=record_id,
            errors=errors,
        )
        has_valid_source = _validate_row_source_ref(
            HIRING_FILE,
            row,
            row_number=row_number,
            record_id=record_id,
            source_refs=source_refs,
            valid_source_refs=valid_source_refs,
            errors=errors,
        )
        _validate_count_fields(
            HIRING_FILE,
            csv_data,
            row,
            row_number,
            record_id,
            has_valid_source,
            errors,
        )


def _validate_entry_level(
    csv_data: _CsvData,
    company_ids: set[str],
    region_ids: set[str],
    source_refs: set[str],
    valid_source_refs: set[str],
    errors: list[ImportValidationIssue],
) -> None:
    seen: set[tuple[str, str]] = set()
    for row_number, row in csv_data.rows:
        record_id = _company_region_record_id(row, row_number)
        _validate_csv_row_required_fields(
            ENTRY_LEVEL_FILE,
            csv_data,
            row,
            row_number,
            record_id,
            errors,
        )
        _validate_company_region_refs(
            ENTRY_LEVEL_FILE,
            row,
            row_number,
            record_id,
            company_ids,
            region_ids,
            errors,
        )
        _validate_enum_field(
            ENTRY_LEVEL_FILE,
            row,
            "student_season_recurrence_signal",
            StudentSeasonRecurrenceSignal.values(),
            row_number,
            record_id,
            errors,
        )
        _validate_boolean_unknown_field(
            ENTRY_LEVEL_FILE,
            row,
            "formal_early_career_program_flag",
            row_number,
            record_id,
            errors,
        )
        _validate_duplicate_fact(
            file_name=ENTRY_LEVEL_FILE,
            code="duplicate_entry_level_fact",
            key=(_text(row.get("company_id")), _text(row.get("region_id"))),
            seen=seen,
            row_number=row_number,
            record_id=record_id,
            errors=errors,
        )
        has_valid_source = _validate_row_source_ref(
            ENTRY_LEVEL_FILE,
            row,
            row_number=row_number,
            record_id=record_id,
            source_refs=source_refs,
            valid_source_refs=valid_source_refs,
            errors=errors,
        )
        _validate_count_fields(
            ENTRY_LEVEL_FILE,
            csv_data,
            row,
            row_number,
            record_id,
            has_valid_source,
            errors,
        )


def _validate_source_type(
    row: dict[str, str],
    row_number: int,
    record_id: str,
    errors: list[ImportValidationIssue],
) -> None:
    value = _text(row.get("source_type"))
    if not value:
        return
    try:
        source_type = SourceType(value)
    except ValueError:
        source_type = None
    if source_type not in ALLOWED_SOURCE_TYPES:
        _add_error(
            errors,
            SOURCE_REFS_FILE,
            "unsupported_source_type",
            f"unsupported source_type for curated imports: {value}",
            row_number=row_number,
            record_id=record_id,
            field="source_type",
        )


def _validate_license_or_terms(
    row: dict[str, str],
    row_number: int,
    record_id: str,
    errors: list[ImportValidationIssue],
) -> None:
    value = _text(row.get("license_or_terms_category"))
    if not value:
        return
    try:
        category = LicenseTermsCategory(value)
    except ValueError:
        category = None
    if category not in ALLOWED_LICENSE_OR_TERMS_CATEGORIES:
        _add_error(
            errors,
            SOURCE_REFS_FILE,
            "unsupported_license_or_terms_category",
            f"unsupported license_or_terms_category for curated imports: {value}",
            row_number=row_number,
            record_id=record_id,
            field="license_or_terms_category",
        )


def _validate_confidence(
    row: dict[str, str],
    row_number: int,
    record_id: str,
    errors: list[ImportValidationIssue],
) -> None:
    value = _text(row.get("confidence"))
    if value and value not in Confidence.values():
        _add_error(
            errors,
            SOURCE_REFS_FILE,
            "invalid_confidence",
            f"unsupported confidence value: {value}",
            row_number=row_number,
            record_id=record_id,
            field="confidence",
        )


def _validate_source_date(
    row: dict[str, str],
    field: str,
    row_number: int,
    record_id: str,
    errors: list[ImportValidationIssue],
) -> date | None:
    value = _text(row.get(field))
    if not value:
        return None
    try:
        return parse_import_date(value)
    except ValueError:
        _add_error(
            errors,
            SOURCE_REFS_FILE,
            "invalid_date_format",
            f"{field} must use YYYY-MM-DD ISO date format",
            row_number=row_number,
            record_id=record_id,
            field=field,
        )
        return None


def _validate_freshness_status(
    row: dict[str, str],
    row_number: int,
    record_id: str,
    errors: list[ImportValidationIssue],
) -> None:
    value = _text(row.get("freshness_status"))
    if not value:
        return
    if value not in ALLOWED_FRESHNESS_STATUSES:
        _add_error(
            errors,
            SOURCE_REFS_FILE,
            "invalid_freshness_status",
            f"unsupported freshness_status: {value}",
            row_number=row_number,
            record_id=record_id,
            field="freshness_status",
        )
        return
    if value == FreshnessStatus.STALE.value:
        _add_error(
            errors,
            SOURCE_REFS_FILE,
            "stale_source_date",
            "source_ref declares stale freshness_status",
            row_number=row_number,
            record_id=record_id,
            field="freshness_status",
        )


def _validate_csv_row_required_fields(
    file_name: str,
    csv_data: _CsvData,
    row: dict[str, str],
    row_number: int,
    record_id: str,
    errors: list[ImportValidationIssue],
) -> None:
    count_value_fields = {
        count_field for count_field, _status_field in COUNT_FIELDS_BY_FILE.get(file_name, ())
    }
    count_status_fields = {
        status_field for _count_field, status_field in COUNT_FIELDS_BY_FILE.get(file_name, ())
    }
    for field in CSV_REQUIRED_FIELDS[file_name]:
        if field not in csv_data.fieldnames:
            continue
        if field == "source_ref":
            continue
        if field in count_value_fields or field in count_status_fields:
            continue
        if _is_blank(row.get(field)):
            _add_error(
                errors,
                file_name,
                "missing_required_field",
                f"row {record_id} is missing required field {field}",
                row_number=row_number,
                record_id=record_id,
                field=field,
            )


def _validate_company_region_refs(
    file_name: str,
    row: dict[str, str],
    row_number: int,
    record_id: str,
    company_ids: set[str],
    region_ids: set[str],
    errors: list[ImportValidationIssue],
) -> None:
    company_id = _text(row.get("company_id"))
    region_id = _text(row.get("region_id"))
    if company_id and company_id not in company_ids:
        _add_error(
            errors,
            file_name,
            "invalid_company_id",
            f"company_id does not reference a known company: {company_id}",
            row_number=row_number,
            record_id=record_id,
            field="company_id",
        )
    if region_id and region_id not in region_ids:
        _add_error(
            errors,
            file_name,
            "invalid_region_id",
            f"region_id does not reference a known region: {region_id}",
            row_number=row_number,
            record_id=record_id,
            field="region_id",
        )


def _validate_row_source_ref(
    file_name: str,
    row: dict[str, Any],
    *,
    row_number: int,
    record_id: str,
    source_refs: set[str],
    valid_source_refs: set[str],
    errors: list[ImportValidationIssue],
) -> bool:
    source_ref = _text(row.get("source_ref"))
    if not source_ref:
        _add_error(
            errors,
            file_name,
            "missing_source_ref",
            f"row {record_id} has no source_ref; no source, no canonical fact",
            row_number=row_number,
            record_id=record_id,
            field="source_ref",
        )
        return False
    if source_ref not in source_refs:
        _add_error(
            errors,
            file_name,
            "invalid_source_ref",
            f"source_ref does not exist in source_refs.csv: {source_ref}",
            row_number=row_number,
            record_id=record_id,
            field="source_ref",
        )
        return False
    if source_ref not in valid_source_refs:
        _add_error(
            errors,
            file_name,
            "invalid_source_ref",
            f"source_ref is present but invalid for canonical use: {source_ref}",
            row_number=row_number,
            record_id=record_id,
            field="source_ref",
        )
        return False
    return True


def _validate_count_fields(
    file_name: str,
    csv_data: _CsvData,
    row: dict[str, str],
    row_number: int,
    record_id: str,
    has_valid_source: bool,
    errors: list[ImportValidationIssue],
) -> None:
    for count_field, status_field in COUNT_FIELDS_BY_FILE.get(file_name, ()):
        if count_field not in csv_data.fieldnames or status_field not in csv_data.fieldnames:
            continue
        count_value = _text(row.get(count_field))
        status_value = _text(row.get(status_field))
        if count_value.lower() in AMBIGUOUS_UNKNOWN_COUNT_VALUES:
            _add_error(
                errors,
                file_name,
                "invalid_unknown_encoding",
                (
                    f"{count_field} uses ambiguous unknown encoding; use a blank "
                    f"value with {status_field}=unknown/not_collected/not_applicable"
                ),
                row_number=row_number,
                record_id=record_id,
                field=count_field,
            )
            return
        if not status_value:
            _add_error(
                errors,
                file_name,
                "ambiguous_count_encoding",
                f"{count_field} requires explicit {status_field}",
                row_number=row_number,
                record_id=record_id,
                field=status_field,
            )
            return
        try:
            status = ObservationStatus(status_value)
        except ValueError:
            _add_error(
                errors,
                file_name,
                "invalid_count_status",
                f"unsupported count status for {count_field}: {status_value}",
                row_number=row_number,
                record_id=record_id,
                field=status_field,
            )
            return
        if status not in IMPORT_COUNT_STATUSES:
            _add_error(
                errors,
                file_name,
                "invalid_count_status",
                f"unsupported count status for {count_field}: {status_value}",
                row_number=row_number,
                record_id=record_id,
                field=status_field,
            )
            return
        if status in UNOBSERVED_COUNT_STATUSES:
            if count_value:
                _add_error(
                    errors,
                    file_name,
                    "ambiguous_count_encoding",
                    f"{count_field} must be blank when {status_field}={status.value}",
                    row_number=row_number,
                    record_id=record_id,
                    field=count_field,
                )
            return

        parsed_count = _parse_non_negative_int(
            count_value,
            file_name=file_name,
            row_number=row_number,
            record_id=record_id,
            field=count_field,
            errors=errors,
        )
        if parsed_count is None:
            return
        if status is ObservationStatus.ZERO_OBSERVED and parsed_count != 0:
            _add_error(
                errors,
                file_name,
                "ambiguous_count_encoding",
                f"{count_field} must be 0 when {status_field}=zero_observed",
                row_number=row_number,
                record_id=record_id,
                field=count_field,
            )
        if status is ObservationStatus.POSITIVE_OBSERVED and parsed_count <= 0:
            _add_error(
                errors,
                file_name,
                "ambiguous_count_encoding",
                f"{count_field} must be positive when {status_field}=positive_observed",
                row_number=row_number,
                record_id=record_id,
                field=count_field,
            )
        if status in OBSERVED_COUNT_STATUSES and not has_valid_source:
            _add_error(
                errors,
                file_name,
                "observed_count_without_valid_source",
                f"{count_field} is observed but the row lacks a valid source_ref",
                row_number=row_number,
                record_id=record_id,
                field=count_field,
            )


def _parse_non_negative_int(
    value: str,
    *,
    file_name: str,
    row_number: int,
    record_id: str,
    field: str,
    errors: list[ImportValidationIssue],
) -> int | None:
    if not value:
        _add_error(
            errors,
            file_name,
            "ambiguous_count_encoding",
            f"{field} requires an explicit non-negative integer for observed counts",
            row_number=row_number,
            record_id=record_id,
            field=field,
        )
        return None
    try:
        parsed = int(value)
    except ValueError:
        _add_error(
            errors,
            file_name,
            "invalid_count_encoding",
            f"{field} must be a non-negative integer or blank for unknown states",
            row_number=row_number,
            record_id=record_id,
            field=field,
        )
        return None
    if parsed < 0:
        _add_error(
            errors,
            file_name,
            "invalid_count_encoding",
            f"{field} must be non-negative",
            row_number=row_number,
            record_id=record_id,
            field=field,
        )
        return None
    return parsed


def _validate_identifier(
    value: str,
    *,
    file_name: str,
    field: str,
    row_number: int,
    record_id: str,
    code: str,
    errors: list[ImportValidationIssue],
) -> bool:
    if _ID_PATTERN.fullmatch(value):
        return True
    _add_error(
        errors,
        file_name,
        code,
        f"{field} must match lowercase snake_case import ID format: {value}",
        row_number=row_number,
        record_id=record_id,
        field=field,
    )
    return False


def _validate_enum_field(
    file_name: str,
    row: dict[str, str],
    field: str,
    allowed_values: frozenset[str],
    row_number: int,
    record_id: str,
    errors: list[ImportValidationIssue],
) -> None:
    value = _text(row.get(field))
    if value and value not in allowed_values:
        _add_error(
            errors,
            file_name,
            "invalid_field_value",
            f"unsupported {field}: {value}",
            row_number=row_number,
            record_id=record_id,
            field=field,
        )


def _validate_boolean_unknown_field(
    file_name: str,
    row: dict[str, str],
    field: str,
    row_number: int,
    record_id: str,
    errors: list[ImportValidationIssue],
) -> None:
    value = _text(row.get(field))
    if value and value not in {"true", "false", "unknown"}:
        _add_error(
            errors,
            file_name,
            "invalid_field_value",
            f"{field} must be true, false, or unknown",
            row_number=row_number,
            record_id=record_id,
            field=field,
        )


def _validate_duplicate_fact(
    *,
    file_name: str,
    code: str,
    key: tuple[str, ...],
    seen: set[Any],
    row_number: int,
    record_id: str,
    errors: list[ImportValidationIssue],
) -> None:
    if any(not item for item in key):
        return
    if key in seen:
        _add_error(
            errors,
            file_name,
            code,
            f"duplicate fact key: {'/'.join(key)}",
            row_number=row_number,
            record_id=record_id,
        )
        return
    seen.add(key)


def _company_region_record_id(
    row: dict[str, str],
    row_number: int,
    *,
    extra_field: str | None = None,
) -> str:
    parts = [_text(row.get("company_id")), _text(row.get("region_id"))]
    if extra_field is not None:
        parts.append(_text(row.get(extra_field)))
    if all(parts):
        return "/".join(parts)
    return f"row:{row_number}"


def _add_error(
    errors: list[ImportValidationIssue],
    file_name: str,
    code: str,
    message: str,
    *,
    row_number: int | None = None,
    record_id: str | None = None,
    field: str | None = None,
) -> None:
    errors.append(
        ImportValidationIssue(
            file=file_name,
            row_number=row_number,
            record_id=record_id,
            field=field,
            code=code,
            message=message,
        )
    )


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_blank(value: Any) -> bool:
    return _text(value) == ""


def _json_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return not value
    return False
