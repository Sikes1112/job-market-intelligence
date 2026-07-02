"""Read-only public report API for Layer 19."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.api.envelope import NOT_FOUND, error_envelope, lightweight_success_envelope
from backend.public_reports.registry import get_public_report, list_public_reports

router = APIRouter(tags=["public-reports"])


@router.get("/public/reports")
def list_reports() -> dict:
    payload = list_public_reports()
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/public/reports/{slug}")
def get_report(slug: str):
    payload = get_public_report(slug)
    if payload is None:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Public report not found: {slug!r}",
            ),
        )
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))
