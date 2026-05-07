"""Scoring weights, caps, and version bundling.

The :class:`ScoringRuleset` carries every knob the formulas need:

* component weights for the *objective opportunity*, *structural ecosystem*,
  and *live market* aggregates;
* the raw-total weights that combine the three top-level aggregates;
* saturation caps that turn unbounded counts into a documented ``[0, 1]``
  scale before weighting.

Everything is overridable at service construction so tests can swap a
ruleset without touching code. The MVP default (:data:`DEFAULT_RULESET`)
honors the documented hierarchy:

* objective opportunity weights — entry-level access leads (40%), current
  hiring volume next (35%), prestige third (25%). Entry-level access leads
  *modestly* — only 5pp above the next factor.
* structural ecosystem weights — eligible density (40%), major-tech density
  (35%), Mag 7 density (25%).
* live market weights — actively-hiring company count (40%), aggregate
  current postings (35%), formal hiring program count (25%).
* raw total combines the three aggregates with a slight emphasis on
  objective opportunity (40%) over structural (30%) and live (30%).

These numbers are intentionally boring and audit-friendly. They are *not*
the final scoring engine — they are the deterministic placeholder that
Slice 11 (output assembly) and the audit slice can read without surprise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from backend.scoring.exceptions import InvalidRuleset
from backend.scoring.types import DEFAULT_SCORE_RULESET_VERSION


@dataclass(frozen=True, slots=True)
class ScoringRuleset:
    version: str

    # Objective opportunity (entry-level leads modestly)
    w_obj_entry_level: float
    w_obj_live_market: float
    w_obj_prestige: float

    # Structural ecosystem
    w_struct_eligible: float
    w_struct_major_tech: float
    w_struct_mag7: float

    # Live market
    w_live_hiring_count: float
    w_live_postings: float
    w_live_programs: float

    # Raw total (combines the three top-level aggregates)
    w_raw_structural: float
    w_raw_live: float
    w_raw_objective: float

    # Saturation caps
    cap_eligible_count: int
    cap_major_tech_count: int
    cap_mag7_count: int
    cap_currently_hiring_count: int
    cap_total_active_postings: int
    cap_total_hiring_programs: int
    cap_entry_level_nonzero_pairs: int
    cap_density_eligible_count: int
    cap_density_total_postings: int
    cap_tech_major_companies: int
    cap_tech_major_postings: int

    def __post_init__(self) -> None:
        # Each weight bundle should sum approximately to 1.0 so callers can
        # reason about the [0, 1] output range. Allow a small float tolerance.
        self._must_sum_to_one(
            "objective opportunity weights",
            (self.w_obj_entry_level, self.w_obj_live_market, self.w_obj_prestige),
        )
        self._must_sum_to_one(
            "structural ecosystem weights",
            (self.w_struct_eligible, self.w_struct_major_tech, self.w_struct_mag7),
        )
        self._must_sum_to_one(
            "live market weights",
            (self.w_live_hiring_count, self.w_live_postings, self.w_live_programs),
        )
        self._must_sum_to_one(
            "raw total weights",
            (self.w_raw_structural, self.w_raw_live, self.w_raw_objective),
        )
        self._enforce_objective_hierarchy()
        self._enforce_positive_caps()

    @staticmethod
    def _must_sum_to_one(label: str, weights: tuple[float, ...]) -> None:
        total = sum(weights)
        if not math.isclose(total, 1.0, abs_tol=1e-9):
            raise InvalidRuleset(f"{label} must sum to 1.0; got {total}")
        for w in weights:
            if w < 0 or w > 1:
                raise InvalidRuleset(f"{label} contains weight outside [0, 1]: {w}")

    def _enforce_objective_hierarchy(self) -> None:
        """Entry-level access must lead, current hiring next, prestige last.
        The lead must be strictly positive (no ties) but moderate in spirit;
        we don't pin a precise gap, only the ordering.
        """
        if not (
            self.w_obj_entry_level > self.w_obj_live_market > self.w_obj_prestige
        ):
            raise InvalidRuleset(
                "objective opportunity weights must satisfy "
                "entry_level > live_market > prestige"
            )

    def _enforce_positive_caps(self) -> None:
        for name, value in (
            ("cap_eligible_count", self.cap_eligible_count),
            ("cap_major_tech_count", self.cap_major_tech_count),
            ("cap_mag7_count", self.cap_mag7_count),
            ("cap_currently_hiring_count", self.cap_currently_hiring_count),
            ("cap_total_active_postings", self.cap_total_active_postings),
            ("cap_total_hiring_programs", self.cap_total_hiring_programs),
            (
                "cap_entry_level_nonzero_pairs",
                self.cap_entry_level_nonzero_pairs,
            ),
            ("cap_density_eligible_count", self.cap_density_eligible_count),
            ("cap_density_total_postings", self.cap_density_total_postings),
            ("cap_tech_major_companies", self.cap_tech_major_companies),
            ("cap_tech_major_postings", self.cap_tech_major_postings),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise InvalidRuleset(f"{name} must be a positive int, got {value!r}")


DEFAULT_RULESET: ScoringRuleset = ScoringRuleset(
    version=DEFAULT_SCORE_RULESET_VERSION,
    # Objective opportunity (entry-level leads modestly)
    w_obj_entry_level=0.40,
    w_obj_live_market=0.35,
    w_obj_prestige=0.25,
    # Structural ecosystem
    w_struct_eligible=0.40,
    w_struct_major_tech=0.35,
    w_struct_mag7=0.25,
    # Live market
    w_live_hiring_count=0.40,
    w_live_postings=0.35,
    w_live_programs=0.25,
    # Raw total
    w_raw_structural=0.30,
    w_raw_live=0.30,
    w_raw_objective=0.40,
    # Saturation caps
    cap_eligible_count=50,
    cap_major_tech_count=10,
    cap_mag7_count=5,
    cap_currently_hiring_count=20,
    cap_total_active_postings=300,
    cap_total_hiring_programs=20,
    cap_entry_level_nonzero_pairs=10,
    cap_density_eligible_count=100,
    cap_density_total_postings=1000,
    cap_tech_major_companies=30,
    cap_tech_major_postings=300,
)


def default_ruleset() -> ScoringRuleset:
    return DEFAULT_RULESET
