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
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.companies.repository import CompanyRepository
from backend.companies.service import CompanyService
from backend.current_opportunities.adapters import StaticOpportunityAdapter
from backend.current_opportunities.repository import CurrentOpportunityRepository
from backend.current_opportunities.service import CurrentOpportunityService
from backend.entry_level.repository import EntryLevelRepository
from backend.entry_level.service import EntryLevelService
from backend.geography.catalog import apply_curated_geography, load_curated_geographies
from backend.geography.repository import RegionRepository
from backend.geography.service import GeographyService, RegionDefinition
from backend.hiring.repository import HiringRepository
from backend.hiring.service import HiringService
from backend.outputs.contextual_challenge import ContextualChallengeService
from backend.outputs.repository import OutputMetadataRepository
from backend.outputs.service import OutputAssemblyService
from backend.presence.repository import PresenceRepository
from backend.presence.service import PresenceService
from backend.provenance.repository import ProvenanceRepository
from backend.provenance.service import (
    FactSourceLinkDefinition,
    ProvenanceService,
    SourceObservationDefinition,
    SourceRefDefinition,
)
from backend.scoring.repository import RegionScoreRepository
from backend.scoring.service import RegionScoringService
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    DataOrigin,
    FactBindingType,
    LicenseTermsCategory,
    ObservationStatus,
    SourceType,
)
from seeds.mvp_data import (
    COMPANIES,
    COMPARISON_PAIRS,
    ENTRY_LEVEL,
    HIRING,
    PRESENCE,
    REGIONS,
)
from seeds.opportunity_data import (
    CORE_MARKET_IDS,
    CURRENT_OPPORTUNITY_SOURCE,
    DEMO_CORE_RUN_ID,
    DemoOpportunityScenario,
    closed_opportunity_records,
    core_scenarios,
    current_opportunity_coverage,
    current_opportunity_records,
    demo_observed_at,
    marketplace_opportunities,
)

_DEMO_SOURCE_ID = "mvp_demo_seed"
_DEMO_OBSERVATION_ID = "mvp_demo_seed_observation"
_DEMO_OBSERVED_AT = datetime(2026, 5, 20, tzinfo=UTC)
_DEMO_NOTES = (
    "MVP demo seed dataset; synthetic_or_curated_demo; "
    "not factual public market coverage."
)


def _empty_counter() -> Counter:
    return Counter()


