"""Region scoring service.

Reads canonical truth (regions, companies, presence, hiring, entry-level)
through :class:`RegionScoreRepository` and writes only ``RegionMarketScore``
rows. Owns:

* per-component formula functions exposed at module level for testability;
* :class:`RegionScoreComputation` — the immutable result of a single
  region's recompute;
* :class:`RegionScoringService` — orchestrates a full recompute including
  state-machine transitions matching Slices 5–9.

Upstream domain *services* (``companies.service`` / ``presence.service`` /
``hiring.service`` / ``entry_level.service``) are deliberately not imported
— scoring reads stored truth through the repository, never re-runs upstream
rule evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.repository import RegionRepository
from backend.hiring.models import CompanyRegionHiring
from backend.scoring.exceptions import (
    MissingRegionForScoring,
    RegionScoreNotFound,
)
from backend.scoring.models import RegionMarketScore
from backend.scoring.normalization import (
    general_density_score,
    raw_total_score,
    saturate,
    tech_market_density_score,
)
from backend.scoring.repository import RegionScoreRepository
from backend.scoring.rulesets import ScoringRuleset, default_ruleset
from backend.shared.state import ObjectState, validate_transition
from backend.shared.versioning import next_version

UpsertOutcome = Literal["created", "updated", "unchanged"]


# ---------------------------------------------------------------------------
# Per-component formula functions
# ---------------------------------------------------------------------------


def compute_structural_ecosystem(
    companies: list[Company], *, ruleset: ScoringRuleset
) -> float:
    """Structural breadth: eligible / major-tech / Mag 7 density.

    Reflects the *static* market structure — who exists in the region — and
    is intentionally insensitive to current hiring activity. Inputs come
    from companies that are already presence='present' for the region.
    """
    eligible_count = sum(1 for c in companies if c.eligibility_status == "eligible")
    major_tech_count = sum(1 for c in companies if c.is_major_tech)
    mag7_count = sum(1 for c in companies if c.is_mag7)
    eligible = saturate(eligible_count, ruleset.cap_eligible_count)
    major_tech = saturate(major_tech_count, ruleset.cap_major_tech_count)
    mag7 = saturate(mag7_count, ruleset.cap_mag7_count)
    return (
        ruleset.w_struct_eligible * eligible
        + ruleset.w_struct_major_tech * major_tech
        + ruleset.w_struct_mag7 * mag7
    )


def compute_live_market(
    hiring_records: list[CompanyRegionHiring], *, ruleset: ScoringRuleset
) -> float:
    """Live activity: actively-hiring company count, current postings,
    formal hiring program counts.

    Treats unknown counts (``None``) as 0 only after at least one record
    establishes that hiring is being tracked. The score reflects current
    activity only — no personalization, no entry-level extraction.
    """
    currently_hiring_count = sum(
        1 for h in hiring_records if h.currently_hiring_flag
    )
    total_active_postings = sum(
        (h.active_posting_count_now or 0) for h in hiring_records
    )
    total_hiring_programs = sum(
        (h.hiring_program_count or 0) for h in hiring_records
    )
    return (
        ruleset.w_live_hiring_count
        * saturate(currently_hiring_count, ruleset.cap_currently_hiring_count)
        + ruleset.w_live_postings
        * saturate(total_active_postings, ruleset.cap_total_active_postings)
        + ruleset.w_live_programs
        * saturate(total_hiring_programs, ruleset.cap_total_hiring_programs)
    )


def compute_early_career_accessibility(
    entry_level_records: list[CompanyRegionEntryLevel],
    *,
    ruleset: ScoringRuleset,
) -> float:
    """Early-career region view, derived from stored
    ``entry_level_access_score`` values on
    :class:`CompanyRegionEntryLevel`.

    Reads stored values only — does not recompute Slice 9 scoring.
    Combines a saturation-capped count of pairs with non-zero access with
    the average access score across those pairs.
    """
    nonzero = [
        r.entry_level_access_score
        for r in entry_level_records
        if r.entry_level_access_score is not None and r.entry_level_access_score > 0
    ]
    if not nonzero:
        return 0.0
    count_factor = saturate(len(nonzero), ruleset.cap_entry_level_nonzero_pairs)
    avg_score = sum(nonzero) / len(nonzero)
    return count_factor * avg_score


def compute_prestige_aggregate(companies: list[Company]) -> tuple[float, bool]:
    """Average ``prestige_score`` across companies.

    Returns ``(score, is_partial)``. ``is_partial`` is True when no company
    had a non-null prestige score, signalling that the score is a documented
    fallback rather than confident truth.
    """
    scores = [c.prestige_score for c in companies if c.prestige_score is not None]
    if not scores:
        return 0.0, True
    return sum(scores) / len(scores), False


def compute_objective_opportunity(
    *,
    early_career: float,
    live_market: float,
    prestige: float,
    ruleset: ScoringRuleset,
) -> float:
    """Objective opportunity = entry-level access (lead) + live market + prestige.

    Weights enforce: entry-level > live market > prestige, modestly. The
    ruleset's ``__post_init__`` rejects rulesets that violate the ordering.
    """
    return (
        ruleset.w_obj_entry_level * early_career
        + ruleset.w_obj_live_market * live_market
        + ruleset.w_obj_prestige * prestige
    )


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegionScoreComputation:
    region_id: str
    structural_ecosystem_score: float
    live_market_score: float
    objective_opportunity_score: float
    raw_total_score: float
    general_density_score: float
    tech_market_density_score: float
    early_career_accessibility_score: float
    score_ruleset_version: str
    source_version_bundle: dict
    partial: bool
    warnings: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RegionScoringService:
    def __init__(
        self,
        score_repo: RegionScoreRepository,
        *,
        region_repo: RegionRepository,
        ruleset: ScoringRuleset | None = None,
    ) -> None:
        self._score_repo = score_repo
        self._region_repo = region_repo
        self._ruleset = ruleset or default_ruleset()

    # --- reads -----------------------------------------------------------

    def get_score(self, region_score_id: str) -> RegionMarketScore:
        row = self._score_repo.get_score(region_score_id)
        if row is None:
            raise RegionScoreNotFound(region_score_id)
        return row

    def get_score_by_region(self, region_id: str) -> RegionMarketScore:
        row = self._score_repo.get_score_by_region(region_id)
        if row is None:
            raise RegionScoreNotFound(region_id)
        return row

    def list_scores(self) -> list[RegionMarketScore]:
        return self._score_repo.list_scores()

    # --- compute (no DB writes) ------------------------------------------

    def compute_scores(self, region_id: str) -> RegionScoreComputation:
        if not self._region_repo.exists(region_id):
            raise MissingRegionForScoring(region_id)

        companies = self._score_repo.list_present_companies_for_region(region_id)
        hiring_records = self._score_repo.list_hiring_for_region(region_id)
        entry_level_records = self._score_repo.list_entry_level_for_region(region_id)

        warnings: list[str] = []
        partial = False

        # Per-component aggregates
        structural = compute_structural_ecosystem(companies, ruleset=self._ruleset)
        live_market = compute_live_market(hiring_records, ruleset=self._ruleset)
        early_career = compute_early_career_accessibility(
            entry_level_records, ruleset=self._ruleset
        )
        prestige_avg, prestige_partial = compute_prestige_aggregate(companies)
        if prestige_partial and companies:
            partial = True
            warnings.append(
                "no companies in region carry prestige_score; prestige aggregate "
                "fell back to 0.0"
            )

        objective = compute_objective_opportunity(
            early_career=early_career,
            live_market=live_market,
            prestige=prestige_avg,
            ruleset=self._ruleset,
        )

        # Density views — separate from raw component scores per DATA_MODEL §8.
        eligible_count = sum(
            1 for c in companies if c.eligibility_status == "eligible"
        )
        total_active_postings = sum(
            (h.active_posting_count_now or 0) for h in hiring_records
        )
        major_tech_company_ids = {
            c.company_id for c in companies if c.is_major_tech
        }
        major_tech_active_postings = sum(
            (h.active_posting_count_now or 0)
            for h in hiring_records
            if h.company_id in major_tech_company_ids
        )

        general_density = general_density_score(
            eligible_count=eligible_count,
            total_active_postings=total_active_postings,
            cap_eligible=self._ruleset.cap_density_eligible_count,
            cap_postings=self._ruleset.cap_density_total_postings,
        )
        tech_density = tech_market_density_score(
            major_tech_company_count=len(major_tech_company_ids),
            major_tech_active_postings=major_tech_active_postings,
            cap_major_companies=self._ruleset.cap_tech_major_companies,
            cap_major_postings=self._ruleset.cap_tech_major_postings,
        )

        raw_total = raw_total_score(
            structural_ecosystem=structural,
            live_market=live_market,
            objective_opportunity=objective,
            w_structural=self._ruleset.w_raw_structural,
            w_live=self._ruleset.w_raw_live,
            w_objective=self._ruleset.w_raw_objective,
        )

        if not companies:
            partial = True
            warnings.append("no present companies for region; scores are minimal")

        return RegionScoreComputation(
            region_id=region_id,
            structural_ecosystem_score=structural,
            live_market_score=live_market,
            objective_opportunity_score=objective,
            raw_total_score=raw_total,
            general_density_score=general_density,
            tech_market_density_score=tech_density,
            early_career_accessibility_score=early_career,
            score_ruleset_version=self._ruleset.version,
            source_version_bundle={
                "ruleset_version": self._ruleset.version,
                "present_company_count": len(companies),
                "hiring_record_count": len(hiring_records),
                "entry_level_record_count": len(entry_level_records),
            },
            partial=partial,
            warnings=tuple(warnings),
        )

    # --- writes ----------------------------------------------------------

    def upsert_for_recompute(
        self, region_id: str, *, region_score_id: str | None = None
    ) -> tuple[RegionMarketScore, UpsertOutcome]:
        """Idempotent recompute keyed on ``region_id``.

        Mirrors Slice 5–9 state-machine flow. ``"unchanged"`` is returned
        when every score column matches the stored row (the
        ``source_version_bundle`` and warnings are intentionally excluded
        from the comparison — they describe the run, not the result).
        """
        computation = self.compute_scores(region_id)

        existing = self._score_repo.get_score_by_region(region_id)
        if existing is None:
            row = RegionMarketScore(
                region_score_id=region_score_id or f"rms_{region_id}",
                region_id=region_id,
            )
            self._apply_computation(row, computation)
            self._score_repo.add_score(row)
            self._score_repo.flush()
            self._set_state(row, ObjectState.BUILDING)
            self._set_state(row, ObjectState.FRESH)
            self._score_repo.flush()
            return row, "created"

        if self._is_unchanged(existing, computation):
            return existing, "unchanged"

        self._apply_computation(existing, computation)
        existing.version = next_version(existing.version)
        if existing.state == ObjectState.NEW.value:
            self._set_state(existing, ObjectState.BUILDING)
            self._set_state(existing, ObjectState.FRESH)
        elif existing.state == ObjectState.BUILDING.value:
            self._set_state(existing, ObjectState.FRESH)
        self._score_repo.flush()
        return existing, "updated"

    # --- internals -------------------------------------------------------

    def _apply_computation(
        self, row: RegionMarketScore, computation: RegionScoreComputation
    ) -> None:
        row.structural_ecosystem_score = computation.structural_ecosystem_score
        row.live_market_score = computation.live_market_score
        row.objective_opportunity_score = computation.objective_opportunity_score
        row.raw_total_score = computation.raw_total_score
        row.general_density_score = computation.general_density_score
        row.tech_market_density_score = computation.tech_market_density_score
        row.early_career_accessibility_score = (
            computation.early_career_accessibility_score
        )
        row.score_ruleset_version = computation.score_ruleset_version
        row.source_version_bundle = computation.source_version_bundle

    def _set_state(self, row: RegionMarketScore, target: ObjectState) -> None:
        validate_transition(row.state, target)
        row.state = target.value

    def _is_unchanged(
        self,
        row: RegionMarketScore,
        computation: RegionScoreComputation,
    ) -> bool:
        return (
            row.structural_ecosystem_score == computation.structural_ecosystem_score
            and row.live_market_score == computation.live_market_score
            and row.objective_opportunity_score
            == computation.objective_opportunity_score
            and row.raw_total_score == computation.raw_total_score
            and row.general_density_score == computation.general_density_score
            and row.tech_market_density_score == computation.tech_market_density_score
            and row.early_career_accessibility_score
            == computation.early_career_accessibility_score
            and row.score_ruleset_version == computation.score_ruleset_version
        )
