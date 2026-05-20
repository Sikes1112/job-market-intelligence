from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.api.app import create_app
from backend.config.settings import Settings


def test_validation_error_returns_safe_response_with_request_id(client: TestClient) -> None:
    response = client.get(
        "/compare",
        params={"region_a": "greater_boston"},
        headers={"X-Request-ID": "validation-req-1"},
    )

    assert response.status_code == 422
    assert response.headers["x-request-id"] == "validation-req-1"
    body = response.json()
    assert body == {
        "error": {
            "type": "validation_error",
            "message": "Invalid request",
            "request_id": "validation-req-1",
        }
    }


def test_unknown_route_returns_safe_404_with_request_id(client: TestClient) -> None:
    response = client.get("/missing-route", headers={"X-Request-ID": "missing-req-1"})

    assert response.status_code == 404
    assert response.headers["x-request-id"] == "missing-req-1"
    assert response.json() == {
        "error": {
            "type": "not_found",
            "message": "Not Found",
            "request_id": "missing-req-1",
        }
    }


def test_database_error_returns_safe_response_without_leakage() -> None:
    app = create_app(settings=_test_settings())

    @app.get("/db-error")
    def db_error() -> None:
        raise SQLAlchemyError(
            "SELECT * FROM private_table using postgresql://user:secret@example/db"
        )

    response = TestClient(app, raise_server_exceptions=False).get(
        "/db-error",
        headers={"X-Request-ID": "db-req-1"},
    )

    assert response.status_code == 503
    assert response.headers["x-request-id"] == "db-req-1"
    assert response.json() == {
        "error": {
            "type": "database_error",
            "message": "Database unavailable",
            "request_id": "db-req-1",
        }
    }
    assert "secret" not in response.text
    assert "postgresql://" not in response.text
    assert "SELECT" not in response.text


def test_unexpected_error_returns_safe_response_without_leakage() -> None:
    app = create_app(settings=_test_settings())

    @app.get("/unexpected")
    def unexpected() -> None:
        raise RuntimeError("secret stack trace detail")

    response = TestClient(app, raise_server_exceptions=False).get(
        "/unexpected",
        headers={"X-Request-ID": "unexpected-req-1"},
    )

    assert response.status_code == 500
    assert response.headers["x-request-id"] == "unexpected-req-1"
    assert response.json() == {
        "error": {
            "type": "internal_error",
            "message": "Internal server error",
            "request_id": "unexpected-req-1",
        }
    }
    assert "secret" not in response.text
    assert "stack trace" not in response.text


def test_existing_domain_error_envelope_includes_request_id(api_client: TestClient) -> None:
    response = api_client.get("/regions/ghost", headers={"X-Request-ID": "domain-req-1"})

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["request_id"] == "domain-req-1"


def _test_settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        rate_limit_enabled=False,
        security_headers_enabled=False,
        _env_file=None,
    )
