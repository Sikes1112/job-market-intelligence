from __future__ import annotations

import csv
import shutil
import socket
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.imports.nyc import import_nyc_dataset
from backend.imports.service import _import_data_origin, import_curated_market_dataset
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink, SourceObservation, SourceRef
from backend.shared.provenance import DataOrigin, ObservationStatus

REPO_ROOT = Path(__file__).resolve().parent.parent
NYC_IMPORT_DIR = REPO_ROOT / "data" / "imports" / "nyc"
AS_OF = date(2026, 7, 9)


def test_valid_nyc_dataset_imports_successfully(session: Session) -> None:
    result = import_nyc_dataset(session, as_of=AS_OF)

    assert result.ok
    assert result.status == "imported"
    assert result.counts["regions"].created == 1
    assert result.counts["companies"].created == 3
    assert result.counts["presence"].created == 3
    assert result.counts["hiring"].created == 3
    assert result.counts["entry_level"].created == 3
    assert result.counts["source_refs"].created == 5
    assert result.counts["source_observations"].created == 5
    assert result.counts["fact_source_links"].created == 13


def test_validation_failure_prevents_all_canonical_writes(
    tmp_path: Path,
    session: Session,
) -> None:
    dataset = _copy_dataset(tmp_path)
    (dataset / "companies.csv").unlink()

    result = import_curated_market_dataset(session, dataset, as_of=AS_OF)

    assert not result.ok
    assert result.status == "validation_failed"
    assert _table_counts(session) == _empty_table_counts()


def test_missing_source_refs_do_not_write_canonical_facts(
    tmp_path: Path,
    session: Session,
) -> None:
    dataset = _copy_dataset(tmp_path)
    _update_csv_row(dataset / "hiring.csv", 0, {"source_ref": ""})

    result = import_curated_market_dataset(session, dataset, as_of=AS_OF)

    assert not result.ok
    assert any(issue.code == "missing_source_ref" for issue in result.validation_errors)
    assert _table_counts(session) == _empty_table_counts()


def test_region_import_creates_greater_nyc(session: Session) -> None:
    import_nyc_dataset(session, as_of=AS_OF)

    region = session.get(Region, "greater_nyc")
    assert region is not None
    assert region.display_name == "Greater NYC"
    assert region.region_type == "greater_region"
    assert region.labor_market_group == "greater_nyc"


def test_company_import_creates_companies(session: Session) -> None:
    import_nyc_dataset(session, as_of=AS_OF)

    companies = session.query(Company).order_by(Company.company_id).all()
    assert len(companies) == 3
    hudson = session.get(Company, "cmp_hudson_applied_ai")
    assert hudson.company_name == "Hudson Applied AI"
    assert hudson.sector_primary == "ai"
    assert hudson.eligibility_status == "eligible"


def test_duplicate_import_run_is_idempotent(session: Session) -> None:
    first = import_nyc_dataset(session, as_of=AS_OF)
    versions = {
        "region": session.get(Region, "greater_nyc").version,
        "company": session.get(Company, "cmp_hudson_applied_ai").version,
        "presence": session.query(CompanyRegionPresence).first().version,
        "hiring": session.query(CompanyRegionHiring).first().version,
        "entry": session.query(CompanyRegionEntryLevel).first().version,
    }
    second = import_nyc_dataset(session, as_of=AS_OF)

    assert first.ok and second.ok
    assert second.counts["regions"].unchanged == 1
    assert second.counts["companies"].unchanged == 3
    assert second.counts["presence"].unchanged == 3
    assert second.counts["hiring"].unchanged == 3
    assert second.counts["entry_level"].unchanged == 3
    assert _table_counts(session) == {
        "regions": 1,
        "companies": 3,
        "presence": 3,
        "hiring": 3,
        "entry_level": 3,
        "source_refs": 5,
        "source_observations": 5,
        "fact_source_links": 13,
    }
    assert session.get(Region, "greater_nyc").version == versions["region"]
    assert session.get(Company, "cmp_hudson_applied_ai").version == versions["company"]