@dataclass(frozen=True)
class SeedResult:
    """Compact summary returned by :func:`run_seed`.

    Each :class:`Counter` records processed upsert operations for its layer
    (``"created"`` / ``"updated"`` / ``"unchanged"``), not final stored-row
    totals. A logical scenario can be processed by more than one seed pass.
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
    marketplace_opportunities: Counter = field(default_factory=_empty_counter)
    current_opportunity_sources: Counter = field(default_factory=_empty_counter)
    current_opportunity_coverage: Counter = field(default_factory=_empty_counter)
    current_opportunities: Counter = field(default_factory=_empty_counter)

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
            _line("marketplace_opp_upserts", self.marketplace_opportunities),
            _line("current_opp_sources", self.current_opportunity_sources),
            _line("current_opp_coverage", self.current_opportunity_coverage),
            _line("current_opp_upserts", self.current_opportunities),
        ]


def run_seed(session: Session, *, demo_now: datetime | None = None) -> SeedResult:
    """Run the full MVP seed/demo pipeline against ``session``.

    The caller owns transaction lifecycle. ``run_seed`` flushes via the
    underlying repositories but does not commit. The CLI entrypoint in
    ``scripts/seed_demo.py`` wraps this in ``session_scope`` so commits
    happen at the boundary.
    """
    result = SeedResult()
    provenance_service = ProvenanceService(ProvenanceRepository(session))
    demo_observation_id = _ensure_demo_provenance(provenance_service)

    # 1) Regions ---------------------------------------------------------
    region_repo = RegionRepository(session)
    geography_service = GeographyService(region_repo)
    for definition in REGIONS:
        region, outcome = geography_service.upsert_for_build(
            _with_curated_geography(definition)
        )
        apply_curated_geography(region_repo, region.region_id)
        result.regions[outcome] += 1
        _link_demo_fact(
            provenance_service,
            observation_id=demo_observation_id,
            fact_type=FactBindingType.REGION,
            fact_id=region.region_id,
        )

    # 2) Companies -------------------------------------------------------
    company_repo = CompanyRepository(session)
    company_service = CompanyService(company_repo)
    for definition in COMPANIES:
        company, outcome = company_service.upsert_for_classify(definition)
        result.companies[outcome] += 1
        _link_demo_fact(
            provenance_service,
            observation_id=demo_observation_id,
            fact_type=FactBindingType.COMPANY,
            fact_id=company.company_id,
        )

    # 3) Presence --------------------------------------------------------
    presence_repo = PresenceRepository(session)
    presence_service = PresenceService(
        presence_repo, company_repo=company_repo, region_repo=region_repo
    )
    for definition in PRESENCE:
        presence, outcome = presence_service.upsert_for_mapping(definition)
        result.presence[outcome] += 1
        _link_demo_fact(
            provenance_service,
            observation_id=demo_observation_id,
            fact_type=FactBindingType.COMPANY_REGION_PRESENCE,
            fact_id=presence.presence_id,
        )

    # 4) Hiring ----------------------------------------------------------
    hiring_repo = HiringRepository(session)
    hiring_service = HiringService(hiring_repo, presence_repo=presence_repo)
    for definition in HIRING:
        hiring, outcome = hiring_service.upsert_for_refresh(definition)
        result.hiring[outcome] += 1
        _link_demo_fact(
            provenance_service,
            observation_id=demo_observation_id,
            fact_type=FactBindingType.COMPANY_REGION_HIRING,
            fact_id=hiring.hiring_id,
        )

    # 5) Entry-level -----------------------------------------------------
    entry_level_repo = EntryLevelRepository(session)
    entry_level_service = EntryLevelService(
        entry_level_repo, hiring_repo=hiring_repo
    )
    for definition in ENTRY_LEVEL:
        entry_level, outcome = entry_level_service.upsert_for_refresh(definition)
        result.entry_level[outcome] += 1
        _link_demo_fact(
            provenance_service,
            observation_id=demo_observation_id,
            fact_type=FactBindingType.COMPANY_REGION_ENTRY_LEVEL,
            fact_id=entry_level.entry_level_id,
        )

    # 6) Region scores ---------------------------------------------------
    score_repo = RegionScoreRepository(session)
    scoring_service = RegionScoringService(score_repo, region_repo=region_repo)
    for region_def in REGIONS:
        score, outcome = scoring_service.upsert_for_recompute(region_def.region_id)
        result.region_scores[outcome] += 1
        _link_demo_fact(
            provenance_service,
            observation_id=demo_observation_id,
            fact_type=FactBindingType.SCORE_INPUT,
            fact_id=score.region_score_id,
        )

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

    # 11) Representative opportunity inventory -------------------------
    seed_opportunity_scenarios(
        session,
        result,
        scenarios=core_scenarios(),
        market_ids=CORE_MARKET_IDS,
        run_id=DEMO_CORE_RUN_ID,
        observed_at=demo_observed_at(demo_now),
    )

    return result


def seed_opportunity_scenarios(
    session: Session,
    result: SeedResult,
    *,
    scenarios: tuple[DemoOpportunityScenario, ...],
    market_ids: set[str] | frozenset[str],
    run_id: str,
    observed_at: datetime,
) -> None:
    """Seed shared scenarios through both existing opportunity domain services."""

    _seed_marketplace_opportunities(
        session,
        result,
        definitions=marketplace_opportunities(scenarios, observed_at=observed_at),
    )
    _seed_current_opportunities(
        session,
        result,
        scenarios=scenarios,
        market_ids=market_ids,
        run_id=run_id,
        observed_at=observed_at,
    )


def _seed_marketplace_opportunities(
    session: Session,
    result: SeedResult,
    *,
    definitions: tuple,
) -> None:
    # Load the data-standards package before the marketplace service so its
    # existing trust-adapter import cycle is initialized in the same order as
    # the FastAPI application.
    import backend.data_standards  # noqa: F401, PLC0415
    from backend.opportunities.repository import OpportunityRepository  # noqa: PLC0415
    from backend.opportunities.service import OpportunityService  # noqa: PLC0415

    repository = OpportunityRepository(session)
    service = OpportunityService(repository)
    for definition in definitions:
        assert definition.opportunity_id is not None
        if repository.get_opportunity(definition.opportunity_id) is not None:
            result.marketplace_opportunities["unchanged"] += 1
            continue
        service.create_opportunity(definition)
        result.marketplace_opportunities["created"] += 1


def _seed_current_opportunities(
    session: Session,
    result: SeedResult,
    *,
    scenarios: tuple[DemoOpportunityScenario, ...],
    market_ids: set[str] | frozenset[str],
    run_id: str,
    observed_at: datetime,
) -> None:
    repository = CurrentOpportunityRepository(session)
    service = CurrentOpportunityService(repository)

    source_exists = repository.get_source(CURRENT_OPPORTUNITY_SOURCE.source_id) is not None
    service.upsert_source(CURRENT_OPPORTUNITY_SOURCE)
    result.current_opportunity_sources[
        "unchanged" if source_exists else "created"
    ] += 1

    coverage_definitions = current_opportunity_coverage(
        market_ids,
        evaluated_at=observed_at,
    )
    for definition in coverage_definitions:
        coverage_exists = repository.get_coverage(
            market_key=definition.market_key,
            role_family=definition.role_family,
            opportunity_type=(
                definition.opportunity_type.value
                if hasattr(definition.opportunity_type, "value")
                else str(definition.opportunity_type)
            ),
        ) is not None
        service.upsert_coverage(definition)
        result.current_opportunity_coverage[
            "unchanged" if coverage_exists else "created"
        ] += 1

    records = current_opportunity_records(scenarios, observed_at=observed_at)
    run_exists = repository.get_run_by_idempotency_key(run_id) is not None
    run = service.refresh_source(
        StaticOpportunityAdapter(
            source_id=CURRENT_OPPORTUNITY_SOURCE.source_id,
            records=records,
            collected_at=observed_at,
            warnings=(
                "Synthetic demonstration records; not real or comprehensive openings.",
            ),
        ),
        run_id=run_id,
        idempotency_key=run_id,
        trigger_type="demo_seed",
        requested_by="scripts.seed_demo",
        now=observed_at,
    )
    if run_exists:
        result.current_opportunities["unchanged"] += len(records)
    else:
        result.current_opportunities["created"] += run.promoted_count


def close_opportunity_scenarios(
    session: Session,
    result: SeedResult,
    *,
    scenarios: tuple[DemoOpportunityScenario, ...],
    run_id: str,
    observed_at: datetime,
) -> None:
    """Close designated scenarios through the governed removal-observation path."""

    records = closed_opportunity_records(scenarios, observed_at=observed_at)
    if not records:
        return
    repository = CurrentOpportunityRepository(session)
    service = CurrentOpportunityService(repository)
    run_exists = repository.get_run_by_idempotency_key(run_id) is not None
    run = service.refresh_source(
        StaticOpportunityAdapter(
            source_id=CURRENT_OPPORTUNITY_SOURCE.source_id,
            records=records,
            collected_at=observed_at,
            warnings=("Synthetic closed-opportunity lifecycle scenario.",),
        ),
        run_id=run_id,
        idempotency_key=run_id,
        trigger_type="demo_seed",
        requested_by="scripts.seed_demo",
        now=observed_at,
    )
    if run_exists:
        result.current_opportunities["unchanged"] += len(records)
    else:
        result.current_opportunities["updated"] += run.promoted_count


def _with_curated_geography(definition: RegionDefinition) -> RegionDefinition:
    """Apply the repository catalog to seed definitions before upsert.

    This keeps repeat seeds unchanged instead of clearing and reapplying
    canonical fields on every run.
    """

    curated = load_curated_geographies().get(definition.region_id)
    if curated is None:
        return definition
    return definition.model_copy(
        update={
            "public_slug": curated.public_slug,
            "primary_city": curated.primary_city,
            "centroid_latitude": curated.centroid_latitude,
            "centroid_longitude": curated.centroid_longitude,
            "focus_bounds": curated.focus_bounds,
            "market_support_status": curated.market_support_status,
        }
    )


def _ensure_demo_provenance(provenance_service: ProvenanceService) -> str:
    provenance_service.upsert_source_ref(
        SourceRefDefinition(
            source_id=_DEMO_SOURCE_ID,
            source_type=SourceType.MANUAL_RESEARCH,
            source_name="MVP demo seed dataset",
            url_or_provider="seeds.mvp_data",
            collected_at=_DEMO_OBSERVED_AT,
            observed_at=_DEMO_OBSERVED_AT,
            license_or_terms_category=LicenseTermsCategory.PERMISSIVE,
            confidence=Confidence.UNKNOWN,
            data_origin=DataOrigin.DEMO_SEED,
            notes=_DEMO_NOTES,
        )
    )
    provenance_service.upsert_observation(
        SourceObservationDefinition(
            observation_id=_DEMO_OBSERVATION_ID,
            source_id=_DEMO_SOURCE_ID,
            collected_at=_DEMO_OBSERVED_AT,
            observed_at=_DEMO_OBSERVED_AT,
            data_origin=DataOrigin.SYNTHETIC_OR_CURATED_DEMO,
            observation_status=ObservationStatus.NOT_APPLICABLE,
            confidence=Confidence.UNKNOWN,
            notes=_DEMO_NOTES,
        )
    )
    return _DEMO_OBSERVATION_ID


def _link_demo_fact(
    provenance_service: ProvenanceService,
    *,
    observation_id: str,
    fact_type: FactBindingType,
    fact_id: str,
) -> None:
    provenance_service.upsert_fact_source_link(
        FactSourceLinkDefinition(
            link_id=f"demo_seed:{fact_type.value}:{fact_id}",
            observation_id=observation_id,
            fact_type=fact_type,
            fact_id=fact_id,
            data_origin=DataOrigin.DEMO_SEED,
            observation_status=ObservationStatus.NOT_APPLICABLE,
            confidence=Confidence.UNKNOWN,
            notes=_DEMO_NOTES,
        )
    )
