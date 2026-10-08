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
from backend.geography.resolver import GeographicResolver
from backend.hiring.models import CompanyRegionHiring
from backend.scoring.exceptions import (
    MissingRegionForScoring,
    RegionScoreNotFound,
)
from backend.scoring.models import RegionMarketScore
from backend.scoring.normalization import saturate
from backend.scoring.repository import RegionScoreRepository
from backend.scoring.rulesets import ScoringRuleset, default_ruleset
from backend.shared.state import ObjectState, validate_transition
from backend.shared.value_semantics import CountSemantics, aggregate_counts
from backend.shared.versioning import next_version

UpsertOutcome = Literal["created", "updated", "unchanged"]


# ---------------------------------------------------------------------------
# Per-component formula functions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LiveMarketInputs:
    currently_hiring_count: int
    active_postings: CountSemantics
    hiring_programs: CountSemantics


def _weighted_known_score(
    components: tuple[tuple[float, float | None], ...],
) -> float | None:
    known = [(weight, value) for weight, value in components if value is not None]
    if not known:
        return None
    known_weight = sum(weight for weight, _ in known)
    return sum(weight * value for weight, value in known) / known_weight


def prepare_live_market_inputs(
    hiring_records: list[CompanyRegionHiring],
) -> LiveMarketInputs:
    return LiveMarketInputs(
        currently_hiring_count=sum(
            1 for h in hiring_records if h.currently_hiring_flag
        ),
        active_postings=aggregate_counts(
            [h.active_posting_count_now for h in hiring_records]
        ),
        hiring_programs=aggregate_counts(
            [h.hiring_program_count for h in hiring_records]
        ),
    )


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
) -> float | None:
    """Live activity: actively-hiring company count, current postings,
    formal hiring program counts.

    Unknown count components are omitted from the weighted combination rather
    than treated as zero. A region with no hiring records has no live-market
    input and returns ``None``.
    """
    if not hiring_records:
        return None
    inputs = prepare_live_market_inputs(hiring_records)
    active_postings = inputs.active_postings.value
    hiring_programs = inputs.hiring_programs.value
    return _weighted_known_score(
        (
            (
                ruleset.w_live_hiring_count,
                saturate(
                    inputs.currently_hiring_count,
                    ruleset.cap_currently_hiring_count,
                ),
            ),
            (
                ruleset.w_live_postings,
                (
                    saturate(active_postings, ruleset.cap_total_active_postings)
                    if active_postings is not None
                    else None
                ),
            ),
            (
                ruleset.w_live_programs,
                (
                    saturate(hiring_programs, ruleset.cap_total_hiring_programs)
                    if hiring_programs is not None
                    else None
                ),
            ),
        )
    )


def compute_early_career_accessibility(
    entry_level_records: list[CompanyRegionEntryLevel],
    *,
    ruleset: ScoringRuleset,
) -> float | None:
    """Early-career region view, derived from stored
    ``entry_level_access_score`` values on
    :class:`CompanyRegionEntryLevel`.

    Reads stored values only — does not recompute Slice 9 scoring.
    Combines a saturation-capped count of pairs with non-zero access with
    the average access score across those pairs.
    """
    if not entry_level_records:
        return None
    known_scores = [
        r.entry_level_access_score
        for r in entry_level_records
        if r.entry_level_access_score is not None
    ]
    if not known_scores:
        return None
    nonzero = [score for score in known_scores if score > 0]
    if not nonzero:
        return 0.0
    count_factor = saturate(len(nonzero), ruleset.cap_entry_level_nonzero_pairs)
    avg_score = sum(nonzero) / len(nonzero)
    return count_factor * avg_score


def compute_prestige_aggregate(companies: list[Company]) -> tuple[float | None, bool]:
    """Average ``prestige_score`` across companies.

    Returns ``(score, is_partial)``. ``is_partial`` is True when no company
    had a non-null prestige score, signalling that the score is a documented
    fallback rather than confident truth.
    """
    scores = [c.prestige_score for c in companies if c.prestige_score is not None]
    if not scores:
        return None, True
    return sum(scores) / len(scores), False


