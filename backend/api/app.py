from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, text

from backend.api.admin import router as admin_router
from backend.api.auth0_middleware import Auth0JWTMiddleware
from backend.api.errors import register_exception_handlers
from backend.api.observability import RequestObservabilityMiddleware
from backend.api.personalized import router as personalized_router
from backend.api.protection import APIProtectionMiddleware
from backend.api.recommendations import router as recommendations_router
from backend.api.routes import router as read_router
from backend.api.user import router as user_router
from backend.config.settings import Settings, get_settings
from backend.shared.db import make_engine, make_session_factory
from backend.shared.logging import configure_logging


def create_app(
    *, engine: Engine | None = None, settings: Settings | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, service_name=settings.service_name)
    owns_engine = engine is None
    if engine is None:
        engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if app.state.owns_engine:
                app.state.engine.dispose()

    app = FastAPI(
        title="Job Market Intelligence Backend",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(APIProtectionMiddleware, settings=settings)
    allowed_origins = settings.cors_allowed_origin_list
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )
    app.add_middleware(Auth0JWTMiddleware, settings=settings)
    app.add_middleware(RequestObservabilityMiddleware)
    register_exception_handlers(app)

    # Engine + session_factory are stored on app.state. Tests build the app
    # with a test-bound engine so /regions, /companies, /compare can read
    # the same in-memory data the test fixture seeded.
    app.state.settings = settings
    app.state.engine = engine
    app.state.owns_engine = owns_engine
    app.state.session_factory = make_session_factory(engine)

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "service": settings.service_name,
            "environment": settings.app_env.value,
        }

    @app.get("/ready")
    def ready() -> JSONResponse:
        checks = {"config": "ok", "database": "ok"}
        status_code = 200
        status_value = "ready"

        try:
            with app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1")).scalar_one()
        except Exception:
            checks["database"] = "failed"
            status_code = 503
            status_value = "not_ready"

        return JSONResponse(
            status_code=status_code,
            content={"status": status_value, "checks": checks},
        )

    app.include_router(read_router)
    app.include_router(personalized_router)
    app.include_router(recommendations_router)
    app.include_router(user_router)
    app.include_router(admin_router)

    return app


app = create_app()
