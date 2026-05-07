"""Invalidation vocabulary for Slice 15.

Source: ``EVENT_TRIGGER_MAP.md`` §3 (per-trigger ``Invalidate``) and
``JOB_ORCHESTRATION_MATRIX.md`` §6 (invalidation tiers).

Slice 15 *recommends* invalidation; it does not mutate any rows itself. The
:class:`InvalidationTarget` enum names the kinds of objects an event can
flag for rebuild, and :class:`InvalidationDirective` carries the scope.

These targets cover MVP V1 only:

* ``region_score``        — entry in ``region_market_scores`` for one region
* ``region_output``       — derived region output object
* ``company_output``      — derived company output object
* ``comparison_output``   — comparison cache entry for one region pair
* ``hiring_refresh``      — flag a (company, region) hiring record stale
* ``entry_level_refresh`` — flag a (company, region) entry-level record stale
* ``presence_mapping``    — flag a (company, region) presence record stale
* ``company_classification`` — flag a company's classification stale

Audit / contextual challenge / personalization targets are intentionally
absent. They belong to later slices.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InvalidationTarget(StrEnum):
    REGION_SCORE = "region_score"
    REGION_OUTPUT = "region_output"
    COMPANY_OUTPUT = "company_output"
    COMPARISON_OUTPUT = "comparison_output"
    HIRING_REFRESH = "hiring_refresh"
    ENTRY_LEVEL_REFRESH = "entry_level_refresh"
    PRESENCE_MAPPING = "presence_mapping"
    COMPANY_CLASSIFICATION = "company_classification"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class InvalidationDirective(BaseModel):
    """A single, scoped invalidation recommendation.

    ``scope`` is a structured pointer at the affected object(s). Examples:

    * ``{"region_id": "greater_boston"}``
    * ``{"company_id": "comp_101", "region_id": "greater_boston"}``
    * ``{"comparison_id": "greater_boston__greater_sf"}``

    ``reason`` is a short string for traceability — surfaced back to the
    caller alongside the recommendation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: InvalidationTarget
    scope: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=1)
