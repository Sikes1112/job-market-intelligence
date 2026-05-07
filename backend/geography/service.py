"""Geography service: region CRUD with hierarchy validation.

This is the first real "service" slice. It owns:

* the :class:`RegionDefinition` Pydantic input shape,
* create / update / upsert operations against :class:`Region`,
* parent / cycle validation,
* state-machine transitions for the build flow (``new → building → fresh``
  for new regions, ``fresh → rebuilding → fresh`` for updates).

It deliberately does **not**:

* enqueue or run jobs (the Geography Build job handler is a separate function
  and is itself a synchronous skeleton — Slice 14 owns dispatch);
* implement normalization formulas, GIS calculations, or custom user
  geographies (out of MVP scope);
* touch any non-geography canonical truth.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.geography.exceptions import (
    DuplicateRegion,
    InvalidRegionHierarchy,
    RegionNotFound,
)
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.geography.types import RegionType
from backend.shared.state import ObjectState, validate_transition
from backend.shared.versioning import next_version

UpsertOutcome = Literal["created", "updated", "unchanged"]

# Defensive depth limit on ancestor walks. Region hierarchies are
# city -> metro -> greater_region -> state at most for MVP; 32 is generous.
_MAX_ANCESTOR_DEPTH = 32


class RegionDefinition(BaseModel):
    """The canonical shape used by callers (and the Geography Build job) to
    declare a region. ``region_id`` is the stable slug-style identifier.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1)
    region_name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    region_type: RegionType
    parent_region_id: str | None = None
    labor_market_group: str | None = None
    normalization_profile_id: str | None = None


class GeographyService:
    def __init__(self, repository: RegionRepository) -> None:
        self._repo = repository

    # --- reads -----------------------------------------------------------

    def get_region(self, region_id: str) -> Region:
        region = self._repo.get(region_id)
        if region is None:
            raise RegionNotFound(region_id)
        return region

    def list_regions(self) -> list[Region]:
        return self._repo.list()

    # --- writes ----------------------------------------------------------

    def create_region(self, definition: RegionDefinition) -> Region:
        if self._repo.exists(definition.region_id):
            raise DuplicateRegion(definition.region_id)
        self._validate_hierarchy(definition.region_id, definition.parent_region_id)
        region = Region(
            region_id=definition.region_id,
            region_name=definition.region_name,
            display_name=definition.display_name,
            region_type=definition.region_type.value,
            parent_region_id=definition.parent_region_id,
            labor_market_group=definition.labor_market_group,
            normalization_profile_id=definition.normalization_profile_id,
        )
        self._repo.add(region)
        self._repo.flush()
        return region

    def update_region(self, definition: RegionDefinition) -> Region:
        region = self.get_region(definition.region_id)
        self._validate_hierarchy(definition.region_id, definition.parent_region_id)
        self._apply_definition(region, definition)
        region.version = next_version(region.version)
        self._repo.flush()
        return region

    def upsert_for_build(
        self, definition: RegionDefinition
    ) -> tuple[Region, UpsertOutcome]:
        """Idempotent upsert used by the Geography Build job handler.

        * If the region does not exist, create it and walk it through
          ``new → building → fresh``.
        * If it exists and the definition matches every stored field, return
          ``"unchanged"`` (no version bump, no state change).
        * Otherwise apply the new definition and bump the version. State
          handling: a region that hasn't yet reached ``fresh`` (still ``new``
          or ``building``) is walked to ``fresh``; a region already ``fresh``
          stays ``fresh`` (the new content *is* the current build, so there is
          no honest reason to mark it stale). Reaching ``rebuilding`` happens
          via ``stale → rebuilding`` once freshness scheduling exists (Slice
          14+); ``OBJECT_STATE_MODEL.md`` §17 lists ``stale`` as the only
          documented predecessor of ``rebuilding``.
        """
        existing = self._repo.get(definition.region_id)
        if existing is None:
            region = self.create_region(definition)
            self._set_state(region, ObjectState.BUILDING)
            self._set_state(region, ObjectState.FRESH)
            self._repo.flush()
            return region, "created"

        if self._is_unchanged(existing, definition):
            return existing, "unchanged"

        self._validate_hierarchy(definition.region_id, definition.parent_region_id)
        self._apply_definition(existing, definition)
        existing.version = next_version(existing.version)

        if existing.state == ObjectState.NEW.value:
            self._set_state(existing, ObjectState.BUILDING)
            self._set_state(existing, ObjectState.FRESH)
        elif existing.state == ObjectState.BUILDING.value:
            self._set_state(existing, ObjectState.FRESH)
        # Other states (fresh, stale, partial, blocked, failed, rebuilding):
        # leave as-is. Slice 14 owns lifecycle progression beyond first build.

        self._repo.flush()
        return existing, "updated"

    # --- internals -------------------------------------------------------

    def _apply_definition(self, region: Region, definition: RegionDefinition) -> None:
        region.region_name = definition.region_name
        region.display_name = definition.display_name
        region.region_type = definition.region_type.value
        region.parent_region_id = definition.parent_region_id
        region.labor_market_group = definition.labor_market_group
        region.normalization_profile_id = definition.normalization_profile_id

    def _set_state(self, region: Region, target: ObjectState) -> None:
        validate_transition(region.state, target)
        region.state = target.value

    def _is_unchanged(self, region: Region, definition: RegionDefinition) -> bool:
        return (
            region.region_name == definition.region_name
            and region.display_name == definition.display_name
            and region.region_type == definition.region_type.value
            and region.parent_region_id == definition.parent_region_id
            and region.labor_market_group == definition.labor_market_group
            and region.normalization_profile_id == definition.normalization_profile_id
        )

    def _validate_hierarchy(self, region_id: str, parent_id: str | None) -> None:
        if parent_id is None:
            return
        if parent_id == region_id:
            raise InvalidRegionHierarchy(
                f"region {region_id!r} cannot be its own parent"
            )

        # Walk the proposed parent's ancestor chain. If we ever encounter
        # ``region_id``, accepting this parent would close a cycle.
        visited: set[str] = set()
        current: str | None = parent_id
        depth = 0
        while current is not None:
            if current == region_id:
                raise InvalidRegionHierarchy(
                    f"hierarchy cycle: {region_id!r} appears in its own ancestor chain"
                )
            if current in visited:
                raise InvalidRegionHierarchy(
                    f"existing cycle in stored ancestor chain at {current!r}"
                )
            visited.add(current)
            depth += 1
            if depth > _MAX_ANCESTOR_DEPTH:
                raise InvalidRegionHierarchy(
                    f"ancestor chain exceeds depth limit at {region_id!r}"
                )
            ancestor = self._repo.get(current)
            if ancestor is None:
                raise InvalidRegionHierarchy(f"parent region {current!r} not found")
            current = ancestor.parent_region_id
