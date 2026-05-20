from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config.settings import Settings
from backend.shared.db import create_all, make_engine


def test_health_startup_does_not_create_or_migrate_database(tmp_path) -> None:
    db_path = tmp_path / "startup.db"
    app = create_app(
        settings=Settings(
            app_env="local",
            database_url=f"sqlite:///{db_path}",
            _env_file=None,
        )
    )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert not db_path.exists()


def test_owned_engine_is_disposed_on_app_shutdown(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "owned.db"
    app = create_app(
        settings=Settings(
            app_env="local",
            database_url=f"sqlite:///{db_path}",
            _env_file=None,
        )
    )
    disposed: list[bool] = []
    original_dispose = app.state.engine.dispose

    def dispose() -> None:
        disposed.append(True)
        original_dispose()

    monkeypatch.setattr(app.state.engine, "dispose", dispose)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert disposed == []

    assert disposed == [True]


def test_injected_engine_is_not_disposed_on_app_shutdown(monkeypatch) -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    disposed: list[bool] = []
    original_dispose = engine.dispose
    monkeypatch.setattr(engine, "dispose", lambda: disposed.append(True))

    app = create_app(
        engine=engine,
        settings=Settings(
            app_env="test",
            database_url="sqlite:///:memory:",
            _env_file=None,
        ),
    )

    try:
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200

        assert disposed == []
    finally:
        original_dispose()


def test_ready_closes_database_check_connection_on_failure(client: TestClient) -> None:
    class FailingConnection:
        exited = False

        def __enter__(self):  # noqa: ANN204
            return self

        def __exit__(self, _exc_type, _exc, _tb) -> None:  # noqa: ANN001
            self.exited = True

        def execute(self, _statement):  # noqa: ANN001, ANN201
            raise RuntimeError("postgresql://user:secret@example.test/db")

    class FailingEngine:
        def __init__(self) -> None:
            self.connection = FailingConnection()

        def connect(self) -> FailingConnection:
            return self.connection

    engine = FailingEngine()
    client.app.state.engine = engine

    response = client.get("/ready")

    assert response.status_code == 503
    assert engine.connection.exited is True
    assert "secret" not in response.text
