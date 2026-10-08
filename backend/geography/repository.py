"""Thin data-access layer for the Region table."""

from __future__ import annotations

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from backend.geography.models import (
    Region,
    RegionAlias,
    RegionCanonicalRedirect,
    RegionIdentityClaim,
    RegionStateMembership,
)


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

    def get_redirect(self, legacy_region_id: str) -> RegionCanonicalRedirect | None:
        return self._session.get(RegionCanonicalRedirect, legacy_region_id)

    def canonical_region_id(self, region_id: str) -> str:
        """Return the active identity, failing closed on corrupted redirect chains."""

        current = region_id
        visited: set[str] = set()
        while True:
            if current in visited:
                raise RuntimeError(f"cycle in Region canonical redirects at {current!r}")
            visited.add(current)
            redirect = self.get_redirect(current)
            if redirect is None:
                return current
            current = redirect.canonical_region_id

    def canonical_region(self, region_id: str) -> Region | None:
        return self.get(self.canonical_region_id(region_id))

    def current_output_identities(
        self,
        region_ids: set[str],
    ) -> dict[str, dict[str, str | None]]:
        """Resolve stored Region IDs to final current output identity in one query."""

        if not region_ids:
            return {}
        statement = text(
            "WITH RECURSIVE region_chain(stored_region_id, current_region_id) AS ("
            " SELECT region_id, region_id FROM regions WHERE region_id IN :region_ids"
            " UNION"
            " SELECT chain.stored_region_id, redirects.canonical_region_id"
            " FROM region_chain AS chain"
            " JOIN region_canonical_redirects AS redirects"
            " ON redirects.legacy_region_id = chain.current_region_id"
            "), final_regions AS ("
            " SELECT chain.stored_region_id, chain.current_region_id"
            " FROM region_chain AS chain"
            " LEFT JOIN region_canonical_redirects AS next_redirect"
            " ON next_redirect.legacy_region_id = chain.current_region_id"
            " WHERE next_redirect.legacy_region_id IS NULL"
            ")"
            " SELECT final_regions.stored_region_id, regions.region_id,"
            " regions.public_slug, regions.display_name"
            " FROM final_regions"
            " JOIN regions ON regions.region_id = final_regions.current_region_id"
        ).bindparams(bindparam("region_ids", expanding=True))
        return {
            row.stored_region_id: {
                "region_id": row.region_id,
                "public_slug": row.public_slug,
                "display_name": row.display_name,
            }
            for row in self._session.execute(
                statement,
                {"region_ids": sorted(region_ids)},
            )
        }

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
        """Return the owner of an external identity token.

        Migrated and service-written data always resolves through the atomic
        claim table. The fallback keeps pre-0042/test-fixture rows readable;
        it is deliberately fail-closed if those legacy tables disagree.
        """

        if not normalized_token:
            return {}
        claim = self.identity_claim(normalized_token)
        if claim is not None:
            return {claim.region_id: {claim.claim_type}}

        from backend.geography.resolver import normalize_geographic_input

        matches: dict[str, set[str]] = {}
        for region in self.list():
            if normalize_geographic_input(region.region_id) == normalized_token:
                matches.setdefault(region.region_id, set()).add("legacy_region_id")
            if (
                region.public_slug is not None
                and normalize_geographic_input(region.public_slug) == normalized_token
            ):
                matches.setdefault(region.region_id, set()).add("legacy_public_slug")
        for alias in self.aliases_for_normalized(normalized_token):
            canonical_region_id = self.canonical_region_id(alias.region_id)
            matches.setdefault(canonical_region_id, set()).add(
                f"legacy_alias:{alias.alias_type}"
            )
        return matches

    def identity_claim(self, normalized_token: str) -> RegionIdentityClaim | None:
        for pending in self._session.new:
            if (
                isinstance(pending, RegionIdentityClaim)
                and pending.normalized_token == normalized_token
            ):
                return pending
        return self._session.get(RegionIdentityClaim, normalized_token)

    def add_identity_claim(self, claim: RegionIdentityClaim) -> None:
        self._session.add(claim)

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

    def list(self, *, include_historical: bool = False) -> list[Region]:
        stmt = select(Region)
        if not include_historical:
            stmt = stmt.where(
                ~Region.region_id.in_(select(RegionCanonicalRedirect.legacy_region_id))
            )
        rows = self._session.execute(stmt.order_by(Region.region_id)).scalars()
        return list(rows)

    def add(self, region: Region) -> None:
        self._session.add(region)

    def flush(self) -> None:
        self._session.flush()
