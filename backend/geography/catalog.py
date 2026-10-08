"""Repository-controlled curated geographic identity metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.geography.exceptions import GeographicAliasConflict
from backend.geography.models import RegionAlias, RegionStateMembership
from backend.geography.repository import RegionRepository
from backend.geography.resolver import (
    claim_identity_token,
    ensure_identity_token_available,
    normalize_geographic_input,
    normalize_public_slug,
)

_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "geography" / "curated_markets.json"


@dataclass(frozen=True, slots=True)
class CuratedGeography:
    region_id: str
    public_slug: str
    primary_city: str
    state_codes: tuple[str, ...]
    market_support_status: str
    centroid_latitude: float | None
    centroid_longitude: float | None
    focus_bounds: dict[str, Any] | None
    aliases: tuple[tuple[str, str], ...]


def load_curated_geographies(path: Path = _CATALOG_PATH) -> dict[str, CuratedGeography]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, CuratedGeography] = {}
    for item in payload["markets"]:
        centroid = item.get("centroid")
        aliases_by_normalized: dict[str, tuple[str, str]] = {}
        for alias in item["aliases"]:
            aliases_by_normalized.setdefault(
                normalize_geographic_input(alias["value"]),
                (alias["value"], alias["type"]),
            )
        geography = CuratedGeography(
            region_id=item["region_id"],
            public_slug=normalize_public_slug(item["public_slug"]),
            primary_city=item["primary_city"],
            state_codes=tuple(sorted({code.strip().upper() for code in item["state_codes"]})),
            market_support_status=item["market_support_status"],
            centroid_latitude=centroid.get("latitude") if centroid else None,
            centroid_longitude=centroid.get("longitude") if centroid else None,
            focus_bounds=item.get("focus_bounds"),
            aliases=tuple(aliases_by_normalized.values()),
        )
        if geography.region_id in result:
            raise RuntimeError(f"duplicate curated geography: {geography.region_id}")
        result[geography.region_id] = geography
    return result


def apply_curated_geography(repository: RegionRepository, region_id: str) -> bool:
    """Idempotently attach 41A metadata to an already-created curated Region."""

    definition = load_curated_geographies().get(region_id)
    region = repository.get(region_id)
    if definition is None or region is None:
        return False
    if region.public_slug is not None and region.public_slug != definition.public_slug:
        raise GeographicAliasConflict(
            f"published slug for {region_id!r} cannot be changed by curated metadata"
        )
    ensure_identity_token_available(
        repository,
        definition.public_slug,
        region_id=region_id,
    )
    region.public_slug = definition.public_slug
    claim_identity_token(
        repository,
        definition.public_slug,
        region_id=region_id,
        claim_type="public_slug",
        source="data/geography/curated_markets.json",
    )
    region.primary_city = definition.primary_city
    region.centroid_latitude = definition.centroid_latitude
    region.centroid_longitude = definition.centroid_longitude
    region.focus_bounds = definition.focus_bounds
    region.market_support_status = definition.market_support_status

    for state_code in definition.state_codes:
        if repository.state_membership(region_id, state_code) is None:
            repository.add_state_membership(
                RegionStateMembership(
                    region_id=region_id,
                    state_code=state_code,
                    membership_type="market_coverage",
                    source="data/geography/curated_markets.json",
                )
            )

    for index, (value, alias_type) in enumerate(definition.aliases, start=1):
        normalized = normalize_geographic_input(value)
        ensure_identity_token_available(repository, value, region_id=region_id)
        existing = repository.alias_for_normalized(normalized)
        if existing is not None:
            if existing.region_id != region_id:
                raise GeographicAliasConflict(
                    f"alias {value!r} already belongs to {existing.region_id!r}"
                )
            continue
        repository.add_alias(
            RegionAlias(
                region_alias_id=f"geo_alias_{region_id}_{index}",
                region_id=region_id,
                alias=value,
                normalized_alias=normalized,
                alias_type=alias_type,
                source="data/geography/curated_markets.json",
            )
        )
        claim_identity_token(
            repository,
            value,
            region_id=region_id,
            claim_type="import_key" if alias_type == "import_key" else "alias",
            source="data/geography/curated_markets.json",
        )
    repository.flush()
    return True