def compute_objective_opportunity(
    *,
    early_career: float | None,
    live_market: float | None,
    prestige: float | None,
    ruleset: ScoringRuleset,
) -> float | None:
    """Objective opportunity = entry-level access (lead) + live market + prestige.

    Weights enforce: entry-level > live market > prestige, modestly. The
    ruleset's ``__post_init__`` rejects rulesets that violate the ordering.
    """
    return _weighted_known_score(
        (
            (ruleset.w_obj_entry_level, early_career),
            (ruleset.w_obj_live_market, live_market),
            (ruleset.w_obj_prestige, prestige),
        )
    )


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegionScoreComputation:
    region_id: str
    structural_ecosystem_score: float
    live_market_score: float | None
    objective_opportunity_score: float | None
    raw_total_score: float | None
    general_density_score: float | None
    tech_market_density_score: float | None
    early_career_accessibility_score: float | None
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
        resolution = GeographicResolver(self._region_repo).resolve(region_id)
        if resolution.resolved and resolution.region_id is not None:
            region_id = resolution.region_id
        row = self._score_repo.get_score_by_region(region_id)
        if row is None:
            raise RegionScoreNotFound(region_id)
        return row

    def list_scores(self) -> list[RegionMarketScore]:
        return self._score_repo.list_scores()

    # --- compute (no DB writes) ------------------------------------------

    def compute_scores(self, region_id: str) -> RegionScoreComputation:
        resolution = GeographicResolver(self._region_repo).resolve(region_id)
        if resolution.resolved and resolution.region_id is not None:
            region_id = resolution.region_id
        if not self._region_repo.exists(region_id):
            raise MissingRegionForScoring(region_id)

        companies = self._score_repo.list_present_companies_for_region(region_id)
        hiring_records = self._score_repo.list_hiring_for_region(region_id)
        entry_level_records = self._score_repo.list_entry_level_for_region(region_id)

        warnings: list[str] = []
        partial = False

        # Per-component aggregates
        structural = compute_structural_ecosystem(companies, ruleset=self._ruleset)
        live_inputs = prepare_live_market_inputs(hiring_records)
        live_market = compute_live_market(hiring_records, ruleset=self._ruleset)
        early_career = compute_early_career_accessibility(
            entry_level_records, ruleset=self._ruleset
        )
        prestige_avg, prestige_partial = compute_prestige_aggregate(companies)
        if prestige_partial and companies:
            partial = True
            warnings.append(
                "no companies in region carry prestige_score; prestige aggregate is unknown"
            )
        if live_market is None:
            partial = True
            warnings.append("hiring counts not collected; live_market_score is unknown")
        elif not (
            live_inputs.active_postings.has_current_observed_value
            and live_inputs.hiring_programs.has_current_observed_value
        ):
            partial = True
            warnings.append(
                "one or more live-market count inputs are unknown and were not "
                "treated as zero"
            )
        if early_career is None:
            partial = True
            warnings.append(
                "entry-level score inputs not collected; "
                "early_career_accessibility_score is unknown"
            )
        elif any(
            row.entry_level_access_score is None for row in entry_level_records
        ):
            partial = True
            warnings.append(
                "one or more entry-level score inputs are unknown and were not "
                "treated as zero"
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
        total_active_postings = (
            sum(
                h.active_posting_count_now
                for h in hiring_records
                if h.active_posting_count_now is not None
            )
            if live_inputs.active_postings.has_current_observed_value
            else None
        )
        major_tech_company_ids = {
            c.company_id for c in companies if c.is_major_tech
        }
        major_tech_posting_semantics = aggregate_counts(
            [
                h.active_posting_count_now
                for h in hiring_records
                if h.company_id in major_tech_company_ids
            ]
        )
        major_tech_active_postings = (
            major_tech_posting_semantics.value
            if major_tech_posting_semantics.has_current_observed_value
            else None
        )

        general_density = _weighted_known_score(
            (
                (
                    0.5,
                    saturate(
                        eligible_count,
                        self._ruleset.cap_density_eligible_count,
                    ),
                ),
                (
                    0.5,
                    (
                        saturate(
                            total_active_postings,
                            self._ruleset.cap_density_total_postings,
                        )
                        if total_active_postings is not None
                        else None
                    ),
                ),
            )
        )
        tech_density = _weighted_known_score(
            (
                (
                    0.5,
                    saturate(
                        len(major_tech_company_ids),
                        self._ruleset.cap_tech_major_companies,
                    ),
                ),
                (
                    0.5,
                    (
                        saturate(
                            major_tech_active_postings,
                            self._ruleset.cap_tech_major_postings,
                        )
                        if major_tech_active_postings is not None
                        else None
                    ),
                ),
            )
        )

        raw_total = _weighted_known_score(
            (
                (self._ruleset.w_raw_structural, structural),
                (self._ruleset.w_raw_live, live_market),
                (self._ruleset.w_raw_objective, objective),
            )
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
                "active_posting_count_status": live_inputs.active_postings.status.value,
                "hiring_program_count_status": live_inputs.hiring_programs.status.value,
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
        region_id = computation.region_id

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
