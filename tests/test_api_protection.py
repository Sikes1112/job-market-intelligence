from __future__ import annotations

from fastapi import Request
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.protection import APIProtectionMiddleware, RateLimitBucket
from backend.config.settings import Settings


def test_security_headers_are_added_when_enabled() -> None:
    client = TestClient(
        create_app(settings=_settings(security_headers_enabled=True))
    )

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["permissions-policy"] == (
        "camera=(), microphone=(), geolocation=()"
    )


def test_security_headers_are_not_forced_when_disabled() -> None:
    client = TestClient(
        create_app(settings=_settings(security_headers_enabled=False))
    )

    response = client.get("/health")

    assert response.status_code == 200
    assert "x-frame-options" not in response.headers


def test_security_headers_are_added_to_error_responses_when_enabled() -> None:
    app = _body_echo_app(
        max_request_body_bytes=4,
        security_headers_enabled=True,
    )

    response = TestClient(app).post("/echo-body", content=b"too-large")

    assert response.status_code == 413
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_request_size_limit_allows_small_body() -> None:
    app = _body_echo_app(max_request_body_bytes=64)
    response = TestClient(app).post("/echo-body", content=b"small")

    assert response.status_code == 200
    assert response.json() == {"size": 5}


def test_request_size_limit_rejects_oversized_body() -> None:
    app = _body_echo_app(max_request_body_bytes=8)
    response = TestClient(app).post(
        "/echo-body",
        content=b"too-large-body",
        headers={"X-Request-ID": "large-req-1"},
    )

    assert response.status_code == 413
    assert response.headers["x-request-id"] == "large-req-1"
    assert response.json() == {
        "error": {
            "type": "request_too_large",
            "message": "Request body too large",
            "request_id": "large-req-1",
        }
    }


def test_request_size_limit_replaces_invalid_request_id() -> None:
    app = _body_echo_app(max_request_body_bytes=8)
    response = TestClient(app).post(
        "/echo-body",
        content=b"too-large-body",
        headers={"X-Request-ID": "bad request id\n"},
    )

    assert response.status_code == 413
    request_id = response.headers["x-request-id"]
    assert request_id
    assert request_id != "unknown"
    assert request_id != "bad request id\n"
    assert response.json()["error"]["request_id"] == request_id


def test_rate_limiting_returns_429_when_enabled() -> None:
    client = TestClient(
        _limited_get_app(
            rate_limit_requests=2,
            rate_limit_window_seconds=60,
        )
    )

    assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 200
    response = client.get("/limited", headers={"X-Request-ID": "rate-req-1"})

    assert response.status_code == 429
    assert response.headers["x-request-id"] == "rate-req-1"
    assert response.headers["retry-after"]
    assert response.json() == {
        "error": {
            "type": "rate_limited",
            "message": "Too many requests",
            "request_id": "rate-req-1",
        }
    }


def test_rate_limiting_is_disabled_when_setting_is_false() -> None:
    client = TestClient(
        create_app(
            settings=_settings(
                rate_limit_enabled=False,
                rate_limit_requests=1,
                rate_limit_window_seconds=60,
            )
        )
    )

    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200


def test_rate_limiting_state_is_per_app_instance() -> None:
    first_client = TestClient(
        _limited_get_app(
            rate_limit_requests=1,
            rate_limit_window_seconds=60,
        )
    )
    second_client = TestClient(
        _limited_get_app(
            rate_limit_requests=1,
            rate_limit_window_seconds=60,
        )
    )

    assert first_client.get("/limited").status_code == 200
    assert first_client.get("/limited").status_code == 429
    assert second_client.get("/limited").status_code == 200


def test_malformed_content_length_does_not_crash_size_check() -> None:
    middleware = APIProtectionMiddleware(
        app=lambda _scope, _receive, _send: None,
        settings=_settings(max_request_body_bytes=8),
    )
    scope = {
        "type": "http",
        "headers": [(b"content-length", b"not-a-number")],
    }

    assert middleware._content_length_too_large(scope) is False


def test_rate_limit_key_handles_missing_client_host() -> None:
    middleware = APIProtectionMiddleware(
        app=lambda _scope, _receive, _send: None,
        settings=_settings(
            rate_limit_enabled=True,
            rate_limit_requests=1,
            rate_limit_window_seconds=60,
        ),
    )
    scope = {"type": "http", "client": None, "headers": []}

    assert middleware._rate_limit_retry_after(scope) is None
    assert middleware._rate_limit_retry_after(scope) is not None


def test_rate_limiter_prunes_expired_buckets() -> None:
    middleware = APIProtectionMiddleware(
        app=lambda _scope, _receive, _send: None,
        settings=_settings(
            rate_limit_enabled=True,
            rate_limit_requests=1,
            rate_limit_window_seconds=60,
        ),
    )
    middleware._rate_limits["expired"] = RateLimitBucket(count=1, reset_at=1.0)
    middleware._rate_limits["active"] = RateLimitBucket(count=1, reset_at=100.0)

    middleware._prune_expired_rate_limits(now=10.0)

    assert set(middleware._rate_limits) == {"active"}


def test_public_demo_cors_allows_exact_configured_origin() -> None:
    client = TestClient(
        create_app(
            settings=Settings(
                app_env="public_demo",
                database_url="sqlite:///public-demo.db",
                cors_allowed_origins="https://demo.example",
                _env_file=None,
            )
        )
    )

    response = client.options(
        "/regions",
        headers={
            "Origin": "https://demo.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Request-ID",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://demo.example"
    assert "*" not in response.headers["access-control-allow-origin"]
    assert "X-Request-ID" in response.headers["access-control-allow-headers"]


def test_public_demo_cors_rejects_unconfigured_origin() -> None:
    client = TestClient(
        create_app(
            settings=Settings(
                app_env="public_demo",
                database_url="sqlite:///public-demo.db",
                cors_allowed_origins="https://demo.example",
                _env_file=None,
            )
        )
    )

    response = client.options(
        "/regions",
        headers={
            "Origin": "https://other.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def _body_echo_app(
    *,
    max_request_body_bytes: int,
    security_headers_enabled: bool = False,
):
    app = create_app(
        settings=_settings(
            max_request_body_bytes=max_request_body_bytes,
            security_headers_enabled=security_headers_enabled,
        )
    )

    @app.post("/echo-body")
    async def echo_body(request: Request) -> dict[str, int]:
        body = await request.body()
        return {"size": len(body)}

    return app


def _limited_get_app(
    *,
    rate_limit_requests: int,
    rate_limit_window_seconds: int,
):
    app = create_app(
        settings=_settings(
            rate_limit_enabled=True,
            rate_limit_requests=rate_limit_requests,
            rate_limit_window_seconds=rate_limit_window_seconds,
        )
    )

    @app.get("/limited")
    def limited() -> dict[str, bool]:
        return {"ok": True}

    return app


def _settings(
    *,
    security_headers_enabled: bool = False,
    rate_limit_enabled: bool = False,
    rate_limit_requests: int = 120,
    rate_limit_window_seconds: int = 60,
    max_request_body_bytes: int = 1_048_576,
) -> Settings:
    return Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        security_headers_enabled=security_headers_enabled,
        rate_limit_enabled=rate_limit_enabled,
        rate_limit_requests=rate_limit_requests,
        rate_limit_window_seconds=rate_limit_window_seconds,
        max_request_body_bytes=max_request_body_bytes,
        _env_file=None,
    )
