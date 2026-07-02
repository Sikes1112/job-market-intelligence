"""Read-only public benchmark API for Layer 19."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.api.envelope import NOT_FOUND, error_envelope, lightweight_success_envelope
from backend.public_benchmarks.registry import (
    get_public_benchmark,
    list_public_benchmarks,
)

router = APIRouter(tags=["public-benchmarks"])


@router.get("/public/benchmarks")
def list_benchmarks() -> dict:
    payload = list_public_benchmarks()
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/public/benchmarks/{slug}")
def get_benchmark(slug: str):
    payload = get_public_benchmark(slug)
    if payload is None:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Public benchmark not found: {slug!r}",
            ),
        )
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))
