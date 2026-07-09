from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, text

from backend.api.admin import router as admin_router
from backend.api.auth0_middleware import Auth0JWTMiddleware
from backend.api.billing import router as billing_router
from backend.api.career_agent import router as career_agent_router
from backend.api.data_standards import router as data_standards_router
from backend.api.errors import register_exception_handlers
from backend.api.exceptions import router as exceptions_router
from backend.api.external import router as external_router
from backend.api.institutions import router as institutions_router
from backend.api.integrations import router as integrations_router
from backend.api.monetization import router as monetization_router
from backend.api.observability import RequestObservabilityMiddleware
from backend.api.opportunities import router as opportunities_router
from backend.api.personalized import router as personalized_router
from backend.api.platform_intelligence import router as platform_intelligence_router
from backend.api.platform_public import router as platform_public_router
from backend.api.policy import router as policy_router
from backend.api.protection import APIProtectionMiddleware
from backend.api.public_benchmarks import router as public_benchmarks_router
from backend.api.public_reports import router as public_reports_router
from backend.api.recommendations import router as recommendations_router
from backend.api.routes import router as read_router
from backend.api.trust import router as trust_router
from backend.api.user import router as user_router
from backend.api.user_intelligence import router as user_intelligence_router
from backend.api.user_reports import router as user_reports_router
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
            allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
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
    app.state.billing_provider = None

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
    app.include_router(career_agent_router)
    app.include_router(data_standards_router)
    app.include_router(public_benchmarks_router)
    app.include_router(public_reports_router)
    app.include_router(opportunities_router)
    app.include_router(trust_router)
    app.include_router(exceptions_router)
    app.include_router(user_intelligence_router)
    app.include_router(user_reports_router)
    app.include_router(policy_router)
    app.include_router(platform_intelligence_router)
    app.include_router(platform_public_router)
    app.include_router(monetization_router)
    app.include_router(billing_router)
    app.include_router(user_router)
    app.include_router(institutions_router)
    app.include_router(integrations_router)
    app.include_router(external_router)
    app.include_router(admin_router)

    return app


app = create_app()