def test_company_region_presence_imports_without_duplicates(session: Session) -> None:
    import_nyc_dataset(session, as_of=AS_OF)
    import_nyc_dataset(session, as_of=AS_OF)

    rows = session.query(CompanyRegionPresence).all()
    assert len(rows) == 3
    assert {row.presence_status for row in rows} == {"present"}
    assert all(row.source_refs for row in rows)


def test_hiring_facts_import_without_duplicates(session: Session) -> None:
    import_nyc_dataset(session, as_of=AS_OF)
    import_nyc_dataset(session, as_of=AS_OF)

    rows = session.query(CompanyRegionHiring).all()
    assert len(rows) == 3
    assert {row.company_id for row in rows} == {
        "cmp_hudson_applied_ai",
        "cmp_brooklyn_cloudworks",
        "cmp_liberty_cyber_systems",
    }


def test_entry_level_facts_import_without_duplicates(session: Session) -> None:
    import_nyc_dataset(session, as_of=AS_OF)
    import_nyc_dataset(session, as_of=AS_OF)

    rows = session.query(CompanyRegionEntryLevel).all()
    assert len(rows) == 3
    assert all(row.entry_level_access_score is None for row in rows)


def test_provenance_metadata_is_preserved_and_attached(session: Session) -> None:
    import_nyc_dataset(session, as_of=AS_OF)

    source = session.get(SourceRef, "src_nyc_hiring_snapshot_2026_06")
    observation = session.get(SourceObservation, "obs_src_nyc_hiring_snapshot_2026_06")
    hiring = session.get(
        CompanyRegionHiring,
        "hiring_cmp_hudson_applied_ai_greater_nyc",
    )
    link_id = hiring.source_refs[0]["fact_source_link_id"]
    link = session.get(FactSourceLink, link_id)

    assert source.source_type == "manual_research"
    assert source.confidence == "medium"
    assert source.freshness_status == "fresh"
    assert source.data_origin == DataOrigin.SYNTHETIC_OR_CURATED_DEMO.value
    assert "not factual public market coverage" in (source.notes or "")
    assert observation.source_id == source.source_id
    assert observation.freshness_status == "fresh"
    assert observation.data_origin == DataOrigin.SYNTHETIC_OR_CURATED_DEMO.value
    assert link.source_id == source.source_id
    assert link.collected_at == source.collected_at
    assert link.observed_at == source.observed_at
    assert link.license_or_terms_category == "permissive"
    assert link.freshness_status == "fresh"
    assert link.data_origin == DataOrigin.SYNTHETIC_OR_CURATED_DEMO.value
    assert hiring.source_refs[0]["source_ref"] == source.source_id


def test_non_fixture_curated_sources_keep_manual_reviewed_semantics() -> None:
    assert _import_data_origin(
        {"source_url_or_reference": "https://example.org/documented-source"}
    ) is DataOrigin.MANUAL_REVIEWED


def test_unknown_counts_remain_unknown_after_import(session: Session) -> None:
    import_nyc_dataset(session, as_of=AS_OF)

    hiring = session.get(
        CompanyRegionHiring,
        "hiring_cmp_liberty_cyber_systems_greater_nyc",
    )
    entry = session.get(
        CompanyRegionEntryLevel,
        "entry_cmp_liberty_cyber_systems_greater_nyc",
    )

    assert hiring.active_posting_count_now is None
    assert hiring.active_posting_count_now_status == ObservationStatus.UNKNOWN.value
    assert entry.internship_count is None
    assert entry.internship_count_status == ObservationStatus.UNKNOWN.value


