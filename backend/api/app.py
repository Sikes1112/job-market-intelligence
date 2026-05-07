from fastapi import FastAPI

from backend.config.settings import get_settings
from backend.shared.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, service_name=settings.service_name)

    app = FastAPI(
        title="Job Market Intelligence Backend",
        version="0.1.0",
    )

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

    return app


app = create_app()
