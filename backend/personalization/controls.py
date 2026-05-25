"""User-adjustable scoring controls for personalized overlays.

The weights here are user-owned overlay inputs. They do not change canonical
region scores or scoring rulesets.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ScoringWeightKey = Literal[
    "entry_level_access",
    "hiring_density",
    "prestige",
    "industry_fit",
    "role_fit",
]

SCORING_WEIGHT_KEYS: tuple[ScoringWeightKey, ...] = (
    "entry_level_access",
    "hiring_density",
    "prestige",
    "industry_fit",
    "role_fit",
)

DEFAULT_SCORING_WEIGHTS: dict[ScoringWeightKey, float] = {
    "entry_level_access": 0.30,
    "hiring_density": 0.25,
    "prestige": 0.15,
    "industry_fit": 0.15,
    "role_fit": 0.15,
}


class ScoringWeightsInput(BaseModel):
    """Transparent user-controlled overlay weights.

    Values are relative weights in ``[0, 1]``. They do not need to sum to
    ``1.0``; preview responses return normalized effective weights.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_level_access: float = Field(
        default=DEFAULT_SCORING_WEIGHTS["entry_level_access"],
        ge=0,
        le=1,
    )
    hiring_density: float = Field(default=DEFAULT_SCORING_WEIGHTS["hiring_density"], ge=0, le=1)
    prestige: float = Field(default=DEFAULT_SCORING_WEIGHTS["prestige"], ge=0, le=1)
    industry_fit: float = Field(default=DEFAULT_SCORING_WEIGHTS["industry_fit"], ge=0, le=1)
    role_fit: float = Field(default=DEFAULT_SCORING_WEIGHTS["role_fit"], ge=0, le=1)

    @model_validator(mode="after")
    def _weights_must_be_usable(self) -> ScoringWeightsInput:
        values = self.as_dict()
        if any(not math.isfinite(value) for value in values.values()):
            raise ValueError("scoring weights must be finite numbers")
        if sum(values.values()) <= 0:
            raise ValueError("at least one scoring weight must be greater than zero")
        return self

    def as_dict(self) -> dict[ScoringWeightKey, float]:
        return {key: float(getattr(self, key)) for key in SCORING_WEIGHT_KEYS}


def default_scoring_weights() -> ScoringWeightsInput:
    return ScoringWeightsInput(**DEFAULT_SCORING_WEIGHTS)


def coerce_scoring_weights(value: object | None) -> ScoringWeightsInput:
    if value is None:
        return default_scoring_weights()
    if isinstance(value, ScoringWeightsInput):
        return value
    if isinstance(value, Mapping):
        return ScoringWeightsInput(**dict(value))
    raise ValueError("scoring_weights must be an object")


def normalize_weights(
    weights: ScoringWeightsInput,
    *,
    available_components: set[ScoringWeightKey] | None = None,
) -> dict[ScoringWeightKey, float]:
    raw = weights.as_dict()
    if available_components is not None:
        raw = {
            key: value
            for key, value in raw.items()
            if key in available_components and value > 0
        }
    total = sum(raw.values())
    if total <= 0:
        return {key: 0.0 for key in SCORING_WEIGHT_KEYS}
    return {key: raw.get(key, 0.0) / total for key in SCORING_WEIGHT_KEYS}


def weighted_overlay_score(
    components: Mapping[ScoringWeightKey, float | None],
    weights: ScoringWeightsInput,
) -> tuple[float | None, dict[ScoringWeightKey, float]]:
    available = {
        key
        for key in SCORING_WEIGHT_KEYS
        if components.get(key) is not None and weights.as_dict()[key] > 0
    }
    if not available:
        return None, normalize_weights(weights, available_components=set())
    normalized = normalize_weights(weights, available_components=available)
    score = sum(
        normalized[key] * float(components[key])
        for key in available
        if components[key] is not None
    )
    return max(0.0, min(1.0, score)), normalized
