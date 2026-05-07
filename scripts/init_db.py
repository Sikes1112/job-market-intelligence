"""Initialize the canonical schema in the configured database.

Usage::

    python scripts/init_db.py

Reads ``DATABASE_URL`` from the environment (see ``.env.example``). Idempotent:
``Base.metadata.create_all`` skips tables that already exist.
"""

from __future__ import annotations

from backend.config.settings import get_settings
from backend.shared.db import create_all, make_engine


def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    create_all(engine)
    print(f"Schema created at {settings.database_url}")


if __name__ == "__main__":
    main()
