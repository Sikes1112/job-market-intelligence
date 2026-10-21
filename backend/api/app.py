from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from backend.api.admin import router as admin_router
from backend.api.auth0_middleware import Auth0JWTMiddleware
from backend.api.billing import router as billing_router
from backend.api.career_agent import router as career_agent_router
from backend.api.career_decisions import router as career_decisions_router
from backend.api.career_identity import router as career_identity_router
from backend.api.current_opportunities import router as current_opportunities_router
from backend.api.data_standards import router as data_standards_router
from backend.api.deep_decisions import router as deep_decisions_router
from backend.api.errors import register_exception_handlers
from backend.api.exceptions import router as exceptions_router
from backend.api.explore import router as explore_router
from backend.api.external import router as external_router
from backend.api.guest_sessions import router as guest_sessions_router
from backend.api.institutions import router as institutions_router
from backend.api.integrations import router as integrations_router
from backend.api.market_intelligence import router as market_intelligence_router
from backend.api.monetization import router as monetization_router
from backend.api.my_search import router as my_search_router
from backend.api.observability import RequestObservabilityMiddleware
from backend.api.operations import router as operations_router
from backend.api.opportunities import router as opportunities_router
from backend.api.personalized import router as personalized_router
from backend.api.platform_intelligence import router as platform_intelligence_router
from backend.api.platform_public import router as platform_public_router
from backend.api.policy import router as policy_router
from backend.api.product_measurement import router as product_measurement_router
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
from backend.explore.shared_intelligence import SharedIntelligenceCoordinator
from backend.operations.error_monitoring import ErrorMonitor
from backend.operations.metrics import InMemoryMetricsRegistry
from backend.operations.status import liveness_payload, readiness_payload
from backend.public_guest.lifecycle import initialize_public_guest_database
from backend.public_guest.middleware import PublicGuestSessionMiddleware
from backend.public_guest.static import configure_public_guest_frontend
from backend.shared.db import make_engine, make_session_factory
from backend.shared.logging import configure_logging


def create_app(*, engine: Engine | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, service_name=settings.service_name)
    owns_engine = engine is None
    if engine is None:
        engine = make_engine(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_recycle=settings.database_pool_recycle_seconds,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            if settings.is_public_guest_demo and app.state.owns_engine:
                initialize_public_guest_database(settings, app.state.engine)
                app.state.public_guest_database_initialized = True
                app.state.explore_shared_intelligence.invalidate()
            yield
        finally:
            if app.state.owns_engine:
                app.state.engine.dispose()

    app = FastAPI(
        title="Job Market Intelligence Backend",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )
    app.add_middleware(APIProtectionMiddleware, settings=settings)
    allowed_origins = settings.cors_allowed_origin_list
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=settings.is_public_guest_demo,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "X-API-Key",
                "X-Request-ID",
                "X-CSRF-Token",
            ],
            expose_headers=["X-Request-ID", "X-Release-ID"],
        )
    app.add_middleware(Auth0JWTMiddleware, settings=settings)
    app.add_middleware(PublicGuestSessionMiddleware, settings=settings)
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
    app.state.metrics_registry = InMemoryMetricsRegistry()
    app.state.error_monitor = ErrorMonitor()
    app.state.explore_shared_intelligence = (
        SharedIntelligenceCoordinator(
            release_id=settings.release_id,
            engine_identity=id(engine),
        )
        if settings.is_public_guest_demo
        else None
    )
    app.state.public_guest_database_initialized = not (
        settings.is_public_guest_demo and owns_engine
    )

    @app.get("/health")
    def health() -> dict:
        return liveness_payload(settings)

    @app.get("/ready")
    def ready() -> JSONResponse:
        if (
            settings.is_public_guest_demo
            and not app.state.public_guest_database_initialized
        ):
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "service": settings.service_name,
                    "environment": settings.app_env.value,
                    "release_id": settings.release_id,
                    "checks": {"config": "ok", "database": "initializing"},
                },
            )
        status_code, content = readiness_payload(app.state.engine, settings)
        return JSONResponse(status_code=status_code, content=content)

    app.include_router(guest_sessions_router)
    app.include_router(read_router)
    app.include_router(market_intelligence_router)
    app.include_router(personalized_router)
    app.include_router(recommendations_router)
    app.include_router(career_agent_router)
    app.include_router(career_decisions_router)
    app.include_router(my_search_router)
    app.include_router(career_identity_router)
    app.include_router(explore_router)
    app.include_router(deep_decisions_router)
    app.include_router(data_standards_router)
    app.include_router(public_benchmarks_router)
    app.include_router(public_reports_router)
    app.include_router(opportunities_router)
    app.include_router(current_opportunities_router)
    app.include_router(trust_router)
    app.include_router(exceptions_router)
    app.include_router(user_intelligence_router)
    app.include_router(user_reports_router)
    app.include_router(policy_router)
    app.include_router(platform_intelligence_router)
    app.include_router(platform_public_router)
    app.include_router(product_measurement_router)
    app.include_router(monetization_router)
    app.include_router(billing_router)
    app.include_router(user_router)
    app.include_router(institutions_router)
    app.include_router(integrations_router)
    app.include_router(external_router)
    app.include_router(operations_router)
    app.include_router(admin_router)

    configure_public_guest_frontend(app, settings)

    return app


app = create_app()
