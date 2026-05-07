"""End-to-end MVP demo orchestrator (Slice 18).

:func:`run_seed` walks the deterministic dataset in :mod:`seeds.mvp_data`
through every documented MVP layer using the existing services:

1. geography — upsert seed regions
2. companies — upsert + classify
3. presence — upsert + decide presence basis
4. hiring — upsert hiring snapshots
5. entry-level — upsert entry-level snapshots
6. region scoring — recompute region market scores
7. region outputs — assemble + persist OutputMetadata
8. company outputs — assemble + persist OutputMetadata
9. comparison output — Boston vs SF
10. contextual challenge output — Boston vs SF

Idempotency: each upsert returns ``"created" | "updated" | "unchanged"``,
so a second run on the same DB produces no duplicate logical rows.

No external IO: this module imports only in-process services and the
read-side repositories already shipped by Slices 5–17.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.companies.repository import CompanyRepository
from backend.companies.service import CompanyService
from backend.entry_level.repository import EntryLevelRepository
from backend.entry_level.service import EntryLevelService
from backend.geography.repository import RegionRepository
from backend.geography.service import GeographyService
from backend.hiring.repository import HiringRepository
from backend.hiring.service import HiringService
from backend.outputs.contextual_challenge import ContextualChallengeService
from backend.outputs.repository import OutputMetadataRepository
from backend.outputs.service import OutputAssemblyService
from backend.presence.repository import PresenceRepository
from backend.presence.service import PresenceService
from backend.scoring.repository import RegionScoreRepository
from backend.scoring.service import RegionScoringService
from seeds.mvp_data import (
    COMPANIES,
    COMPARISON_PAIRS,
    ENTRY_LEVEL,
    HIRING,
    PRESENCE,
    REGIONS,
)


def _empty_counter() -> Counter:
    return Counter()


@dataclass(frozen=True)
class SeedResult:
    """Compact summary returned by :func:`run_seed`.

    Each :class:`Counter` records the upsert outcomes for its layer
    (``"created"`` / ``"updated"`` / ``"unchanged"``).
    """

    regions: Counter = field(default_factory=_empty_counter)
    companies: Counter = field(default_factory=_empty_counter)
    presence: Counter = field(default_factory=_empty_counter)
    hiring: Counter = field(default_factory=_empty_counter)
    entry_level: Counter = field(default_factory=_empty_counter)
    region_scores: Counter = field(default_factory=_empty_counter)
    region_outputs: Counter = field(default_factory=_empty_counter)
    company_outputs: Counter = field(default_factory=_empty_counter)
    comparison_outputs: Counter = field(default_factory=_empty_counter)
    contextual_outputs: Counter = field(default_factory=_empty_counter)

    def summary_lines(self) -> list[str]:
        def _line(label: str, counter: Counter) -> str:
            created = counter.get("created", 0)
            updated = counter.get("updated", 0)
            unchanged = counter.get("unchanged", 0)
            return (
                f"  {label:<22} "
                f"created={created} updated={updated} unchanged={unchanged}"
            )

        return [
            "MVP demo seed summary:",
            _line("regions", self.regions),
            _line("companies", self.companies),
            _line("presence", self.presence),
            _line("hiring", self.hiring),
            _line("entry_level", self.entry_level),
            _line("region_scores", self.region_scores),
            _line("region_outputs", self.region_outputs),
            _line("company_outputs", self.company_outputs),
            _line("comparison_outputs", self.comparison_outputs),
            _line("contextual_outputs", self.contextual_outputs),
        ]


def run_seed(session: Session) -> SeedResult:
    """Run the full MVP seed/demo pipeline against ``session``.

    The caller owns transaction lifecycle. ``run_seed`` flushes via the
    underlying repositories but does not commit. The CLI entrypoint in
    ``scripts/seed_demo.py`` wraps this in ``session_scope`` so commits
    happen at the boundary.
    """
    result = SeedResult()

    # 1) Regions ---------------------------------------------------------
    region_repo = RegionRepository(session)
    geography_service = GeographyService(region_repo)
    for definition in REGIONS:
        _, outcome = geography_service.upsert_for_build(definition)
        result.regions[outcome] += 1

    # 2) Companies -------------------------------------------------------
    company_repo = CompanyRepository(session)
    company_service = CompanyService(company_repo)
    for definition in COMPANIES:
        _, outcome = company_service.upsert_for_classify(definition)
        result.companies[outcome] += 1

    # 3) Presence --------------------------------------------------------
    presence_repo = PresenceRepository(session)
    presence_service = PresenceService(
        presence_repo, company_repo=company_repo, region_repo=region_repo
    )
    for definition in PRESENCE:
        _, outcome = presence_service.upsert_for_mapping(definition)
        result.presence[outcome] += 1

    # 4) Hiring ----------------------------------------------------------
    hiring_repo = HiringRepository(session)
    hiring_service = HiringService(hiring_repo, presence_repo=presence_repo)
    for definition in HIRING:
        _, outcome = hiring_service.upsert_for_refresh(definition)
        result.hiring[outcome] += 1

    # 5) Entry-level -----------------------------------------------------
    entry_level_repo = EntryLevelRepository(session)
    entry_level_service = EntryLevelService(
        entry_level_repo, hiring_repo=hiring_repo
    )
    for definition in ENTRY_LEVEL:
        _, outcome = entry_level_service.upsert_for_refresh(definition)
        result.entry_level[outcome] += 1

    # 6) Region scores ---------------------------------------------------
    score_repo = RegionScoreRepository(session)
    scoring_service = RegionScoringService(score_repo, region_repo=region_repo)
    for region_def in REGIONS:
        _, outcome = scoring_service.upsert_for_recompute(region_def.region_id)
        result.region_scores[outcome] += 1

    # 7-9) Output assembly ----------------------------------------------
    output_repo = OutputMetadataRepository(session)
    output_service = OutputAssemblyService(
        output_repo,
        session=session,
        region_repo=region_repo,
        company_repo=company_repo,
        presence_repo=presence_repo,
        hiring_repo=hiring_repo,
        entry_level_repo=entry_level_repo,
        score_repo=score_repo,
    )

    for region_def in REGIONS:
        region_result = output_service.build_region(region_def.region_id)
        result.region_outputs[region_result.action] += 1

    for company_def in COMPANIES:
        company_result = output_service.build_company(company_def.company_id)
        result.company_outputs[company_result.action] += 1

    for region_a, region_b in COMPARISON_PAIRS:
        comparison_result = output_service.build_comparison(region_a, region_b)
        result.comparison_outputs[comparison_result.action] += 1

    # 10) Contextual challenge ------------------------------------------
    contextual_service = ContextualChallengeService(
        output_repo,
        session=session,
        region_repo=region_repo,
        score_repo=score_repo,
    )
    for region_a, region_b in COMPARISON_PAIRS:
        contextual_result = contextual_service.build(region_a, region_b)
        result.contextual_outputs[contextual_result.action] += 1

    return result
