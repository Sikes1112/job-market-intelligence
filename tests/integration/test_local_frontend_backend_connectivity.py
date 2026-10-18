"""Local Vite-to-FastAPI connectivity smoke coverage."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import pytest

from backend.shared.db import make_engine, make_session_factory, session_scope
from backend.shared.migrations import upgrade_database
from seeds.mvp_seed import run_seed

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = REPO_ROOT / "frontend"
VITE = FRONTEND_ROOT / "node_modules" / ".bin" / "vite"


def test_vite_proxy_reaches_fastapi_without_intercepting_frontend_routes(
    tmp_path: Path,
) -> None:
    if not VITE.is_file():
        pytest.skip("frontend dependencies are not installed")

    database_url = f"sqlite:///{tmp_path / 'connectivity.db'}"
    upgrade_database(database_url, allow_existing_schema_stamp=True)
    engine = make_engine(database_url)
    with session_scope(make_session_factory(engine)) as session:
        run_seed(session)
    engine.dispose()

    backend_port = _free_port()
    frontend_port = _free_port()
    backend_env = {
        **os.environ,
        "APP_ENV": "local",
        "DATABASE_URL": database_url,
        "RATE_LIMIT_ENABLED": "false",
        "SECURITY_HEADERS_ENABLED": "false",
    }
    frontend_env = {
        **os.environ,
        "VITE_DEV_API_TARGET": f"http://127.0.0.1:{backend_port}",
        "VITE_LOCAL_AUTH": "true",
    }
    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.api.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(backend_port),
        ],
        cwd=REPO_ROOT,
        env=backend_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    frontend = subprocess.Popen(
        [str(VITE), "--host", "127.0.0.1", "--port", str(frontend_port), "--strictPort"],
        cwd=FRONTEND_ROOT,
        env=frontend_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_url(f"http://127.0.0.1:{backend_port}/health")
        _wait_for_url(f"http://127.0.0.1:{frontend_port}/markets")

        health_body, health_headers = _read(
            f"http://127.0.0.1:{frontend_port}/health"
        )
        assert json.loads(health_body)["service"] == "jmi-backend"
        assert health_headers.get("x-request-id")

        opportunities_body, opportunities_headers = _read(
            f"http://127.0.0.1:{frontend_port}/opportunities?active=true"
        )
        opportunities = json.loads(opportunities_body)["data"]["opportunities"]
        assert {item["id"] for item in opportunities} == {
                "opp_demo_boston_software_2",
            "opp_demo_sf_data",
        }
        assert opportunities_headers.get("x-request-id")

        comparison_body, comparison_headers = _read(
            f"http://127.0.0.1:{frontend_port}/compare"
            "?region_a=greater_boston&region_b=sf_bay_area"
        )
        comparison = json.loads(comparison_body)
        assert comparison["status"] in {"success", "partial"}
        assert comparison_headers.get("x-request-id")

        current_body, current_headers = _read(
            (
                f"http://127.0.0.1:{frontend_port}/current-opportunities"
                "?market=greater_boston&role_family=software_engineering"
            ),
            headers={
                "X-Verified-OIDC-Claims": json.dumps(
                    {
                        "iss": "https://local.job-market-intelligence.test/",
                        "sub": "local|explorer",
                        "email": "local-explorer@example.test",
                    }
                )
            },
        )
        current = json.loads(current_body)["data"]["opportunities"]
        assert len(current) == 1
        assert current[0]["market_id"] == "greater_boston"
        assert current[0]["provenance"]["sources"][0]["synthetic"] is True
        assert current_headers.get("x-request-id")

        for frontend_path in (
            "/markets",
            "/markets/region/greater_boston",
            "/compare/nyc-vs-seattle-tech-careers",
            "/data-standards",
        ):
            body, headers = _read(f"http://127.0.0.1:{frontend_port}{frontend_path}")
            assert "text/html" in headers.get("content-type", "")
            assert '<div id="root"></div>' in body
    finally:
        _stop(frontend)
        _stop(backend)


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_url(url: str, *, timeout_seconds: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1):  # noqa: S310 - loopback test server
                return
        except (OSError, URLError):
            time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {url}")


def _read(url: str, *, headers: dict[str, str] | None = None) -> tuple[str, object]:
    request = Request(url, headers=headers or {})  # noqa: S310 - loopback test server
    with urlopen(request, timeout=5) as response:  # noqa: S310 - loopback test server
        return response.read().decode("utf-8"), response.headers


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
