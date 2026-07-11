"""Convenience entry point for the checked-in Greater NYC curated dataset."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.imports.post_import import run_curated_market_post_import
from backend.imports.result import (
    CuratedMarketImportResult,
    CuratedMarketPostImportResult,
)
from backend.imports.service import import_curated_market_dataset


def nyc_dataset_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "imports" / "nyc"


def import_nyc_dataset(
    session: Session,
    *,
    as_of: date | datetime | None = None,
) -> CuratedMarketImportResult:
    return import_curated_market_dataset(session, "nyc", as_of=as_of)


def run_nyc_post_import(
    session: Session,
    *,
    as_of: date | datetime | None = None,
    comparison_region_ids: tuple[str, ...] = (),
) -> CuratedMarketPostImportResult:
    return run_curated_market_post_import(
        session,
        "nyc",
        as_of=as_of,
        comparison_region_ids=comparison_region_ids,
    )
