from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.shared.db import create_all, make_engine, make_session_factory


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def session() -> Iterator[Session]:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    factory = make_session_factory(engine)
    s = factory()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


@pytest.fixture
def api_client(session: Session) -> TestClient:
    """FastAPI TestClient sharing the same in-memory DB as the ``session``
    fixture. The API routes resolve ``get_session`` to yield the test's
    seeded session via FastAPI's dependency-override mechanism."""
    app = create_app(engine=session.bind)

    def _override_get_session() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    return TestClient(app)