def test_observed_zero_counts_remain_zero_after_import(session: Session) -> None:
    import_nyc_dataset(session, as_of=AS_OF)

    hiring = session.get(
        CompanyRegionHiring,
        "hiring_cmp_brooklyn_cloudworks_greater_nyc",
    )
    entry = session.get(
        CompanyRegionEntryLevel,
        "entry_cmp_brooklyn_cloudworks_greater_nyc",
    )

    assert hiring.active_posting_count_now == 0
    assert hiring.active_posting_count_now_status == ObservationStatus.ZERO_OBSERVED.value
    assert entry.internship_count == 0
    assert entry.internship_count_status == ObservationStatus.ZERO_OBSERVED.value


def test_positive_observed_counts_remain_positive_after_import(
    session: Session,
) -> None:
    import_nyc_dataset(session, as_of=AS_OF)

    hiring = session.get(
        CompanyRegionHiring,
        "hiring_cmp_hudson_applied_ai_greater_nyc",
    )
    entry = session.get(
        CompanyRegionEntryLevel,
        "entry_cmp_hudson_applied_ai_greater_nyc",
    )

    assert hiring.active_posting_count_now == 9
    assert hiring.active_posting_count_now_status == (
        ObservationStatus.POSITIVE_OBSERVED.value
    )
    assert entry.internship_count == 7
    assert entry.internship_count_status == ObservationStatus.POSITIVE_OBSERVED.value


def test_unknown_counts_are_not_coerced_into_zero(session: Session) -> None:
    import_nyc_dataset(session, as_of=AS_OF)

    values = [
        row.active_posting_count_now
        for row in session.query(CompanyRegionHiring).all()
        if row.active_posting_count_now_status == ObservationStatus.UNKNOWN.value
    ]
    values.extend(
        row.internship_count
        for row in session.query(CompanyRegionEntryLevel).all()
        if row.internship_count_status == ObservationStatus.UNKNOWN.value
    )
    assert values
    assert all(value is None for value in values)


def test_import_result_is_structured_and_deterministic(session: Session) -> None:
    first = import_nyc_dataset(session, as_of=AS_OF)
    second = import_nyc_dataset(session, as_of=AS_OF)

    assert set(first.counts_as_dict()) == set(second.counts_as_dict())
    assert first.validation.summary.as_dict() == second.validation.summary.as_dict()
    assert first.diagnostics == ()
    assert second.diagnostics == ()
    assert first.counts_as_dict()["regions"] == {
        "created": 1,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "failed": 0,
    }
    assert second.counts_as_dict()["regions"] == {
        "created": 0,
        "updated": 0,
        "unchanged": 1,
        "skipped": 0,
        "failed": 0,
    }


def test_import_requires_no_scraping_network_or_live_api_calls(
    monkeypatch,
    session: Session,
) -> None:
    def _blocked_network(*_args, **_kwargs):
        raise AssertionError("network access is not allowed for curated imports")

    monkeypatch.setattr(socket, "create_connection", _blocked_network)

    result = import_nyc_dataset(session, as_of=AS_OF)

    assert result.ok
    assert session.query(Company).count() == 3


def _copy_dataset(tmp_path: Path) -> Path:
    target = tmp_path / "nyc"
    shutil.copytree(NYC_IMPORT_DIR, target)
    return target


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


def _table_counts(session: Session) -> dict[str, int]:
    return {
        "regions": session.query(Region).count(),
        "companies": session.query(Company).count(),
        "presence": session.query(CompanyRegionPresence).count(),
        "hiring": session.query(CompanyRegionHiring).count(),
        "entry_level": session.query(CompanyRegionEntryLevel).count(),
        "source_refs": session.query(SourceRef).count(),
        "source_observations": session.query(SourceObservation).count(),
        "fact_source_links": session.query(FactSourceLink).count(),
    }


def _empty_table_counts() -> dict[str, int]:
    return {
        "regions": 0,
        "companies": 0,
        "presence": 0,
        "hiring": 0,
        "entry_level": 0,
        "source_refs": 0,
        "source_observations": 0,
        "fact_source_links": 0,
    }
