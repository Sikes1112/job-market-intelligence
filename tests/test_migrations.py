import pytest
from sqlalchemy import UniqueConstraint, inspect, text

from backend.shared.db import Base, create_all, import_all_models, make_engine
from backend.shared.migrations import upgrade_database


def test_alembic_upgrade_head_creates_current_schema(tmp_path) -> None:
    db_path = tmp_path / "migration-validation.db"
    database_url = f"sqlite:///{db_path}"

    upgrade_database(database_url)

    engine = make_engine(database_url)
    try:
        inspector = inspect(engine)
        import_all_models()

        created_tables = set(inspector.get_table_names()) - {"alembic_version"}
        assert created_tables == set(Base.metadata.tables)

        for table_name, table in Base.metadata.tables.items():
            created_columns = {
                column["name"]: column for column in inspector.get_columns(table_name)
            }
            model_columns = {column.name for column in table.columns}
            assert set(created_columns) == model_columns
            for column in table.columns:
                assert created_columns[column.name]["nullable"] == column.nullable

            created_primary_key = tuple(
                inspector.get_pk_constraint(table_name)["constrained_columns"]
            )
            model_primary_key = tuple(column.name for column in table.primary_key.columns)
            assert created_primary_key == model_primary_key

            created_foreign_keys = {
                (
                    tuple(foreign_key["constrained_columns"]),
                    foreign_key["referred_table"],
                    tuple(foreign_key["referred_columns"]),
                )
                for foreign_key in inspector.get_foreign_keys(table_name)
            }
            model_foreign_keys = {
                (
                    tuple(element.parent.name for element in constraint.elements),
                    constraint.referred_table.name,
                    tuple(element.column.name for element in constraint.elements),
                )
                for constraint in table.foreign_key_constraints
            }
            assert created_foreign_keys == model_foreign_keys

            created_index_names = {index["name"] for index in inspector.get_indexes(table_name)}
            model_index_names = {index.name for index in table.indexes}
            assert created_index_names == model_index_names

            created_unique_constraints = {
                tuple(constraint["column_names"])
                for constraint in inspector.get_unique_constraints(table_name)
            }
            model_unique_constraints = {
                tuple(column.name for column in constraint.columns)
                for constraint in table.constraints
                if isinstance(constraint, UniqueConstraint)
            }
            assert created_unique_constraints == model_unique_constraints
    finally:
        engine.dispose()


def test_local_demo_migration_wrapper_stamps_existing_create_all_schema(tmp_path) -> None:
    db_path = tmp_path / "legacy-demo.db"
    database_url = f"sqlite:///{db_path}"

    engine = make_engine(database_url)
    try:
        create_all(engine)
    finally:
        engine.dispose()

    upgrade_database(database_url, allow_existing_schema_stamp=True)

    engine = make_engine(database_url)
    try:
        with engine.connect() as connection:
            version = connection.execute(text("select version_num from alembic_version"))
            assert version.scalar_one() == "0024_platform_api_access_control"
    finally:
        engine.dispose()


def test_alembic_upgrade_head_is_idempotent(tmp_path) -> None:
    db_path = tmp_path / "idempotent.db"
    database_url = f"sqlite:///{db_path}"

    upgrade_database(database_url)
    upgrade_database(database_url)

    engine = make_engine(database_url)
    try:
        with engine.connect() as connection:
            version = connection.execute(text("select version_num from alembic_version"))
            assert version.scalar_one() == "0024_platform_api_access_control"
    finally:
        engine.dispose()


def test_existing_schema_stamp_rejects_schema_with_missing_index(tmp_path) -> None:
    db_path = tmp_path / "legacy-broken.db"
    database_url = f"sqlite:///{db_path}"

    engine = make_engine(database_url)
    try:
        create_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP INDEX ix_companies_sector_primary"))
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="refusing to stamp"):
        upgrade_database(database_url, allow_existing_schema_stamp=True)

    engine = make_engine(database_url)
    try:
        inspector = inspect(engine)
        if "alembic_version" in inspector.get_table_names():
            with engine.connect() as connection:
                versions = connection.execute(
                    text("select version_num from alembic_version")
                ).scalars()
            assert "0024_platform_api_access_control" not in set(versions)
    finally:
        engine.dispose()
