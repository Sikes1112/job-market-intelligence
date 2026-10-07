from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class _HttpBucket:
    count: int = 0
    error_count: int = 0
    duration_ms_total: float = 0.0
    duration_ms_max: float = 0.0


class InMemoryMetricsRegistry:
    """Small per-process metrics registry with bounded label cardinality."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._http: dict[tuple[str, str, str], _HttpBucket] = defaultdict(_HttpBucket)

    def record_http_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        status_class = f"{max(status_code, 0) // 100}xx"
        key = (method.upper(), route, status_class)
        with self._lock:
            bucket = self._http[key]
            bucket.count += 1
            if status_code >= 500:
                bucket.error_count += 1
            bucket.duration_ms_total += max(duration_ms, 0.0)
            bucket.duration_ms_max = max(bucket.duration_ms_max, duration_ms)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            http = []
            for (method, route, status_class), bucket in sorted(self._http.items()):
                avg = bucket.duration_ms_total / bucket.count if bucket.count else 0.0
                http.append(
                    {
                        "method": method,
                        "route": route,
                        "status_class": status_class,
                        "count": bucket.count,
                        "error_count": bucket.error_count,
                        "duration_ms_avg": round(avg, 3),
                        "duration_ms_max": round(bucket.duration_ms_max, 3),
                    }
                )
        return {"http": http}


def metrics_registry_from_app_state(state: object) -> InMemoryMetricsRegistry | None:
    registry = getattr(state, "metrics_registry", None)
    if isinstance(registry, InMemoryMetricsRegistry):
        return registry
    return None

