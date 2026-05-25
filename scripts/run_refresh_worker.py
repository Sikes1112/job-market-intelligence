"""Run the refresh worker process.

Production posture is RQ + Redis. The local adapter is available only for
non-production smoke checks because it has process-local memory.
"""

from __future__ import annotations

import argparse
import os
import sys

from backend.refresh.adapters import (
    RefreshQueueConfigurationError,
    create_refresh_queue_adapter,
    run_rq_worker,
)
from backend.refresh.runner import RefreshWorkerRunner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run refresh worker process.")
    parser.add_argument(
        "--adapter",
        choices=("rq", "local"),
        default=os.getenv("REFRESH_QUEUE_ADAPTER", "rq"),
    )
    parser.add_argument("--redis-url", default=os.getenv("REDIS_URL"))
    parser.add_argument("--queue", default=os.getenv("REFRESH_QUEUE_NAME", "refresh"))
    parser.add_argument("--max-jobs", type=int, default=None)
    args = parser.parse_args(argv)

    try:
        if args.adapter == "rq":
            if not args.redis_url:
                raise RefreshQueueConfigurationError("REDIS_URL is required for the RQ worker")
            run_rq_worker(redis_url=args.redis_url, queue_names=[args.queue])
            return 0

        queue = create_refresh_queue_adapter(adapter="local")
        records = RefreshWorkerRunner(queue).run_until_empty(max_jobs=args.max_jobs)
        print(f"local refresh worker processed {len(records)} job(s)")
        return 0
    except RefreshQueueConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
