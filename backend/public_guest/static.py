from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles

from backend.config.settings import Settings
from backend.public_guest.policy import public_guest_frontend_path_allowed


class ImmutableStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: dict) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def configure_public_guest_frontend(app: FastAPI, settings: Settings) -> None:
    if not settings.is_public_guest_demo:
        return
    dist_dir = resolve_frontend_dist_dir(settings.frontend_dist_dir)
    index_file = dist_dir / "index.html"
    assets_dir = dist_dir / "assets"
    if not index_file.is_file() or not assets_dir.is_dir():
        raise RuntimeError(
            f"compiled frontend is missing from {dist_dir}; run the frontend build first"
        )

    app.mount(
        "/assets",
        ImmutableStaticFiles(directory=assets_dir, check_dir=True),
        name="public-guest-assets",
    )
    data_dir = dist_dir / "data"
    if data_dir.is_dir():
        app.mount(
            "/data",
            StaticFiles(directory=data_dir, check_dir=True),
            name="public-guest-data",
        )

    @app.get("/", include_in_schema=False, name="public-guest-spa-root")
    def spa_root(request: Request) -> FileResponse:
        return _spa_index(request, index_file)

    @app.get("/{frontend_path:path}", include_in_schema=False, name="public-guest-spa-fallback")
    def spa_fallback(frontend_path: str, request: Request) -> FileResponse:
        path = f"/{frontend_path}"
        if not public_guest_frontend_path_allowed(path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return _spa_index(request, index_file)


def resolve_frontend_dist_dir(configured: str) -> Path:
    path = Path(configured)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return path.resolve()


def _spa_index(request: Request, index_file: Path) -> FileResponse:
    if "text/html" not in request.headers.get("accept", "").lower():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return FileResponse(
        index_file,
        media_type="text/html",
        headers={"Cache-Control": "no-cache, max-age=0, must-revalidate"},
    )
