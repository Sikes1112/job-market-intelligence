from __future__ import annotations

import logging
from collections.abc import Iterator

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.api.request_context import get_request_id, request_id_from_scope
from backend.config.settings import Settings


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class RaisingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        raise RuntimeError("logging sink unavailable")


def test_request_logging_includes_observability_fields(client: TestClient) -> None:
    handler = ListHandler()
    logger = logging.getLogger("backend.api.requests")
    previous_level = logger.level
    previous_disabled = logger.disabled
    previous_manager_disable = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    logger.setLevel(logging.INFO)
    logger.disabled = False
    logger.addHandler(handler)
    try:
        response = client.get("/health")
    finally:
        logger.removeHandler(handler)
        logger.disabled = previous_disabled
        logger.setLevel(previous_level)
        logging.disable(previous_manager_disable)

    assert response.status_code == 200
    assert handler.records
    fields = handler.records[-1].extra_fields
    assert fields["request_id"] == response.headers["x-request-id"]
    assert fields["method"] == "GET"
    assert fields["path"] == "/health"
    assert fields["route"] == "/health"
    assert fields["status_code"] == 200
    assert isinstance(fields["duration_ms"], float)
    assert fields["duration_ms"] >= 0
    assert fields["error_type"] is None
    assert fields["release_id"] == "unknown"
    assert fields["service"] == "jmi-backend"
    assert get_request_id() is None


def test_request_logging_path_excludes_query_string(client: TestClient) -> None:
    handler = ListHandler()
    logger = logging.getLogger("backend.api.requests")
    previous_level = logger.level
    previous_disabled = logger.disabled
    previous_manager_disable = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    logger.setLevel(logging.INFO)
    logger.disabled = False
    logger.addHandler(handler)
    try:
        response = client.get("/health?DATABASE_URL=postgresql://user:secret@example/db")
    finally:
        logger.removeHandler(handler)
        logger.disabled = previous_disabled
        logger.setLevel(previous_level)
        logging.disable(previous_manager_disable)

    assert response.status_code == 200
    fields = handler.records[-1].extra_fields
    assert fields["path"] == "/health"
    assert fields["route"] == "/health"
    assert "secret" not in fields["path"]


def test_request_logging_sink_failure_does_not_crash_request(
    client: TestClient,
) -> None:
    handler = RaisingHandler()
    logger = logging.getLogger("backend.api.requests")
    previous_level = logger.level
    previous_disabled = logger.disabled
    previous_manager_disable = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    logger.setLevel(logging.INFO)
    logger.disabled = False
    logger.addHandler(handler)
    try:
        response = client.get("/health")
    finally:
        logger.removeHandler(handler)
        logger.disabled = previous_disabled
        logger.setLevel(previous_level)
        logging.disable(previous_manager_disable)

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert get_request_id() is None


def test_request_logging_includes_error_type_for_unhandled_exception(
    session: Session,
) -> None:
    app = _app_with_raising_route(session)
    handler = ListHandler()
    logger = logging.getLogger("backend.api.requests")
    previous_level = logger.level
    previous_disabled = logger.disabled
    previous_manager_disable = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    logger.setLevel(logging.INFO)
    logger.disabled = False
    logger.addHandler(handler)
    try:
        response = TestClient(app, raise_server_exceptions=False).get("/boom")
    finally:
        logger.removeHandler(handler)
        logger.disabled = previous_disabled
        logger.setLevel(previous_level)
        logging.disable(previous_manager_disable)

    assert response.status_code == 500
    assert handler.records
    fields = handler.records[-1].extra_fields
    assert fields["request_id"]
    assert fields["method"] == "GET"
    assert fields["path"] == "/boom"
    assert fields["route"] == "/boom"
    assert fields["status_code"] == 500
    assert fields["error_type"] == "ValueError"
    assert get_request_id() is None


def test_request_logging_includes_error_type_for_protection_response() -> None:
    app = create_app(
        settings=Settings(
            app_env="test",
            database_url="sqlite:///:memory:",
            max_request_body_bytes=4,
            _env_file=None,
        )
    )

    @app.post("/echo-body")
    async def echo_body(request: Request) -> dict[str, int]:
        body = await request.body()
        return {"size": len(body)}

    handler = ListHandler()
    logger = logging.getLogger("backend.api.requests")
    previous_level = logger.level
    previous_disabled = logger.disabled
    previous_manager_disable = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    logger.setLevel(logging.INFO)
    logger.disabled = False
    logger.addHandler(handler)
    try:
        response = TestClient(app).post("/echo-body", content=b"too-large")
    finally:
        logger.removeHandler(handler)
        logger.disabled = previous_disabled
        logger.setLevel(previous_level)
        logging.disable(previous_manager_disable)

    assert response.status_code == 413
    assert handler.records
    fields = handler.records[-1].extra_fields
    assert fields["request_id"] == response.headers["x-request-id"]
    assert fields["method"] == "POST"
    assert fields["path"] == "/echo-body"
    assert fields["status_code"] == 413
    assert fields["duration_ms"] >= 0
    assert fields["error_type"] == "request_too_large"
    assert get_request_id() is None


def test_request_logging_includes_public_demo_denial_error_type() -> None:
    app = create_app(
        settings=Settings(
            app_env="public_demo",
            database_url="sqlite:///public-demo.db",
            cors_allowed_origins="https://demo.example",
            _env_file=None,
        )
    )
    handler = ListHandler()
    logger = logging.getLogger("backend.api.requests")
    previous_level = logger.level
    previous_disabled = logger.disabled
    previous_manager_disable = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    logger.setLevel(logging.INFO)
    logger.disabled = False
    logger.addHandler(handler)
    try:
        response = TestClient(app).post(
            "/admin/overrides",
            headers={"X-Request-ID": "public-demo-denied-1"},
            json={"target_id": "comp_a"},
        )
    finally:
        logger.removeHandler(handler)
        logger.disabled = previous_disabled
        logger.setLevel(previous_level)
        logging.disable(previous_manager_disable)

    assert response.status_code == 403
    assert handler.records
    fields = handler.records[-1].extra_fields
    assert fields["request_id"] == "public-demo-denied-1"
    assert fields["method"] == "POST"
    assert fields["path"] == "/admin/overrides"
    assert fields["status_code"] == 403
    assert fields["error_type"] == "public_demo_read_only"
    assert get_request_id() is None


def test_request_id_from_scope_generates_safe_id_without_observability() -> None:
    scope = {"type": "http", "headers": []}

    request_id = request_id_from_scope(scope)

    assert request_id
    assert request_id != "unknown"
    assert scope["state"]["request_id"] == request_id


def _app_with_raising_route(session: Session) -> FastAPI:
    app = create_app(engine=session.bind)

    def _override_get_session() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = _override_get_session

    @app.get("/boom")
    def boom() -> None:
        raise ValueError("test-only failure")

    return app
