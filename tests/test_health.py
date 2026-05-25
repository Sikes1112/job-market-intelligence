from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.config.settings import Settings


def test_health_is_liveness_only(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "jmi-backend"
    assert "environment" in body
    assert "database_url" not in body
    assert "checks" not in body


def test_health_does_not_depend_on_database(client: TestClient) -> None:
    class BrokenEngine:
        def connect(self):  # noqa: ANN201
            raise AssertionError("/health must not touch the database")

    client.app.state.engine = BrokenEngine()
    response = client.get("/health")

    assert response.status_code == 200


def test_health_response_header_includes_request_id(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["x-request-id"]


def test_health_preserves_valid_inbound_request_id(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "req-123_ABC"})

    assert response.headers["x-request-id"] == "req-123_ABC"


def test_health_replaces_unsafe_inbound_request_id(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "bad request id\n"})

    request_id = response.headers["x-request-id"]
    assert request_id
    assert request_id != "bad request id\n"


def test_health_replaces_overlong_inbound_request_id(client: TestClient) -> None:
    inbound = "a" * 129
    response = client.get("/health", headers={"X-Request-ID": inbound})

    request_id = response.headers["x-request-id"]
    assert request_id
    assert request_id != inbound


def test_ready_returns_ready_when_database_and_config_pass(session) -> None:
    app = create_app(engine=session.bind)
    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    ready_body = response.json()
    assert ready_body == {
        "status": "ready",
        "checks": {"config": "ok", "database": "ok"},
    }
    assert "database_url" not in ready_body


def test_ready_returns_503_when_database_check_fails(client: TestClient) -> None:
    class BrokenEngine:
        def connect(self):  # noqa: ANN201
            raise RuntimeError("postgresql://user:secret@example/db")

    client.app.state.engine = BrokenEngine()
    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body == {
        "status": "not_ready",
        "checks": {"config": "ok", "database": "failed"},
    }
    assert "secret" not in response.text
    assert "postgresql://" not in response.text


def test_health_and_ready_remain_available_in_public_demo(session: Session) -> None:
    app = create_app(
        engine=session.bind,
        settings=Settings(
            app_env="public_demo",
            database_url="sqlite:///explicit-public-demo.db",
            cors_allowed_origins="https://demo.example",
            _env_file=None,
        ),
    )
    client = TestClient(app)

    health = client.get("/health")
    ready = client.get("/ready")

    assert health.status_code == 200
    assert health.json()["environment"] == "public_demo"
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "checks": {"config": "ok", "database": "ok"},
    }
