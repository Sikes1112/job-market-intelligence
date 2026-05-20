"""Slice 18 — MVP demo seed entrypoint.

Usage::

    python -m scripts.seed_demo [--database-url URL] [--quiet]

Applies migrations, runs the MVP seed
pipeline once, and prints a compact ``created/updated/unchanged`` summary
per layer. Re-running on an already-seeded database returns ``unchanged``
for every layer that hasn't changed; no duplicate logical rows are created.

The script never performs network IO, scraping, or AI/NLP calls.
It refuses staging/prod app environments and requires explicit confirmation for
non-SQLite demo database targets.
"""

from __future__ import annotations

import argparse
import sys

from backend.config.settings import get_settings, redact_database_url
from backend.shared.db import (
    make_engine,
    make_session_factory,
    session_scope,
)
from backend.shared.demo_safety import ensure_demo_database_target_allowed
from backend.shared.migrations import upgrade_database
from seeds.mvp_seed import run_seed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the MVP demo dataset.")
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override the configured database_url.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the post-run summary.",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    database_url = args.database_url or settings.database_url

    ensure_demo_database_target_allowed(settings, database_url)
    upgrade_database(database_url, allow_existing_schema_stamp=True)
    engine = make_engine(database_url)
    factory = make_session_factory(engine)

    with session_scope(factory) as session:
        result = run_seed(session)

    if not args.quiet:
        for line in result.summary_lines():
            print(line)
        print(f"Schema + seed dataset present at {redact_database_url(database_url)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
