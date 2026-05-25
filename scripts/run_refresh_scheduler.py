"""Run the refresh scheduler process once.

The scheduler only enqueues planned cadence jobs. It does not execute refresh
handlers or perform data refresh work.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime

from backend.refresh.adapters import RefreshQueueConfigurationError, create_refresh_queue_adapter
from backend.refresh.scheduler import RefreshSchedulerRunner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run refresh scheduler once.")
    parser.add_argument(
        "--adapter",
        choices=("rq", "local"),
        default=os.getenv("REFRESH_QUEUE_ADAPTER", "rq"),
    )
    parser.add_argument("--redis-url", default=os.getenv("REDIS_URL"))
    parser.add_argument("--queue", default=os.getenv("REFRESH_QUEUE_NAME", "refresh"))
    args = parser.parse_args(argv)

    try:
        queue = create_refresh_queue_adapter(
            adapter=args.adapter,
            redis_url=args.redis_url,
            queue_name=args.queue,
        )
    except RefreshQueueConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    result = RefreshSchedulerRunner(queue).enqueue_due(now=datetime.now(UTC))
    enqueued = sum(1 for item in result.enqueue_results if item.outcome == "enqueued")
    suppressed = sum(1 for item in result.enqueue_results if item.outcome == "already_active")
    print(
        "refresh scheduler planned "
        f"{len(result.plan.requests)} job(s), enqueued {enqueued}, "
        f"already active {suppressed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
