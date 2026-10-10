"""Read-only smoke check for a deployed beta backend."""

from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

READS = (
    ("GET", "/me", None),
    ("GET", "/me/career-identity", None),
    ("GET", "/me/explore/context", None),
    ("POST", "/me/explore/markets", {"session_overrides": {}}),
    ("GET", "/me/search-workspace", None),
)


def main() -> int:
    base_url = os.environ.get("BETA_SMOKE_BASE_URL", "").rstrip("/")
    token = os.environ.get("BETA_SMOKE_ACCESS_TOKEN", "")
    if not base_url.startswith("https://"):
        raise SystemExit("BETA_SMOKE_BASE_URL must be an HTTPS origin")
    results = [
        _call(base_url, method, path, body, token="")
        for method, path, body in (("GET", "/health", None), ("GET", "/ready", None))
    ]
    if token:
        results.extend(
            _call(base_url, method, path, body, token=token) for method, path, body in READS
        )
    else:
        results.append(
            {
                "path": "authenticated_reads",
                "status": "skipped",
                "reason": "BETA_SMOKE_ACCESS_TOKEN not set",
            }
        )
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0 if all(item.get("ok", item.get("status") == "skipped") for item in results) else 1


def _call(base_url: str, method: str, path: str, body: dict | None, *, token: str) -> dict:
    payload = json.dumps(body).encode() if body is not None else None
    headers = {
        "Accept": "application/json",
        "X-Request-ID": f"release-smoke-{path.strip('/').replace('/', '-') or 'root'}",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{base_url}{path}", data=payload, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310
            response.read(2048)
            return {
                "path": path,
                "status": response.status,
                "ok": 200 <= response.status < 300,
                "request_id": response.headers.get("X-Request-ID"),
                "release_id": response.headers.get("X-Release-ID"),
            }
    except HTTPError as exc:
        return {
            "path": path,
            "status": exc.code,
            "ok": False,
            "request_id": exc.headers.get("X-Request-ID"),
            "release_id": exc.headers.get("X-Release-ID"),
        }
    except URLError as exc:
        return {
            "path": path,
            "status": "network_error",
            "ok": False,
            "error_class": type(exc.reason).__name__,
        }


if __name__ == "__main__":
    sys.exit(main())
