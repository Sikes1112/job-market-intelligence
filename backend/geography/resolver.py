"""Canonical geographic lookup and compatibility resolution.

Lookup normalization is deliberately narrower than identity: it folds case,
outer/internal whitespace, and separator punctuation (spaces, ``-``, ``_``,
``/``, commas, and periods). Abbreviations are data in ``region_aliases``;
they are never inferred. Durable identity remains ``Region.region_id``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from backend.geography.exceptions import (
    GeographicIdentityConflict,
    GeographicInputAmbiguous,
    GeographicInputUnknown,
)
from backend.geography.models import Region
from backend.geography.repository import RegionRepository

ResolutionStatus = Literal["resolved", "unresolved", "ambiguous"]

_SEPARATOR_RE = re.compile(r"[\s_\-/,\.]+")
_SLUG_INVALID_RE = re.compile(r"[^a-z0-9-]+")
_SLUG_DASH_RE = re.compile(r"-+")
MAX_PUBLIC_SLUG_LENGTH = 96


def normalize_geographic_input(value: object) -> str:
    """Return the stable lookup form; never use this as persisted identity."""

    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return _SEPARATOR_RE.sub(" ", normalized).strip()


def normalize_public_slug(value: object) -> str:
    if not isinstance(value, str):
        return ""
    slug = unicodedata.normalize("NFKC", value).casefold().strip().replace("_", " ")
    slug = re.sub(r"\s+", "-", slug)
    slug = _SLUG_INVALID_RE.sub("-", slug)
    return _SLUG_DASH_RE.sub("-", slug).strip("-")


def ensure_identity_token_available(
    repository: RegionRepository,
    value: object,
    *,
    region_id: str,
) -> str:
    """Validate one ID/slug/alias token against the shared lookup namespace."""

    normalized = normalize_geographic_input(value)
    if not normalized:
        raise GeographicIdentityConflict("geographic identity token must not be blank")
    owners = repository.identity_matches(normalized)
    conflicts = sorted(owner for owner in owners if owner != region_id)
    if conflicts:
        raise GeographicIdentityConflict(
            f"geographic token {value!r} is already owned by {conflicts!r}"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class GeographicResolution:
    status: ResolutionStatus
    input_value: str
    normalized_input: str
    region_id: str | None = None
    public_slug: str | None = None
    display_name: str | None = None
    region_type: str | None = None
    resolution_source: str | None = None
    state_codes: tuple[str, ...] = ()
    primary_city: str | None = None
    centroid_latitude: float | None = None
    centroid_longitude: float | None = None
    focus_bounds: dict | None = None
    market_support_status: str = "unknown"
    candidate_region_ids: tuple[str, ...] = ()

    @property
    def resolved(self) -> bool:
        return self.status == "resolved" and self.region_id is not None

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "input": self.input_value,
            "normalized_input": self.normalized_input,
            "region_id": self.region_id,
            "public_slug": self.public_slug,
            "display_name": self.display_name,
            "region_type": self.region_type,
            "resolution_source": self.resolution_source,
            "state_codes": list(self.state_codes),
            "primary_city": self.primary_city,
            "centroid": (
                {
                    "latitude": self.centroid_latitude,
                    "longitude": self.centroid_longitude,
                }
                if self.centroid_latitude is not None and self.centroid_longitude is not None
                else None
            ),
            "focus_bounds": self.focus_bounds,
            "market_support_status": self.market_support_status,
            "candidate_region_ids": list(self.candidate_region_ids),
        }


class GeographicResolver:
    """Resolve supported identity forms to one canonical Region."""

    def __init__(self, repository: RegionRepository) -> None:
        self._repo = repository

    def resolve(self, value: object) -> GeographicResolution:
        raw = value.strip() if isinstance(value, str) else ""
        normalized = normalize_geographic_input(raw)
        if not raw or not normalized:
            return self._unresolved(raw, normalized)

        # IDs, public slugs, and aliases are one conflict-safe namespace.  New
        # writes prevent collisions; this ambiguity branch makes pre-existing
        # or manually-corrupted data fail closed instead of relying on lookup
        # precedence.
        identity_matches = self._repo.identity_matches(normalized)
        identity_region_ids = tuple(sorted(identity_matches))
        if len(identity_region_ids) > 1:
            return self._ambiguous(raw, normalized, identity_region_ids)
        if identity_region_ids:
            region = self._repo.get(identity_region_ids[0])
            if region is not None:
                sources = identity_matches[region.region_id]
                if raw == region.region_id and "region_id" in sources:
                    source = "region_id"
                elif "public_slug" in sources:
                    source = "public_slug"
                else:
                    source = sorted(sources)[0]
                return self._resolved(raw, normalized, region, source)

        # Compatibility for pre-41A/ad-hoc Regions that do not yet have aliases.
        name_matches = self._repo.list_by_normalized_name(normalized)
        candidates = tuple(sorted({region.region_id for region in name_matches}))
        if len(candidates) > 1:
            return self._ambiguous(raw, normalized, candidates)
        if name_matches:
            return self._resolved(raw, normalized, name_matches[0], "legacy_region_name")
        return self._unresolved(raw, normalized)

    def require(self, value: object) -> GeographicResolution:
        result = self.resolve(value)
        if result.status == "ambiguous":
            raise GeographicInputAmbiguous(
                f"ambiguous geographic input {result.input_value!r}: "
                f"{list(result.candidate_region_ids)!r}"
            )
        if not result.resolved:
            raise GeographicInputUnknown(f"unknown geographic input: {result.input_value!r}")
        return result

    def _resolved(
        self,
        raw: str,
        normalized: str,
        region: Region,
        source: str,
    ) -> GeographicResolution:
        return GeographicResolution(
            status="resolved",
            input_value=raw,
            normalized_input=normalized,
            region_id=region.region_id,
            public_slug=region.public_slug,
            display_name=region.display_name,
            region_type=region.region_type,
            resolution_source=source,
            state_codes=self._repo.state_codes(region.region_id),
            primary_city=region.primary_city,
            centroid_latitude=region.centroid_latitude,
            centroid_longitude=region.centroid_longitude,
            focus_bounds=region.focus_bounds,
            market_support_status=region.market_support_status,
            candidate_region_ids=(region.region_id,),
        )

    @staticmethod
    def _unresolved(raw: str, normalized: str) -> GeographicResolution:
        return GeographicResolution(
            status="unresolved", input_value=raw, normalized_input=normalized
        )

    @staticmethod
    def _ambiguous(raw: str, normalized: str, candidates: tuple[str, ...]) -> GeographicResolution:
        return GeographicResolution(
            status="ambiguous",
            input_value=raw,
            normalized_input=normalized,
            candidate_region_ids=candidates,
        )
