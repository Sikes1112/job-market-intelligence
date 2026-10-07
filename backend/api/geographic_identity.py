"""Shared API adapter for canonical geographic route/query identities."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.geography.repository import RegionRepository
from backend.geography.resolver import GeographicResolver


def require_canonical_region_id(session: Session, value: str) -> str:
    """Resolve an API identity token or raise a typed geography exception."""

    resolution = GeographicResolver(RegionRepository(session)).require(value)
    assert resolution.region_id is not None
    return resolution.region_id
