"""Governed, deterministic opportunity scenarios for the portfolio demo.

The catalogue is shared by the Layer 23 marketplace and Layer 38 current-
opportunity writers. Sharing scenario inputs keeps company, market, role, and
routing identity coherent without collapsing the two domain services.

Every scenario is synthetic. Public URLs use the reserved ``.example`` domain,
source metadata carries an explicit synthetic origin, and freshness is relative
to the local seed invocation rather than a claim about a real opening.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from backend.current_opportunities.schemas import (
    AcquisitionMethod,
    AllowedUseClassification,
    CoverageStatus,
    LicenseTermsClassification,
    OpportunityCoverageInput,
    OpportunityKind,
    SourceRegistryInput,
    SourceTrustClassification,
)
from backend.current_opportunities.schemas import (
    OpportunitySourceType as CurrentOpportunitySourceType,
)
from backend.opportunities.schemas import (
    EmployerInfluenceMetadataCreate,
    OpportunityBindingConfidence,
    OpportunityCreate,
    OpportunityLocationMode,
    OpportunityProgramType,
    OpportunityRegionBindingCreate,
    OpportunityReviewStatus,
    OpportunityRoleFamilyBindingCreate,
    OpportunitySeniorityLevel,
    OpportunitySourceCreate,
    OpportunitySourceType,
    OpportunityTrustLabel,
)

DEMO_OPPORTUNITY_SOURCE_ID = "portfolio_demo_opportunities"
DEMO_CORE_RUN_ID = "portfolio_demo_opportunities_core_v2"
DEMO_PORTFOLIO_RUN_ID = "portfolio_demo_opportunities_eight_market_v2"
DEMO_CLOSED_RUN_ID = "portfolio_demo_opportunities_closed_v2"
DEMO_OPPORTUNITY_DATA_ORIGIN = "synthetic_or_curated_demo"

MARKET_LABELS: dict[str, str] = {
    "greater_boston": "Greater Boston",
    "greater_nyc": "New York City",
    "sf_bay_area": "San Francisco Bay Area",
    "greater_seattle": "Seattle",
    "washington_dc": "Washington, DC",
    "austin": "Austin",
    "atlanta": "Atlanta",
    "chicago": "Chicago",
}


@dataclass(frozen=True, slots=True)
class DemoOpportunityScenario:
    key: str
    market_id: str
    company_id: str
    company_name: str
    title: str
    role_family: str
    seniority_level: str
    work_arrangement: str
    opportunity_type: str = "job"
    employment_type: str = "full_time"
    compensation_min: float | None = None
    compensation_max: float | None = None
    compensation_interval: str = "annual"
    skills: tuple[str, ...] = ()
    aging: bool = False
    missing_application_url: bool = False
    closed: bool = False

    @property
    def market_label(self) -> str:
        return MARKET_LABELS[self.market_id]


DEMO_OPPORTUNITY_SCENARIOS: tuple[DemoOpportunityScenario, ...] = (
    # Greater Boston: the default software/job experience has useful results.
    DemoOpportunityScenario(
        "boston-software-1",
        "greater_boston",
        "cmp_google",
        "Google",
        "Demo Software Engineer I",
        "software_engineering",
        "entry_level",
        "hybrid",
        compensation_min=110_000,
        compensation_max=135_000,
        skills=("Python", "Distributed systems"),
    ),
    DemoOpportunityScenario(
        "boston-software-2",
        "greater_boston",
        "comp_hubspot",
        "HubSpot",
        "Demo New Graduate Platform Engineer",
        "software_engineering",
        "new_graduate",
        "remote",
        compensation_min=98_000,
        compensation_max=122_000,
        skills=("TypeScript", "Cloud platforms"),
    ),
    DemoOpportunityScenario(
        "boston-software-3",
        "greater_boston",
        "cmp_beacon_robotics",
        "Beacon Robotics",
        "Demo Robotics Software Engineer I",
        "software_engineering",
        "early_career",
        "onsite",
        compensation_min=96_000,
        compensation_max=118_000,
        skills=("Robotics", "C++"),
    ),
    # New York: product, applied-AI, and solutions paths.
    DemoOpportunityScenario(
        "nyc-applied-ai",
        "greater_nyc",
        "cmp_hudson_applied_ai",
        "Hudson Applied AI",
        "Demo Applied AI Engineer I",
        "applied_ai",
        "entry_level",
        "hybrid",
        compensation_min=125_000,
        compensation_max=155_000,
        skills=("Python", "Machine learning", "Evaluation"),
    ),
    DemoOpportunityScenario(
        "nyc-product",
        "greater_nyc",
        "cmp_brooklyn_cloudworks",
        "Brooklyn Cloudworks",
        "Demo Technical Product Associate",
        "product_management",
        "entry_level",
        "onsite",
        compensation_min=105_000,
        compensation_max=128_000,
        skills=("Product discovery", "Analytics"),
    ),
    DemoOpportunityScenario(
        "nyc-solutions",
        "greater_nyc",
        "cmp_liberty_cyber_systems",
        "Liberty Cyber Systems",
        "Demo Solutions Engineer I",
        "solutions_engineering",
        "early_career",
        "hybrid",
        skills=("Customer discovery", "Security"),
    ),
    # Bay Area: strongest applied-AI compensation, with product/data adjacency.
    DemoOpportunityScenario(
        "sf-applied-ai",
        "sf_bay_area",
        "cmp_pacific_ai_labs",
        "Pacific AI Labs",
        "Demo Applied AI Engineer, New Graduate",
        "applied_ai",
        "new_graduate",
        "onsite",
        compensation_min=145_000,
        compensation_max=180_000,
        skills=("Python", "Model evaluation", "Data systems"),
    ),
    DemoOpportunityScenario(
        "sf-product",
        "sf_bay_area",
        "cmp_google",
        "Google",
        "Demo Associate Technical Product Manager",
        "product_management",
        "early_career",
        "hybrid",
        compensation_min=135_000,
        compensation_max=165_000,
        skills=("AI product strategy", "Experiment design"),
    ),
    DemoOpportunityScenario(
        "sf-data",
        "sf_bay_area",
        "comp_databricks",
        "Databricks",
        "Demo Data Platform Engineer I",
        "data_ai",
        "entry_level",
        "hybrid",
        compensation_min=138_000,
        compensation_max=172_000,
        skills=("Python", "Data platforms"),
    ),
    # Seattle: varied arrangements and one intentionally aging internship.
    DemoOpportunityScenario(
        "seattle-applied-ai",
        "greater_seattle",
        "cmp_hudson_applied_ai",
        "Hudson Applied AI",
        "Demo Applied AI Solutions Associate",
        "applied_ai",
        "entry_level",
        "remote",
        compensation_min=118_000,
        compensation_max=145_000,
        skills=("Machine learning", "Customer discovery"),
    ),
    DemoOpportunityScenario(
        "seattle-solutions",
        "greater_seattle",
        "cmp_cascade_cloud_labs",
        "Cascade Cloud Labs",
        "Demo Cloud Solutions Engineer I",
        "solutions_engineering",
        "early_career",
        "hybrid",
        skills=("Cloud", "Technical demonstrations"),
    ),
    DemoOpportunityScenario(
        "seattle-software-intern",
        "greater_seattle",
        "cmp_sound_security_systems",
        "Sound Security Systems",
        "Demo Security Software Intern",
        "software_engineering",
        "internship",
        "onsite",
        opportunity_type="internship",
        employment_type="internship",
        aging=True,
        compensation_min=29,
        compensation_max=36,
        compensation_interval="hourly",
        skills=("Python", "Security engineering"),
    ),
    # Washington, DC: public-sector-adjacent solutions/product/data mix.
    DemoOpportunityScenario(
        "dc-solutions",
        "washington_dc",
        "cmp_microsoft",
        "Microsoft",
        "Demo Cloud Solutions Engineer I",
        "solutions_engineering",
        "entry_level",
        "hybrid",
        compensation_min=105_000,
        compensation_max=132_000,
        skills=("Cloud", "Customer discovery"),
    ),
    DemoOpportunityScenario(
        "dc-data-ai",
        "washington_dc",
        "cmp_cisco",
        "Cisco Systems",
        "Demo Applied Data Analyst",
        "data_ai",
        "entry_level",
        "onsite",
        compensation_min=92_000,
        compensation_max=116_000,
        skills=("Python", "Analytics", "Security"),
    ),
    DemoOpportunityScenario(
        "dc-product",
        "washington_dc",
        "cmp_deloitte",
        "Deloitte",
        "Demo Technical Product Analyst",
        "product_management",
        "early_career",
        "hybrid",
        skills=("Product analytics", "Stakeholder discovery"),
    ),
    # Austin: engineering strength plus an experimental product scope.
    DemoOpportunityScenario(
        "austin-software",
        "austin",
        "cmp_google",
        "Google",
        "Demo Software Engineer I",
        "software_engineering",
        "entry_level",
        "hybrid",
        compensation_min=108_000,
        compensation_max=134_000,
        skills=("Go", "Cloud platforms"),
    ),
    DemoOpportunityScenario(
        "austin-product",
        "austin",
        "cmp_deloitte",
        "Deloitte",
        "Demo Technical Product Associate",
        "product_management",
        "entry_level",
        "remote",
        skills=("Product discovery", "Analytics"),
    ),
    DemoOpportunityScenario(
        "austin-data-ai",
        "austin",
        "cmp_lone_star_cloud",
        "Lone Star Cloud",
        "Demo Data and AI Engineer I",
        "data_ai",
        "early_career",
        "onsite",
        compensation_min=96_000,
        compensation_max=120_000,
        skills=("Python", "Data pipelines"),
    ),
    # Atlanta: one incomplete route intentionally demonstrates exclusion.
    DemoOpportunityScenario(
        "atlanta-solutions",
        "atlanta",
        "cmp_microsoft",
        "Microsoft",
        "Demo Solutions Engineer I",
        "solutions_engineering",
        "entry_level",
        "hybrid",
        compensation_min=92_000,
        compensation_max=116_000,
        skills=("Cloud", "Technical demonstrations"),
    ),
    DemoOpportunityScenario(
        "atlanta-software-intern",
        "atlanta",
        "cmp_cisco",
        "Cisco Systems",
        "Demo Software Engineering Intern",
        "software_engineering",
        "internship",
        "onsite",
        opportunity_type="internship",
        employment_type="internship",
        missing_application_url=True,
        skills=("Networking", "Python"),
    ),
    DemoOpportunityScenario(
        "atlanta-data",
        "atlanta",
        "cmp_jpmorgan_chase",
        "JPMorgan Chase",
        "Demo Data Platform Analyst",
        "data_ai",
        "early_career",
        "hybrid",
        skills=("SQL", "Data quality"),
    ),
    # Chicago: explicit unsupported coverage and a closed row preserve abstention.
    DemoOpportunityScenario(
        "chicago-applied-ai",
        "chicago",
        "cmp_google",
        "Google",
        "Demo Applied AI Engineer I",
        "applied_ai",
        "entry_level",
        "hybrid",
        compensation_min=116_000,
        compensation_max=145_000,
        skills=("Python", "Machine learning"),
    ),
    DemoOpportunityScenario(
        "chicago-product-closed",
        "chicago",
        "cmp_microsoft",
        "Microsoft",
        "Demo Technical Product Analyst",
        "product_management",
        "early_career",
        "onsite",
        closed=True,
        skills=("Product analytics", "Cloud"),
    ),
    DemoOpportunityScenario(
        "chicago-solutions-limited",
        "chicago",
        "cmp_jpmorgan_chase",
        "JPMorgan Chase",
        "Demo Platform Solutions Associate",
        "solutions_engineering",
        "entry_level",
        "hybrid",
        skills=("Data platforms", "Customer discovery"),
    ),
)

CORE_MARKET_IDS = frozenset({"greater_boston", "sf_bay_area"})
CORE_SCENARIO_KEYS = frozenset({"boston-software-2", "sf-data"})


def demo_observed_at(now: datetime | None = None) -> datetime:
    """Return the explicit simulated observation time for one seed invocation."""

    value = now or datetime.now(UTC)
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def scenarios_for_markets(
    market_ids: set[str] | frozenset[str],
) -> tuple[DemoOpportunityScenario, ...]:
    return tuple(item for item in DEMO_OPPORTUNITY_SCENARIOS if item.market_id in market_ids)


def core_scenarios() -> tuple[DemoOpportunityScenario, ...]:
    """Return scenarios whose employers already exist in the narrow MVP seed."""

    return tuple(item for item in DEMO_OPPORTUNITY_SCENARIOS if item.key in CORE_SCENARIO_KEYS)


CURRENT_OPPORTUNITY_SOURCE = SourceRegistryInput(
    source_id=DEMO_OPPORTUNITY_SOURCE_ID,
    provider="Synthetic portfolio demonstration fixture",
    display_name="Synthetic portfolio demonstration opportunities",
    source_type=CurrentOpportunitySourceType.CURATED_INPUT,
    acquisition_method=AcquisitionMethod.CURATED_IMPORT,
    allowed_use=AllowedUseClassification.ALLOWED_WITH_CAUTION,
    license_terms=LicenseTermsClassification.PERMISSIVE,
    trust=SourceTrustClassification.MEDIUM,
    freshness_sla_hours=2160,
    supported_domains=("portfolio-demo.example",),
    supported_markets=tuple(MARKET_LABELS),
    supported_opportunity_types=(
        OpportunityKind.JOB,
        OpportunityKind.INTERNSHIP,
        OpportunityKind.EARLY_CAREER_PROGRAM,
    ),
    ranking_use_allowed=True,
    display_use_allowed=True,
    refresh_config={
        "fixture_version": "v2",
        "data_origin": DEMO_OPPORTUNITY_DATA_ORIGIN,
        "synthetic": True,
        "freshness_policy": "simulated_relative_to_seed_time",
    },
    provenance_requirements=(
        "provider_record_id",
        "observed_at",
        "synthetic_demo_label",
    ),
)


def marketplace_opportunities(
    scenarios: tuple[DemoOpportunityScenario, ...],
    *,
    observed_at: datetime,
) -> tuple[OpportunityCreate, ...]:
    return tuple(_marketplace_opportunity(item, observed_at=observed_at) for item in scenarios)


def current_opportunity_coverage(
    market_ids: set[str] | frozenset[str],
    *,
    evaluated_at: datetime,
) -> tuple[OpportunityCoverageInput, ...]:
    # Insert exact scopes before wildcard scopes. The service's public lookup
    # intentionally falls back to wildcard contracts, so this ordering keeps
    # an exact upsert from updating the already-present fallback row.
    rows: list[OpportunityCoverageInput] = []
    if "austin" in market_ids:
        rows.append(
            _coverage(
                "cov_demo_austin_product_job",
                market_id="austin",
                role_family="product_management",
                opportunity_type=OpportunityKind.JOB,
                status=CoverageStatus.EXPERIMENTAL,
                evaluated_at=evaluated_at,
            )
        )
    if "chicago" in market_ids:
        rows.append(
            _coverage(
                "cov_demo_chicago_solutions_job",
                market_id="chicago",
                role_family="solutions_engineering",
                opportunity_type=OpportunityKind.JOB,
                status=CoverageStatus.UNSUPPORTED,
                evaluated_at=evaluated_at,
            )
        )
    rows.extend(
        _coverage(
            f"cov_demo_{market_id}_all",
            market_id=market_id,
            role_family="*",
            opportunity_type="*",
            status=CoverageStatus.LIMITED,
            evaluated_at=evaluated_at,
        )
        for market_id in MARKET_LABELS
        if market_id in market_ids
    )
    return tuple(rows)


def current_opportunity_records(
    scenarios: tuple[DemoOpportunityScenario, ...],
    *,
    observed_at: datetime,
) -> tuple[dict[str, object], ...]:
    return tuple(_current_record(item, observed_at=observed_at) for item in scenarios)


def closed_opportunity_records(
    scenarios: tuple[DemoOpportunityScenario, ...],
    *,
    observed_at: datetime,
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "provider_record_id": item.key,
            "observed_at": observed_at,
            "collected_at": observed_at,
            "status": "removed",
            "raw_payload": {
                "provider_record_id": item.key,
                "synthetic_demo": True,
                "data_origin": DEMO_OPPORTUNITY_DATA_ORIGIN,
                "removal_reason": "synthetic closed-opportunity scenario",
            },
        }
        for item in scenarios
        if item.closed
    )


def _marketplace_opportunity(
    scenario: DemoOpportunityScenario,
    *,
    observed_at: datetime,
) -> OpportunityCreate:
    application_deadline = date(2000, 1, 1) if scenario.closed else date(2099, 12, 31)
    application_open_date = date(1999, 12, 1) if scenario.closed else observed_at.date()
    program_type = (
        OpportunityProgramType.INTERNSHIP
        if scenario.opportunity_type == "internship"
        else OpportunityProgramType.NEW_GRAD_ROLE
        if scenario.seniority_level in {"entry_level", "new_graduate"}
        else OpportunityProgramType.EMPLOYER_PROGRAM
    )
    seniority = (
        OpportunitySeniorityLevel.INTERNSHIP
        if scenario.seniority_level == "internship"
        else OpportunitySeniorityLevel.NEW_GRAD
        if scenario.seniority_level in {"entry_level", "new_graduate"}
        else OpportunitySeniorityLevel.EARLY_CAREER
    )
    return OpportunityCreate(
        opportunity_id=f"opp_demo_{scenario.key.replace('-', '_')}",
        employer_program_id=f"program_demo_{scenario.key.replace('-', '_')}",
        employer_id=scenario.company_id,
        employer_name=scenario.company_name,
        program_name=scenario.title,
        program_type=program_type,
        location_mode=OpportunityLocationMode(scenario.work_arrangement),
        seniority_level=seniority,
        eligibility_summary=(
            "Synthetic portfolio-demo scenario for filters and routing; "
            "it is not an actual opening."
        ),
        application_url=f"https://portfolio-demo.example/apply/{scenario.key}",
        source_url=f"https://portfolio-demo.example/opportunities/{scenario.key}",
        source_type=OpportunitySourceType.MANUAL_RESEARCH,
        application_open_date=application_open_date,
        application_deadline=application_deadline,
        compensation_min=scenario.compensation_min,
        compensation_max=scenario.compensation_max,
        compensation_disclosed=scenario.compensation_min is not None,
        trust_label=OpportunityTrustLabel.UNVERIFIED,
        review_status=OpportunityReviewStatus.PENDING_REVIEW,
        employer_influence=EmployerInfluenceMetadataCreate(
            internal_review_notes=(
                "Synthetic demonstration data; never treat as a real employer program."
            )
        ),
        sources=(
            OpportunitySourceCreate(
                opportunity_source_id=f"src_opp_demo_{scenario.key.replace('-', '_')}",
                source_type=OpportunitySourceType.MANUAL_RESEARCH,
                source_url=f"https://portfolio-demo.example/sources/{scenario.key}",
                source_name="Synthetic portfolio demonstration fixture",
                collected_at=observed_at,
                verification_note=(
                    "Reserved .example demonstration record; not factual market evidence."
                ),
            ),
        ),
        region_bindings=(
            OpportunityRegionBindingCreate(
                opportunity_region_binding_id=f"region_opp_demo_{scenario.key.replace('-', '_')}",
                region_id=scenario.market_id,
                region_label=scenario.market_label,
                binding_confidence=OpportunityBindingConfidence.HIGH,
            ),
        ),
        role_family_bindings=(
            OpportunityRoleFamilyBindingCreate(
                opportunity_role_family_binding_id=(
                    f"role_opp_demo_{scenario.key.replace('-', '_')}"
                ),
                role_family=scenario.role_family,
                role_family_label=scenario.role_family.replace("_", " ").title(),
                binding_confidence=OpportunityBindingConfidence.HIGH,
            ),
        ),
        created_at=observed_at,
    )


def _coverage(
    coverage_id: str,
    *,
    market_id: str,
    role_family: str,
    opportunity_type: OpportunityKind | str,
    status: CoverageStatus,
    evaluated_at: datetime,
) -> OpportunityCoverageInput:
    return OpportunityCoverageInput(
        coverage_id=coverage_id,
        market_key=market_id,
        market_id=market_id,
        market_label=MARKET_LABELS[market_id],
        role_family=role_family,
        opportunity_type=opportunity_type,
        status=status,
        rationale=(
            "Synthetic portfolio-demo coverage for governed workflow behavior; "
            "it is intentionally non-exhaustive and is not live-market coverage."
        ),
        source_basis={
            "sources": [DEMO_OPPORTUNITY_SOURCE_ID],
            "data_origin": DEMO_OPPORTUNITY_DATA_ORIGIN,
            "synthetic": True,
            "freshness_policy": "simulated_relative_to_seed_time",
        },
        minimum_expected_sources=1,
        freshness_max_age_hours=8760,
        last_evaluated_at=evaluated_at,
    )


def _current_record(
    scenario: DemoOpportunityScenario,
    *,
    observed_at: datetime,
) -> dict[str, object]:
    scenario_observed_at = observed_at - timedelta(days=100) if scenario.aging else observed_at
    application_url = (
        None
        if scenario.missing_application_url
        else f"https://portfolio-demo.example/apply/{scenario.key}"
    )
    payload: dict[str, object] = {
        "provider_record_id": scenario.key,
        "company_id": scenario.company_id,
        "company_name": scenario.company_name,
        "title": scenario.title,
        "role_family": scenario.role_family,
        "seniority_level": scenario.seniority_level,
        "market_id": scenario.market_id,
        "market_label": scenario.market_label,
        "location": f"{scenario.market_label} ({scenario.work_arrangement})",
        "work_arrangement": scenario.work_arrangement,
        "employment_type": scenario.employment_type,
        "opportunity_type": scenario.opportunity_type,
        "posting_date": scenario_observed_at.date().isoformat(),
        "closing_date": "2099-12-31",
        "application_url": application_url,
        "source_url": f"https://portfolio-demo.example/opportunities/{scenario.key}",
        "description": (
            "Synthetic demonstration opportunity for local portfolio testing; "
            "this is not an actual opening or factual employer activity."
        ),
        "skills": list(scenario.skills),
        "requirements": [
            "Synthetic portfolio demonstration only",
            "No real application is accepted",
        ],
        "synthetic_demo": True,
        "data_origin": DEMO_OPPORTUNITY_DATA_ORIGIN,
    }
    if scenario.compensation_min is not None:
        payload.update(
            {
                "compensation_min": scenario.compensation_min,
                "compensation_max": scenario.compensation_max,
                "compensation_currency": "USD",
                "compensation_interval": scenario.compensation_interval,
            }
        )
    return {
        "provider_record_id": scenario.key,
        "observed_at": scenario_observed_at,
        "collected_at": observed_at,
        "raw_payload": payload,
    }
