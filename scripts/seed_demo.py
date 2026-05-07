"""Slice 18 — MVP demo seed entrypoint.

Usage::

    python scripts/seed_demo.py [--database-url URL] [--quiet]

Initializes the schema (idempotent ``create_all``), runs the MVP seed
pipeline once, and prints a compact ``created/updated/unchanged`` summary
per layer. Re-running on an already-seeded database returns ``unchanged``
for every layer that hasn't changed; no duplicate logical rows are created.

The script never performs network IO, scraping, or AI/NLP calls.
"""

from __future__ import annotations

import argparse
import sys

from backend.config.settings import get_settings
from backend.shared.db import (
    create_all,
    make_engine,
    make_session_factory,
    session_scope,
)
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

    engine = make_engine(database_url)
    create_all(engine)
    factory = make_session_factory(engine)

    with session_scope(factory) as session:
        result = run_seed(session)

    if not args.quiet:
        for line in result.summary_lines():
            print(line)
        print(f"Schema + seed dataset present at {database_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
