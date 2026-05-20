"""Apply database migrations to the configured local/demo database.

Usage::

    python -m scripts.init_db

Reads ``DATABASE_URL`` from the environment. This script is a local/demo
convenience wrapper around ``alembic upgrade head``; production deployment
should run Alembic migrations explicitly as part of its release process. It is
blocked for staging/prod app environments.
"""

from __future__ import annotations

from backend.config.settings import get_settings, redact_database_url
from backend.shared.demo_safety import ensure_demo_database_target_allowed
from backend.shared.migrations import upgrade_database


def main() -> None:
    settings = get_settings()
    ensure_demo_database_target_allowed(settings, settings.database_url)
    upgrade_database(settings.database_url, allow_existing_schema_stamp=True)
    print(f"Schema migrated to head at {redact_database_url(settings.database_url)}")


if __name__ == "__main__":
    main()
