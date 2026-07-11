from __future__ import annotations

import csv
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from backend.imports.registry import (
    load_market_registry,
    validate_market_registry,
)
from backend.imports.validation import (
    ImportValidationResult,
    validate_curated_market_dataset,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPORT_ROOT = REPO_ROOT / "data" / "imports"
REGISTRY_PATH = IMPORT_ROOT / "markets.json"
AS_OF = date(2026, 7, 9)
EXPECTED_MARKET_KEYS = {
    "nyc",
    "seattle",
    "san_francisco_bay_area",
    "boston",
    "washington_dc",
    "austin",
    "atlanta",
    "chicago",
}


def test_market_registry_loads_registered_markets() -> None:
    result = validate_market_registry(REGISTRY_PATH)
    registry = load_market_registry(REGISTRY_PATH)

    assert result.ok
    assert set(registry) == EXPECTED_MARKET_KEYS
    assert registry["nyc"].region_id == "greater_nyc"
    assert registry["seattle"].region_id == "greater_seattle"
    assert registry["san_francisco_bay_area"].region_id == "sf_bay_area"
    assert registry["seattle"].dataset_path == IMPORT_ROOT / "seattle"


def test_duplicate_market_keys_fail(tmp_path: Path) -> None:
    root = _copy_import_root(tmp_path)
    records = _read_registry(root)
    records[1]["market_key"] = "nyc"
    records[1]["dataset_path"] = "nyc"
    _write_registry(root, records)

    result = validate_market_registry(root / "markets.json")

    assert _has_registry_error(result, "duplicate_market_key")


def test_duplicate_region_ids_fail(tmp_path: Path) -> None:
    root = _copy_import_root(tmp_path)
    records = _read_registry(root)
    records[1]["region_id"] = "greater_nyc"
    _write_registry(root, records)

    result = validate_market_registry(root / "markets.json")

    assert _has_registry_error(result, "duplicate_region_id")


def test_missing_required_registry_fields_fail(tmp_path: Path) -> None:
    root = _copy_import_root(tmp_path)
    records = _read_registry(root)
    del records[0]["dataset_path"]
    _write_registry(root, records)

    result = validate_market_registry(root / "markets.json")

    assert _has_registry_error(result, "missing_required_field", field="dataset_path")


def test_unsupported_registry_statuses_fail(tmp_path: Path) -> None:
    root = _copy_import_root(tmp_path)
    records = _read_registry(root)
    records[0]["coverage_status"] = "scraped"
    records[1]["import_status"] = "scheduled"
    _write_registry(root, records)

    result = validate_market_registry(root / "markets.json")

    assert _has_registry_error(result, "unsupported_coverage_status")
    assert _has_registry_error(result, "unsupported_import_status")


def test_invalid_registry_date_and_dataset_path_fail(tmp_path: Path) -> None:
    root = _copy_import_root(tmp_path)
    records = _read_registry(root)
    records[0]["last_curated_at"] = "06/15/2026"
    records[1]["dataset_path"] = "missing_seattle"
    _write_registry(root, records)

    result = validate_market_registry(root / "markets.json")

    assert _has_registry_error(result, "invalid_date_format")
    assert _has_registry_error(result, "invalid_dataset_path")


def test_registry_region_id_mismatch_fails(tmp_path: Path) -> None:
    root = _copy_import_root(tmp_path)
    records = _read_registry(root)
    records[1]["region_id"] = "greater_nyc"
    records[1]["dataset_path"] = "seattle"
    _write_registry(root, records)

    result = validate_market_registry(root / "markets.json")

    assert _has_registry_error(result, "registry_region_id_mismatch")


def test_market_key_dataset_path_mismatch_fails(tmp_path: Path) -> None:
    root = _copy_import_root(tmp_path)
    records = _read_registry(root)
    records[1]["dataset_path"] = "nyc"
    _write_registry(root, records)

    result = validate_market_registry(root / "markets.json")

    assert _has_registry_error(result, "market_key_dataset_path_mismatch")


def test_invalid_market_key_fails_registry_aware_validation() -> None:
    result = validate_curated_market_dataset(
        "not_registered",
        registry_path=REGISTRY_PATH,
        as_of=AS_OF,
    )

    assert _has_validation_error(result, "invalid_market_key", file="markets.json")


def test_nyc_validates_through_market_registry() -> None:
    result = validate_curated_market_dataset(
        "nyc",
        registry_path=REGISTRY_PATH,
        as_of=AS_OF,
    )

    assert result.ok
    assert result.summary.region_count == 1
    assert result.summary.company_count == 3


def test_seattle_validates_through_market_registry() -> None:
    result = validate_curated_market_dataset(
        "seattle",
        registry_path=REGISTRY_PATH,
        as_of=AS_OF,
    )

    assert result.ok
    assert result.summary.as_dict() == {
        "region_count": 1,
        "company_count": 3,
        "presence_fact_count": 3,
        "hiring_fact_count": 3,
        "entry_level_fact_count": 3,
        "source_ref_count": 5,
    }


def test_registry_aware_validation_enforces_required_files_per_market(
    tmp_path: Path,
) -> None:
    root = _copy_import_root(tmp_path)
    (root / "seattle" / "hiring.csv").unlink()

    result = validate_curated_market_dataset(
        "seattle",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )

    assert _has_validation_error(result, "missing_required_file", file="hiring.csv")


def test_registry_aware_validation_rejects_unknown_company_refs_per_market(
    tmp_path: Path,
) -> None:
    root = _copy_import_root(tmp_path)
    _update_csv_row(
        root / "seattle" / "presence.csv",
        0,
        {"company_id": "cmp_missing_company"},
    )

    result = validate_curated_market_dataset(
        "seattle",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )

    assert _has_validation_error(result, "invalid_company_id", file="presence.csv")


@pytest.mark.parametrize(
    ("file_name", "error_code"),
    (
        ("presence.csv", "duplicate_presence_fact"),
        ("hiring.csv", "duplicate_hiring_fact"),
        ("entry_level.csv", "duplicate_entry_level_fact"),
    ),
)
def test_registry_aware_validation_rejects_duplicate_facts_per_market(
    tmp_path: Path,
    file_name: str,
    error_code: str,
) -> None:
    root = _copy_import_root(tmp_path)
    path = root / "seattle" / file_name
    rows = _read_csv(path)
    _append_csv_row(path, rows[0])

    result = validate_curated_market_dataset(
        "seattle",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )

    assert _has_validation_error(result, error_code, file=file_name)


def test_registry_aware_stale_source_validation_is_deterministic(
    tmp_path: Path,
) -> None:
    root = _copy_import_root(tmp_path)
    _update_source_ref(
        root / "seattle",
        "src_seattle_hiring_snapshot_2026_06",
        {"observed_at": "2025-01-01"},
    )

    first = validate_curated_market_dataset(
        "seattle",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )
    second = validate_curated_market_dataset(
        "seattle",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )

    assert _has_validation_error(first, "stale_source_date", file="source_refs.csv")
    assert first.errors == second.errors


def test_registry_aware_validation_rejects_cross_market_source_refs(
    tmp_path: Path,
) -> None:
    root = _copy_import_root(tmp_path)
    _replace_text(
        root / "seattle" / "source_refs.csv",
        "src_seattle_company_roster_2026_06",
        "src_nyc_company_roster_2026_06",
    )
    _replace_text(
        root / "seattle" / "companies.csv",
        "src_seattle_company_roster_2026_06",
        "src_nyc_company_roster_2026_06",
    )

    result = validate_curated_market_dataset(
        "seattle",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )

    assert _has_validation_error(result, "source_ref_market_mismatch")


def test_registry_aware_validation_rejects_wrong_region_refs(
    tmp_path: Path,
) -> None:
    root = _copy_import_root(tmp_path)
    hiring = root / "seattle" / "hiring.csv"
    text = hiring.read_text(encoding="utf-8")
    hiring.write_text(
        text.replace("greater_seattle", "greater_nyc", 1),
        encoding="utf-8",
    )

    result = validate_curated_market_dataset(
        "seattle",
        registry_path=root / "markets.json",
        as_of=AS_OF,
    )

    assert _has_validation_error(result, "invalid_region_id", file="hiring.csv")


def _copy_import_root(tmp_path: Path) -> Path:
    root = tmp_path / "imports"
    shutil.copytree(IMPORT_ROOT, root)
    return root


def _read_registry(root: Path) -> list[dict[str, str]]:
    return json.loads((root / "markets.json").read_text(encoding="utf-8"))


def _write_registry(root: Path, records: list[dict[str, str]]) -> None:
    (root / "markets.json").write_text(
        json.dumps(records, indent=2) + "\n",
        encoding="utf-8",
    )


def _replace_text(path: Path, old: str, new: str) -> None:
    path.write_text(
        path.read_text(encoding="utf-8").replace(old, new),
        encoding="utf-8",
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _append_csv_row(path: Path, row: dict[str, str]) -> None:
    rows = _read_csv(path)
    fieldnames = list(rows[0].keys())
    rows.append(dict(row))
    _write_csv(path, rows, fieldnames)


def _update_csv_row(path: Path, row_index: int, updates: dict[str, str]) -> None:
    rows = _read_csv(path)
    fieldnames = list(rows[0].keys())
    rows[row_index].update(updates)
    _write_csv(path, rows, fieldnames)


def _update_source_ref(dataset: Path, source_ref: str, updates: dict[str, str]) -> None:
    path = dataset / "source_refs.csv"
    rows = _read_csv(path)
    fieldnames = list(rows[0].keys())
    for row in rows:
        if row["source_ref"] == source_ref:
            row.update(updates)
            break
    else:
        raise AssertionError(f"source_ref not found in fixture: {source_ref}")
    _write_csv(path, rows, fieldnames)


def _has_registry_error(result, code: str, *, field: str | None = None) -> bool:
    return any(
        issue.code == code and (field is None or issue.field == field)
        for issue in result.errors
    )


def _has_validation_error(
    result: ImportValidationResult,
    code: str,
    *,
    file: str | None = None,
) -> bool:
    return any(
        issue.code == code and (file is None or issue.file == file)
        for issue in result.errors
    )
