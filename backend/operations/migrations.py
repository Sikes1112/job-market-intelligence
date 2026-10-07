from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text
from sqlalchemy.engine import Connection

from backend.shared.migrations import make_alembic_config


@dataclass(frozen=True, slots=True)
class MigrationStatus:
    status: str
    current_revisions: tuple[str, ...]
    expected_heads: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def expected_migration_heads(database_url: str) -> tuple[str, ...]:
    script = ScriptDirectory.from_config(make_alembic_config(database_url))
    return tuple(sorted(script.get_heads()))


def database_migration_status(engine: Engine, database_url: str) -> MigrationStatus:
    expected = expected_migration_heads(database_url)
    try:
        with engine.connect() as connection:
            return database_migration_status_from_connection(
                connection,
                database_url,
                expected_heads=expected,
            )
    except Exception:
        return MigrationStatus(
            status="unavailable",
            current_revisions=(),
            expected_heads=expected,
        )


def database_migration_status_from_connection(
    connection: Connection,
    database_url: str,
    *,
    expected_heads: tuple[str, ...] | None = None,
) -> MigrationStatus:
    expected = expected_heads or expected_migration_heads(database_url)
    try:
        inspector = inspect(connection)
        if "alembic_version" not in set(inspector.get_table_names()):
            return MigrationStatus(
                status="unversioned",
                current_revisions=(),
                expected_heads=expected,
            )
        rows = connection.execute(text("SELECT version_num FROM alembic_version")).all()
    except Exception:
        return MigrationStatus(
            status="unavailable",
            current_revisions=(),
            expected_heads=expected,
        )

    current = tuple(sorted(str(row[0]) for row in rows if row[0]))
    if current == expected:
        status = "current"
    elif not current:
        status = "unversioned"
    else:
        status = "mismatch"
    return MigrationStatus(status=status, current_revisions=current, expected_heads=expected)
