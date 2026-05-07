"""Verify the canonical schema covers every entity called out in DATA_MODEL.md."""

from sqlalchemy import inspect

from backend.shared.db import Base, create_all, make_engine

REQUIRED_TABLES = {
    "regions",
    "companies",
    "company_region_presence",
    "company_region_hiring",
    "company_region_entry_level",
    "region_market_scores",
    "jobs",
    "output_metadata",
}

# Every canonical truth/output object must carry these metadata columns
# (DATA_MODEL.md §2 + §10 + Slice 2 success criteria).
CANONICAL_METADATA_COLUMNS = {"state", "version", "created_at", "updated_at"}

CANONICAL_METADATA_TABLES = REQUIRED_TABLES - {"jobs"}  # jobs has its own envelope columns


def test_all_required_tables_registered() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)
    found = set(inspector.get_table_names())
    assert REQUIRED_TABLES.issubset(found), REQUIRED_TABLES - found


def test_canonical_metadata_columns_present() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)
    missing: dict[str, set[str]] = {}
    for table_name in CANONICAL_METADATA_TABLES:
        cols = {c["name"] for c in inspector.get_columns(table_name)}
        gaps = CANONICAL_METADATA_COLUMNS - cols
        if gaps:
            missing[table_name] = gaps
    assert not missing, missing


def test_jobs_table_has_envelope_columns() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("jobs")}
    expected = {
        "job_id",
        "job_type",
        "queue_name",
        "status",
        "priority",
        "scope_hash",
        "dedupe_key",
        "retry_count",
        "max_retries",
        "input_hash",
        "output_hash",
        "dependency_refs",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
        "error_code",
        "error_message",
        "warnings",
    }
    missing = expected - cols
    assert not missing, missing


def test_pair_uniqueness_indexes_exist() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    inspector = inspect(engine)

    def has_unique_pair(table: str, columns: tuple[str, ...]) -> bool:
        for uq in inspector.get_unique_constraints(table):
            if tuple(uq["column_names"]) == columns:
                return True
        return False

    assert has_unique_pair("company_region_presence", ("company_id", "region_id"))
    assert has_unique_pair("company_region_hiring", ("company_id", "region_id"))
    assert has_unique_pair("company_region_entry_level", ("company_id", "region_id"))
    assert has_unique_pair("region_market_scores", ("region_id",))
    assert has_unique_pair("output_metadata", ("output_type", "subject_id"))


def test_metadata_registry_has_no_extra_tables() -> None:
    """Slice 2 should not pull in surprise tables from later slices."""
    declared = set(Base.metadata.tables.keys())
    assert declared == REQUIRED_TABLES, declared.symmetric_difference(REQUIRED_TABLES)
