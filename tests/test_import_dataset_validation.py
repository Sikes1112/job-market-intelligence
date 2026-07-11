from __future__ import annotations

import csv
import json
import shutil
from datetime import date
from pathlib import Path

from backend.imports.validation import ImportValidationResult, validate_import_dataset

REPO_ROOT = Path(__file__).resolve().parent.parent
NYC_IMPORT_DIR = REPO_ROOT / "data" / "imports" / "nyc"
AS_OF = date(2026, 7, 9)


def test_valid_nyc_dataset_loads_successfully() -> None:
    result = _validate(NYC_IMPORT_DIR)

    assert result.ok
    assert result.errors == ()
    assert result.summary.as_dict() == {
        "region_count": 1,
        "company_count": 3,
        "presence_fact_count": 3,
        "hiring_fact_count": 3,
        "entry_level_fact_count": 3,
        "source_ref_count": 5,
    }


def test_all_required_files_are_enforced(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    (dataset / "hiring.csv").unlink()

    result = _validate(dataset)

    assert _has_error(result, "missing_required_file", file="hiring.csv")


def test_missing_required_fields_fail_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    _remove_csv_field(dataset / "companies.csv", "sector")

    result = _validate(dataset)

    assert _has_error(result, "missing_required_field", file="companies.csv", field="sector")


def test_missing_source_refs_fail_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    _update_csv_row(dataset / "presence.csv", 0, {"source_ref": ""})

    result = _validate(dataset)

    assert _has_error(result, "missing_source_ref", file="presence.csv", field="source_ref")


def test_invalid_source_refs_fail_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    _update_csv_row(dataset / "presence.csv", 0, {"source_ref": "src_missing"})

    result = _validate(dataset)

    assert _has_error(result, "invalid_source_ref", file="presence.csv", field="source_ref")


def test_source_refs_missing_provenance_fail_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    _update_source_ref(
        dataset,
        "src_nyc_presence_observation_2026_06",
        {"observed_at": ""},
    )

    result = _validate(dataset)

    assert _has_error(
        result,
        "missing_provenance_field",
        file="source_refs.csv",
        field="observed_at",
    )


def test_unsupported_source_type_fails_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    _update_source_ref(
        dataset,
        "src_nyc_hiring_snapshot_2026_06",
        {"source_type": "llm_generated"},
    )

    result = _validate(dataset)

    assert _has_error(
        result,
        "unsupported_source_type",
        file="source_refs.csv",
        field="source_type",
    )


def test_unsupported_license_or_terms_category_fails_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    _update_source_ref(
        dataset,
        "src_nyc_hiring_snapshot_2026_06",
        {"license_or_terms_category": "prohibited"},
    )

    result = _validate(dataset)

    assert _has_error(
        result,
        "unsupported_license_or_terms_category",
        file="source_refs.csv",
        field="license_or_terms_category",
    )


def test_invalid_date_format_fails_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    _update_source_ref(
        dataset,
        "src_nyc_hiring_snapshot_2026_06",
        {"observed_at": "06/15/2026"},
    )

    result = _validate(dataset)

    assert _has_error(
        result,
        "invalid_date_format",
        file="source_refs.csv",
        field="observed_at",
    )


def test_invalid_confidence_fails_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    _update_source_ref(
        dataset,
        "src_nyc_hiring_snapshot_2026_06",
        {"confidence": "certain"},
    )

    result = _validate(dataset)

    assert _has_error(result, "invalid_confidence", file="source_refs.csv", field="confidence")


def test_duplicate_company_ids_fail_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    rows = _read_csv(dataset / "companies.csv")
    _append_csv_row(dataset / "companies.csv", rows[0])

    result = _validate(dataset)

    assert _has_error(result, "duplicate_company_id", file="companies.csv")


def test_duplicate_region_ids_fail_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    path = dataset / "regions.json"
    regions = json.loads(path.read_text())
    regions.append(dict(regions[0]))
    path.write_text(json.dumps(regions, indent=2) + "\n")

    result = _validate(dataset)

    assert _has_error(result, "duplicate_region_id", file="regions.json")


def test_duplicate_presence_facts_fail_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    rows = _read_csv(dataset / "presence.csv")
    _append_csv_row(dataset / "presence.csv", rows[0])

    result = _validate(dataset)

    assert _has_error(result, "duplicate_presence_fact", file="presence.csv")


def test_duplicate_hiring_facts_fail_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    rows = _read_csv(dataset / "hiring.csv")
    _append_csv_row(dataset / "hiring.csv", rows[0])

    result = _validate(dataset)

    assert _has_error(result, "duplicate_hiring_fact", file="hiring.csv")


def test_duplicate_entry_level_facts_fail_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    rows = _read_csv(dataset / "entry_level.csv")
    _append_csv_row(dataset / "entry_level.csv", rows[0])

    result = _validate(dataset)

    assert _has_error(result, "duplicate_entry_level_fact", file="entry_level.csv")


def test_stale_source_dates_fail_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    _update_source_ref(
        dataset,
        "src_nyc_hiring_snapshot_2026_06",
        {"observed_at": "2025-01-01"},
    )

    result = _validate(dataset)

    assert _has_error(result, "stale_source_date", file="source_refs.csv", field="observed_at")


def test_unknown_count_is_not_treated_as_zero(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    _update_csv_row(
        dataset / "hiring.csv",
        2,
        {"active_posting_count": "unknown", "active_posting_count_status": "unknown"},
    )

    result = _validate(dataset)

    assert _has_error(result, "invalid_unknown_encoding", file="hiring.csv")


def test_sourced_observed_zero_is_allowed(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    _update_csv_row(
        dataset / "entry_level.csv",
        2,
        {"internship_count": "0", "internship_count_status": "zero_observed"},
    )

    result = _validate(dataset)

    assert result.ok


def test_ambiguous_blank_count_encoding_fails_validation(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    _update_csv_row(
        dataset / "hiring.csv",
        0,
        {"active_posting_count": "", "active_posting_count_status": ""},
    )

    result = _validate(dataset)

    assert _has_error(result, "ambiguous_count_encoding", file="hiring.csv")


def test_validation_returns_deterministic_structured_errors(tmp_path: Path) -> None:
    dataset = _copy_dataset(tmp_path)
    _update_csv_row(dataset / "presence.csv", 0, {"source_ref": ""})
    _update_source_ref(
        dataset,
        "src_nyc_hiring_snapshot_2026_06",
        {"confidence": "certain"},
    )

    first = _validate(dataset)
    second = _validate(dataset)

    assert first.errors == second.errors
    assert first.errors
    first_error = first.errors[0]
    assert first_error.file
    assert first_error.code
    assert first_error.message
    assert first_error.as_dict()["code"] == first_error.code


def _validate(path: Path) -> ImportValidationResult:
    return validate_import_dataset(path, as_of=AS_OF)


def _copy_dataset(tmp_path: Path) -> Path:
    target = tmp_path / "nyc"
    shutil.copytree(NYC_IMPORT_DIR, target)
    return target


def _has_error(
    result: ImportValidationResult,
    code: str,
    *,
    file: str | None = None,
    field: str | None = None,
) -> bool:
    return any(
        issue.code == code
        and (file is None or issue.file == file)
        and (field is None or issue.field == field)
        for issue in result.errors
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _update_csv_row(path: Path, row_index: int, updates: dict[str, str]) -> None:
    rows = _read_csv(path)
    fieldnames = list(rows[0].keys())
    rows[row_index].update(updates)
    _write_csv(path, rows, fieldnames)


def _append_csv_row(path: Path, row: dict[str, str]) -> None:
    rows = _read_csv(path)
    fieldnames = list(rows[0].keys())
    rows.append(dict(row))
    _write_csv(path, rows, fieldnames)


def _remove_csv_field(path: Path, field: str) -> None:
    rows = _read_csv(path)
    fieldnames = [name for name in rows[0] if name != field]
    stripped_rows = [{name: row[name] for name in fieldnames} for row in rows]
    _write_csv(path, stripped_rows, fieldnames)


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
