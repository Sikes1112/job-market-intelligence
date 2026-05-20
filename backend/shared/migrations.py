from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import UniqueConstraint, inspect

from alembic import command
from backend.config.settings import is_sqlite_database_url
from backend.shared.db import Base, import_all_models, make_engine


def make_alembic_config(database_url: str) -> Config:
    """Build an Alembic config pointed at the repo migration environment."""
    repo_root = Path(__file__).resolve().parents[2]
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_database(
    database_url: str,
    revision: str = "head",
    *,
    allow_existing_schema_stamp: bool = False,
) -> None:
    """Apply migrations to the configured database."""
    config = make_alembic_config(database_url)
    if allow_existing_schema_stamp and revision == "head":
        if _has_unversioned_model_tables(database_url):
            if not is_sqlite_database_url(database_url):
                raise RuntimeError(
                    "Existing schema stamping is only allowed for SQLite "
                    "local/demo databases."
                )
            if _has_current_unversioned_schema(database_url):
                command.stamp(config, revision)
                return
            raise RuntimeError(
                "Existing unversioned database schema does not match current "
                "metadata; refusing to stamp or migrate in place."
            )
    command.upgrade(config, revision)


def _has_current_unversioned_schema(database_url: str) -> bool:
    engine = make_engine(database_url)
    try:
        inspector = inspect(engine)
        dialect = engine.dialect
        table_names = set(inspector.get_table_names())
        if "alembic_version" in table_names:
            return False

        import_all_models()
        model_tables = set(Base.metadata.tables)
        if not model_tables.issubset(table_names):
            return False

        for table_name, table in Base.metadata.tables.items():
            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            model_columns = {column.name for column in table.columns}
            if existing_columns != model_columns:
                return False
            created_columns = {
                column["name"]: column for column in inspector.get_columns(table_name)
            }
            for column in table.columns:
                created_column = created_columns[column.name]
                if created_column["nullable"] != column.nullable:
                    return False
                created_type = created_column["type"].compile(dialect=dialect).lower()
                model_type = column.type.compile(dialect=dialect).lower()
                if created_type != model_type:
                    return False

            created_primary_key = tuple(
                inspector.get_pk_constraint(table_name)["constrained_columns"]
            )
            model_primary_key = tuple(column.name for column in table.primary_key.columns)
            if created_primary_key != model_primary_key:
                return False

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
            if created_foreign_keys != model_foreign_keys:
                return False

            created_index_names = {
                index["name"] for index in inspector.get_indexes(table_name)
            }
            model_index_names = {index.name for index in table.indexes}
            if created_index_names != model_index_names:
                return False

            created_unique_constraints = {
                tuple(constraint["column_names"])
                for constraint in inspector.get_unique_constraints(table_name)
            }
            model_unique_constraints = {
                tuple(column.name for column in constraint.columns)
                for constraint in table.constraints
                if isinstance(constraint, UniqueConstraint)
            }
            if created_unique_constraints != model_unique_constraints:
                return False
    finally:
        engine.dispose()

    return True


def _has_unversioned_model_tables(database_url: str) -> bool:
    engine = make_engine(database_url)
    try:
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        if "alembic_version" in table_names:
            return False

        import_all_models()
        return bool(set(Base.metadata.tables) & table_names)
    finally:
        engine.dispose()
