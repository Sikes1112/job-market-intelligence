"""Curated market registry for deterministic market imports."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from backend.imports.contracts import REGIONS_FILE
from backend.imports.provenance import parse_import_date

MARKET_REGISTRY_FILE = "markets.json"

REQUIRED_MARKET_FIELDS: tuple[str, ...] = (
    "market_key",
    "region_id",
    "display_name",
    "dataset_path",
    "coverage_status",
    "import_status",
    "last_curated_at",
    "peer_group",
)

SUPPORTED_COVERAGE_STATUSES: frozenset[str] = frozenset(
    {
        "curated",
        "partial_curated",
    }
)

SUPPORTED_IMPORT_STATUSES: frozenset[str] = frozenset(
    {
        "ready",
        "paused",
    }
)

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,127}$")


@dataclass(frozen=True, slots=True)
class MarketRegistryIssue:
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
class CuratedMarketRegistryEntry:
    market_key: str
    region_id: str
    display_name: str
    dataset_path: Path
    coverage_status: str
    import_status: str
    last_curated_at: str
    peer_group: str
    notes: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MarketRegistryValidationResult:
    errors: tuple[MarketRegistryIssue, ...]
    warnings: tuple[MarketRegistryIssue, ...]
    entries: tuple[CuratedMarketRegistryEntry, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def by_market_key(self) -> MappingProxyType[str, CuratedMarketRegistryEntry]:
        return MappingProxyType({entry.market_key: entry for entry in self.entries})


class MarketRegistryError(ValueError):
    def __init__(self, errors: tuple[MarketRegistryIssue, ...]) -> None:
        self.errors = errors
        message = "; ".join(error.message for error in errors)
        super().__init__(message or "invalid curated market registry")


def default_market_registry_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "imports" / MARKET_REGISTRY_FILE


def validate_market_registry(
    registry_path: str | Path | None = None,
) -> MarketRegistryValidationResult:
    path = Path(registry_path) if registry_path is not None else default_market_registry_path()
    errors: list[MarketRegistryIssue] = []
    warnings: list[MarketRegistryIssue] = []
    entries: list[CuratedMarketRegistryEntry] = []

    if not path.is_file():
        errors.append(
            MarketRegistryIssue(
                file=MARKET_REGISTRY_FILE,
                code="missing_market_registry",
                message=f"curated market registry is missing: {path}",
            )
        )
        return MarketRegistryValidationResult(
            errors=tuple(errors),
            warnings=tuple(warnings),
            entries=(),
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(
            MarketRegistryIssue(
                file=MARKET_REGISTRY_FILE,
                code="registry_read_error",
                message=f"could not read curated market registry: {exc}",
            )
        )
        return MarketRegistryValidationResult(
            errors=tuple(errors),
            warnings=tuple(warnings),
            entries=(),
        )

    if not isinstance(raw, list):
        errors.append(
            MarketRegistryIssue(
                file=MARKET_REGISTRY_FILE,
                code="invalid_registry_shape",
                message="markets.json must contain a JSON array of market records",
            )
        )
        return MarketRegistryValidationResult(
            errors=tuple(errors),
            warnings=tuple(warnings),
            entries=(),
        )

    seen_market_keys: set[str] = set()
    seen_region_ids: set[str] = set()
    for row_number, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            errors.append(
                MarketRegistryIssue(
                    file=MARKET_REGISTRY_FILE,
                    code="invalid_registry_record",
                    message="market registry records must be JSON objects",
                    row_number=row_number,
                )
            )
            continue
        before = len(errors)
        _validate_required_fields(item, row_number, errors)

        market_key = _text(item.get("market_key"))
        region_id = _text(item.get("region_id"))
        record_id = market_key or f"record:{row_number}"

        _validate_identifier(
            market_key,
            field="market_key",
            code="invalid_market_key",
            row_number=row_number,
            record_id=record_id,
            errors=errors,
        )
        _validate_identifier(
            region_id,
            field="region_id",
            code="invalid_region_id",
            row_number=row_number,
            record_id=record_id,
            errors=errors,
        )

        if market_key:
            if market_key in seen_market_keys:
                errors.append(
                    MarketRegistryIssue(
                        file=MARKET_REGISTRY_FILE,
                        code="duplicate_market_key",
                        message=f"duplicate market_key: {market_key}",
                        row_number=row_number,
                        record_id=record_id,
                        field="market_key",
                    )
                )
            seen_market_keys.add(market_key)

        if region_id:
            if region_id in seen_region_ids:
                errors.append(
                    MarketRegistryIssue(
                        file=MARKET_REGISTRY_FILE,
                        code="duplicate_region_id",
                        message=f"duplicate registry region_id: {region_id}",
                        row_number=row_number,
                        record_id=record_id,
                        field="region_id",
                    )
                )
            seen_region_ids.add(region_id)

        coverage_status = _text(item.get("coverage_status"))
        if coverage_status and coverage_status not in SUPPORTED_COVERAGE_STATUSES:
            errors.append(
                MarketRegistryIssue(
                    file=MARKET_REGISTRY_FILE,
                    code="unsupported_coverage_status",
                    message=f"unsupported coverage_status: {coverage_status}",
                    row_number=row_number,
                    record_id=record_id,
                    field="coverage_status",
                )
            )

        import_status = _text(item.get("import_status"))
        if import_status and import_status not in SUPPORTED_IMPORT_STATUSES:
            errors.append(
                MarketRegistryIssue(
                    file=MARKET_REGISTRY_FILE,
                    code="unsupported_import_status",
                    message=f"unsupported import_status: {import_status}",
                    row_number=row_number,
                    record_id=record_id,
                    field="import_status",
                )
            )

        last_curated_at = _text(item.get("last_curated_at"))
        if last_curated_at:
            try:
                parse_import_date(last_curated_at)
            except ValueError:
                errors.append(
                    MarketRegistryIssue(
                        file=MARKET_REGISTRY_FILE,
                        code="invalid_date_format",
                        message="last_curated_at must use YYYY-MM-DD ISO date format",
                        row_number=row_number,
                        record_id=record_id,
                        field="last_curated_at",
                    )
                )

        dataset_path = _resolve_dataset_path(
            path,
            item.get("dataset_path"),
            row_number=row_number,
            record_id=record_id,
            errors=errors,
        )
        if market_key and dataset_path is not None and dataset_path.name != market_key:
            errors.append(
                MarketRegistryIssue(
                    file=MARKET_REGISTRY_FILE,
                    code="market_key_dataset_path_mismatch",
                    message=(
                        "registry dataset_path final directory must match "
                        f"market_key {market_key!r}"
                    ),
                    row_number=row_number,
                    record_id=record_id,
                    field="dataset_path",
                )
            )

        if dataset_path is not None and region_id:
            _validate_registry_region_matches_dataset(
                dataset_path,
                region_id,
                row_number=row_number,
                record_id=record_id,
                errors=errors,
            )

        if len(errors) == before and dataset_path is not None:
            entries.append(
                CuratedMarketRegistryEntry(
                    market_key=market_key,
                    region_id=region_id,
                    display_name=_text(item.get("display_name")),
                    dataset_path=dataset_path,
                    coverage_status=coverage_status,
                    import_status=import_status,
                    last_curated_at=last_curated_at,
                    peer_group=_text(item.get("peer_group")),
                    notes=_optional_text(item.get("notes")),
                    warnings=_string_tuple(item.get("warnings")),
                )
            )

    return MarketRegistryValidationResult(
        errors=tuple(errors),
        warnings=tuple(warnings),
        entries=tuple(entries),
    )


def load_market_registry(
    registry_path: str | Path | None = None,
) -> MappingProxyType[str, CuratedMarketRegistryEntry]:
    result = validate_market_registry(registry_path)
    if not result.ok:
        raise MarketRegistryError(result.errors)
    return result.by_market_key


def resolve_market_registry_entry(
    market_key: str,
    registry_path: str | Path | None = None,
) -> CuratedMarketRegistryEntry:
    registry = load_market_registry(registry_path)
    try:
        return registry[market_key]
    except KeyError as exc:
        raise KeyError(f"unknown curated market_key: {market_key}") from exc


def _validate_required_fields(
    item: dict[str, Any],
    row_number: int,
    errors: list[MarketRegistryIssue],
) -> None:
    record_id = _text(item.get("market_key")) or f"record:{row_number}"
    for field in REQUIRED_MARKET_FIELDS:
        if _json_blank(item.get(field)):
            errors.append(
                MarketRegistryIssue(
                    file=MARKET_REGISTRY_FILE,
                    code="missing_required_field",
                    message=f"market registry record {record_id} is missing {field}",
                    row_number=row_number,
                    record_id=record_id,
                    field=field,
                )
            )


def _validate_identifier(
    value: str,
    *,
    field: str,
    code: str,
    row_number: int,
    record_id: str,
    errors: list[MarketRegistryIssue],
) -> None:
    if not value:
        return
    if not _ID_PATTERN.fullmatch(value):
        errors.append(
            MarketRegistryIssue(
                file=MARKET_REGISTRY_FILE,
                code=code,
                message=f"{field} must be lowercase snake_case: {value}",
                row_number=row_number,
                record_id=record_id,
                field=field,
            )
        )


def _resolve_dataset_path(
    registry_path: Path,
    raw_value: Any,
    *,
    row_number: int,
    record_id: str,
    errors: list[MarketRegistryIssue],
) -> Path | None:
    dataset_path = _text(raw_value)
    if not dataset_path:
        return None
    path = Path(dataset_path)
    if not path.is_absolute():
        path = registry_path.parent / path
    path = path.resolve()
    if not path.is_dir():
        errors.append(
            MarketRegistryIssue(
                file=MARKET_REGISTRY_FILE,
                code="invalid_dataset_path",
                message=f"registry dataset_path does not exist: {path}",
                row_number=row_number,
                record_id=record_id,
                field="dataset_path",
            )
        )
        return None
    return path


def _validate_registry_region_matches_dataset(
    dataset_path: Path,
    region_id: str,
    *,
    row_number: int,
    record_id: str,
    errors: list[MarketRegistryIssue],
) -> None:
    regions_path = dataset_path / REGIONS_FILE
    if not regions_path.is_file():
        return
    try:
        raw = json.loads(regions_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return
    if not isinstance(raw, list):
        return
    dataset_region_ids = {
        _text(record.get("region_id"))
        for record in raw
        if isinstance(record, dict) and _text(record.get("region_id"))
    }
    if dataset_region_ids != {region_id}:
        errors.append(
            MarketRegistryIssue(
                file=MARKET_REGISTRY_FILE,
                code="registry_region_id_mismatch",
                message=(
                    f"registry region_id {region_id!r} does not match "
                    f"dataset regions {sorted(dataset_region_ids)!r}"
                ),
                row_number=row_number,
                record_id=record_id,
                field="region_id",
            )
        )


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    return ()


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _json_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False
