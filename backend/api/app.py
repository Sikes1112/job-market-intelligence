from fastapi import FastAPI
from sqlalchemy import Engine

from backend.api.personalized import router as personalized_router
from backend.api.routes import router as read_router
from backend.config.settings import get_settings
from backend.shared.db import make_engine, make_session_factory
from backend.shared.logging import configure_logging


def create_app(*, engine: Engine | None = None) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, service_name=settings.service_name)

    app = FastAPI(
        title="Job Market Intelligence Backend",
        version="0.1.0",
    )

    # Engine + session_factory are stored on app.state. Tests build the app
    # with a test-bound engine so /regions, /companies, /compare can read
    # the same in-memory data the test fixture seeded.
    if engine is None:
        engine = make_engine(settings.database_url)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "success",
            "data": {"service": "ok"},
            "metadata": {
                "state": "fresh",
                "warnings": [],
            },
            "error": None,
        }

    app.include_router(read_router)
    app.include_router(personalized_router)

    return app


app = create_app()
