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
from datetime import UTC, date, datetime

from sqlalchemy import func, select

from backend.config.settings import get_settings, redact_database_url
from backend.current_opportunities.models import CurrentOpportunity
from backend.opportunities.models import Opportunity
from backend.shared.db import (
    make_engine,
    make_session_factory,
    session_scope,
)
from backend.shared.demo_safety import ensure_demo_database_target_allowed
from backend.shared.migrations import upgrade_database
from seeds.mvp_seed import run_seed
from seeds.portfolio_seed import run_portfolio_seed


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
    parser.add_argument(
        "--portfolio",
        action="store_true",
        help=(
            "Extend the narrow MVP seed with all eight bundled markets, 24 "
            "synthetic opportunity scenarios, and the local reviewer state."
        ),
    )
    parser.add_argument(
        "--demo-as-of",
        type=date.fromisoformat,
        default=None,
        help=(
            "Fixture review date used by --portfolio (YYYY-MM-DD). Defaults to "
            "the invocation date; pass an explicit value for a reproducible snapshot."
        ),
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    database_url = args.database_url or settings.database_url

    ensure_demo_database_target_allowed(settings, database_url)
    upgrade_database(database_url, allow_existing_schema_stamp=True)
    engine = make_engine(database_url)
    factory = make_session_factory(engine)

    demo_now = datetime.now(UTC)
    stored_opportunity_counts: tuple[int, int] | None = None
    with session_scope(factory) as session:
        result = run_seed(session, demo_now=demo_now)
        portfolio_result = (
            run_portfolio_seed(
                session,
                result,
                as_of=args.demo_as_of or demo_now.date(),
                demo_now=demo_now,
            )
            if args.portfolio
            else None
        )
        if portfolio_result is not None:
            stored_opportunity_counts = (
                session.scalar(select(func.count()).select_from(Opportunity)) or 0,
                session.scalar(select(func.count()).select_from(CurrentOpportunity)) or 0,
            )

    if not args.quiet:
        for line in result.summary_lines():
            print(line)
        if portfolio_result is not None:
            print(
                "  portfolio_demo         "
                f"markets={len(portfolio_result.imported.markets_succeeded)} "
                f"reviewer_user={portfolio_result.reviewer.user_id} "
                f"decision={portfolio_result.reviewer.decision_id}"
            )
            if stored_opportunity_counts is not None:
                marketplace_count, current_count = stored_opportunity_counts
                print(
                    "  portfolio_stored_rows  "
                    f"marketplace_opportunities={marketplace_count} "
                    f"current_opportunities={current_count}"
                )
        print(f"Schema + seed dataset present at {redact_database_url(database_url)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
