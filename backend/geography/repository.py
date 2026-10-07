"""Thin data-access layer for the Region table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.geography.models import Region, RegionAlias, RegionStateMembership


class RegionRepository:
    """Repository for :class:`backend.geography.models.Region`.

    Pure data access. No business validation lives here.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, region_id: str) -> Region | None:
        return self._session.get(Region, region_id)

    @property
    def session(self) -> Session:
        return self._session

    def get_by_public_slug(self, public_slug: str) -> Region | None:
        return self._session.execute(
            select(Region).where(Region.public_slug == public_slug)
        ).scalar_one_or_none()

    def list_by_normalized_name(self, normalized_name: str) -> list[Region]:
        rows = self.list()
        from backend.geography.resolver import normalize_geographic_input

        return [
            row
            for row in rows
            if normalized_name
            in {
                normalize_geographic_input(row.region_id),
                normalize_geographic_input(row.region_name),
                normalize_geographic_input(row.display_name),
            }
        ]

    def aliases_for_normalized(self, normalized_alias: str) -> list[RegionAlias]:
        rows = self._session.execute(
            select(RegionAlias)
            .where(RegionAlias.normalized_alias == normalized_alias)
            .order_by(RegionAlias.region_id, RegionAlias.region_alias_id)
        ).scalars()
        return list(rows)

    def identity_matches(self, normalized_token: str) -> dict[str, set[str]]:
        """Return owners across every externally resolvable identity namespace.

        Cross-table uniqueness cannot be expressed with a normal SQL unique
        constraint.  Write services use this read in the same transaction as
        the write, and the resolver uses it to fail closed if legacy/manual
        data ever contains a collision.
        """

        if not normalized_token:
            return {}
        from backend.geography.resolver import normalize_geographic_input

        matches: dict[str, set[str]] = {}
        for region in self.list():
            if normalize_geographic_input(region.region_id) == normalized_token:
                matches.setdefault(region.region_id, set()).add("region_id")
            if (
                region.public_slug is not None
                and normalize_geographic_input(region.public_slug) == normalized_token
            ):
                matches.setdefault(region.region_id, set()).add("public_slug")
        for alias in self.aliases_for_normalized(normalized_token):
            matches.setdefault(alias.region_id, set()).add(f"alias:{alias.alias_type}")
        return matches

    def alias_for_normalized(self, normalized_alias: str) -> RegionAlias | None:
        rows = self.aliases_for_normalized(normalized_alias)
        return rows[0] if rows else None

    def aliases_for_region(self, region_id: str) -> list[RegionAlias]:
        rows = self._session.execute(
            select(RegionAlias)
            .where(RegionAlias.region_id == region_id)
            .order_by(RegionAlias.alias_type, RegionAlias.alias)
        ).scalars()
        return list(rows)

    def add_alias(self, alias: RegionAlias) -> None:
        self._session.add(alias)

    def state_codes(self, region_id: str) -> tuple[str, ...]:
        rows = self._session.execute(
            select(RegionStateMembership.state_code)
            .where(RegionStateMembership.region_id == region_id)
            .order_by(RegionStateMembership.state_code)
        ).scalars()
        return tuple(rows)

    def state_membership(self, region_id: str, state_code: str) -> RegionStateMembership | None:
        return self._session.get(RegionStateMembership, (region_id, state_code))

    def add_state_membership(self, membership: RegionStateMembership) -> None:
        self._session.add(membership)

    def exists(self, region_id: str) -> bool:
        return self.get(region_id) is not None

    def list(self) -> list[Region]:
        rows = self._session.execute(select(Region).order_by(Region.region_id)).scalars()
        return list(rows)

    def add(self, region: Region) -> None:
        self._session.add(region)

    def flush(self) -> None:
        self._session.flush()
