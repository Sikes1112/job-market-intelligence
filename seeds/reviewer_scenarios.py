"""Minimal, idempotent reviewer state for the three portfolio walkthroughs.

Scenarios A and B remain search/comparison-first and do not invent Career
Identity data. Scenario C is attached only to the explicit local-development
identity used by ``VITE_LOCAL_AUTH``. Fresh users remain empty.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.auth.boundary import ExternalAuthPrincipal
from backend.career_decisions.repository import CareerDecisionRepository
from backend.career_decisions.schemas import (
    ActionPlanCreateInput,
    DecisionCreateInput,
    DecisionOptionInput,
    OptionSelectInput,
)
from backend.career_decisions.service import CareerDecisionService
from backend.career_identity.repository import CareerIdentityRepository
from backend.career_identity.schemas import (
    CareerFactState,
    CareerFactType,
    CareerIdentityFactInput,
    CareerIdentityPrivacyInput,
    FactProvenanceInput,
)
from backend.career_identity.service import CareerIdentityService
from backend.companies.repository import CompanyRepository
from backend.geography.repository import RegionRepository
from backend.scoring.repository import RegionScoreRepository
from backend.users.repository import UserRepository
from backend.users.service import (
    SavedMarketArtifactInput,
    UserIdentityService,
    UserPersonalizationPersistenceService,
    UserPreferenceProfileInput,
)

LOCAL_DEMO_ISSUER = "https://local.job-market-intelligence.test/"
LOCAL_DEMO_SUBJECT = "local|explorer"
SCENARIO_C_DECISION_TITLE = "Synthetic demo: choose an applied-AI launch market"
SCENARIO_SOURCE_LABEL = "Synthetic portfolio reviewer scenario"


@dataclass(frozen=True, slots=True)
class ReviewerScenarioResult:
    user_id: str
    identity_fact_count: int
    decision_id: str
    action_count: int
    created_decision: bool


def seed_reviewer_scenarios(session: Session) -> ReviewerScenarioResult:
    """Prepare the explicit local reviewer identity through owned services."""

    user_repo = UserRepository(session)
    resolution = UserIdentityService(user_repo).resolve_external_principal(
        ExternalAuthPrincipal(
            provider="auth0",
            issuer=LOCAL_DEMO_ISSUER,
            subject=LOCAL_DEMO_SUBJECT,
            email="local-explorer@example.test",
            email_verified=True,
            display_name="Synthetic flexible graduate",
        )
    )
    user_id = resolution.user.user_id

    identity_repo = CareerIdentityRepository(session)
    identity_service = CareerIdentityService(identity_repo, user_repo)
    identity = identity_service.get_or_create_identity(user_id)
    identity_service.update_privacy(
        user_id,
        CareerIdentityPrivacyInput(
            ingestion_consent_granted=False,
            inference_consent_granted=False,
            downstream_personalization_consent_granted=True,
            retain_import_metadata=False,
            expected_version=identity.current_version,
        ),
    )
    provenance = FactProvenanceInput(
        source_type="synthetic_demo",
        source_label=SCENARIO_SOURCE_LABEL,
        source_ref="portfolio-demo.example/reviewer-scenarios/flexible-graduate",
        extraction_method="deterministic_seed",
        confidence="explicit_synthetic",
        notes="Illustrative reviewer state; not information about a real person.",
    )
    facts = (
        CareerIdentityFactInput(
            fact_type=CareerFactType.EDUCATION,
            normalized_key="demo-graduate-education",
            state=CareerFactState.EXPLICIT,
            provenance=provenance,
            payload={
                "institution": "Portfolio Demo University",
                "degree_type": "Master's",
                "field_of_study": "Applied Computing",
                "currently_enrolled": True,
                "expected_completion_date": "2027-05-15",
                "description": "Synthetic demonstration education record.",
            },
        ),
        CareerIdentityFactInput(
            fact_type=CareerFactType.CAREER_GOAL,
            normalized_key="demo-applied-ai-goal",
            state=CareerFactState.EXPLICIT,
            provenance=provenance,
            payload={
                "goal_type": "near_term_objective",
                "description": (
                    "Explore entry-level applied AI, technical product, and solutions roles."
                ),
                "priority": 5,
            },
        ),
        CareerIdentityFactInput(
            fact_type=CareerFactType.ROLE_PREFERENCE,
            normalized_key="demo-applied-ai-role",
            state=CareerFactState.EXPLICIT,
            provenance=provenance,
            payload={
                "role_title": "Applied AI Engineer",
                "function": "applied_ai",
                "seniority": "entry_level",
                "employment_type": "full_time",
                "preference_kind": "preferred",
                "priority": 5,
            },
        ),
        CareerIdentityFactInput(
            fact_type=CareerFactType.ROLE_PREFERENCE,
            normalized_key="demo-solutions-role",
            state=CareerFactState.EXPLICIT,
            provenance=provenance,
            payload={
                "role_title": "Solutions Engineer",
                "function": "solutions_engineering",
                "seniority": "entry_level",
                "preference_kind": "preferred",
                "priority": 4,
            },
        ),
        CareerIdentityFactInput(
            fact_type=CareerFactType.SKILL,
            normalized_key="demo-python-skill",
            state=CareerFactState.EXPLICIT,
            provenance=provenance,
            payload={"name": "Python", "normalized_name": "python"},
        ),
        CareerIdentityFactInput(
            fact_type=CareerFactType.SKILL,
            normalized_key="demo-product-discovery-skill",
            state=CareerFactState.EXPLICIT,
            provenance=provenance,
            payload={"name": "Product discovery", "normalized_name": "product discovery"},
        ),
        CareerIdentityFactInput(
            fact_type=CareerFactType.WORK_ARRANGEMENT_PREFERENCE,
            normalized_key="demo-flexible-arrangement",
            state=CareerFactState.EXPLICIT,
            provenance=provenance,
            payload={
                "arrangement": "flexible",
                "willingness": "preferred",
                "constraints": "Synthetic persona is open to onsite, hybrid, or remote work.",
                "priority": 3,
            },
        ),
    )
    for fact in facts:
        # The Career Identity merge path deliberately records duplicate
        # provenance attempts. A seed rerun is not a new user assertion, so
        # avoid manufacturing history for an already-installed fixture fact.
        if (
            identity_repo.get_fact_by_key(
                career_identity_id=identity.career_identity_id,
                fact_type=fact.fact_type.value,
                normalized_key=fact.normalized_key,
            )
            is None
        ):
            identity_service.upsert_fact(user_id, fact)

    persistence = UserPersonalizationPersistenceService(user_repo, RegionRepository(session))
    persistence.upsert_preference_profile(
        user_id,
        UserPreferenceProfileInput(
            role_interests=["applied_ai", "product_management", "solutions_engineering"],
            industry_interests=["ai", "cloud", "software"],
            preferred_regions=[],
            prestige_weighting="medium",
            brand_weighting="low",
            career_stage="entry_level",
            remote_hybrid_preference="flexible",
        ),
    )
    persistence.save_market_artifact(
        user_id,
        SavedMarketArtifactInput(
            artifact_type="comparison",
            artifact_ref="reviewer-scenario-b-nyc-boston-dc",
            label="Synthetic demo: NYC, Boston, and Washington comparison",
            notes=(
                "User-selected alternatives for a reviewer scenario; no automatic "
                "radius or proximity calculation is implied."
            ),
            snapshot={
                "artifact_type": "comparison",
                "label": "Synthetic reviewer comparison",
                "region_ids": ["greater_nyc", "greater_boston", "washington_dc"],
                "saved_from": "portfolio_demo_seed",
            },
        ),
    )

    decision_repo = CareerDecisionRepository(session)
    decision_service = CareerDecisionService(
        decision_repo,
        identity_repo,
        user_repo,
        RegionRepository(session),
        CompanyRepository(session),
        RegionScoreRepository(session),
    )
    existing = next(
        (
            row
            for row in decision_repo.list_decisions(user_id)
            if row.title == SCENARIO_C_DECISION_TITLE
        ),
        None,
    )
    created_decision = existing is None
    if existing is None:
        view = decision_service.create_decision(
            user_id,
            DecisionCreateInput(
                decision_type="location_choice",
                title=SCENARIO_C_DECISION_TITLE,
                description=(
                    "Synthetic reviewer decision comparing seeded applied-AI and adjacent paths."
                ),
                time_horizon="graduation-to-first-role",
                priorities=(
                    {"key": "entry_level_access", "label": "Entry-level access", "weight": 5},
                    {"key": "role_fit", "label": "Applied-AI or adjacent role fit", "weight": 5},
                    {"key": "work_arrangement", "label": "Arrangement flexibility", "weight": 3},
                ),
                options=(
                    DecisionOptionInput(
                        title="San Francisco Bay Area",
                        description=(
                            "Higher illustrative compensation and applied-AI concentration."
                        ),
                        scenario={
                            "region_ids": ["sf_bay_area"],
                            "roles": ["Applied AI Engineer"],
                            "work_arrangement": "hybrid",
                        },
                    ),
                    DecisionOptionInput(
                        title="Greater Seattle",
                        description="Remote/hybrid AI and solutions alternatives.",
                        scenario={
                            "region_ids": ["greater_seattle"],
                            "roles": ["Solutions Engineer"],
                            "work_arrangement": "remote",
                        },
                    ),
                    DecisionOptionInput(
                        title="Austin",
                        description="Engineering and data/AI alternatives with coverage caveats.",
                        scenario={
                            "region_ids": ["austin"],
                            "roles": ["Technical Product Manager"],
                            "work_arrangement": "onsite",
                        },
                    ),
                ),
            ),
        )
        decision_service.compare_decision(user_id, view.decision_id)
        option = next(item for item in view.options if item.title == "San Francisco Bay Area")
        decision_service.select_option(
            user_id,
            view.decision_id,
            OptionSelectInput(
                option_id=option.option_id,
                user_note="Synthetic reviewer selection; not a real user's decision.",
            ),
        )
        existing = decision_repo.get_decision(view.decision_id)
    assert existing is not None
    plan = decision_service.create_action_plan(
        user_id,
        existing.decision_id,
        ActionPlanCreateInput(title="Synthetic applied-AI market investigation plan"),
    )
    return ReviewerScenarioResult(
        user_id=user_id,
        identity_fact_count=len(identity_repo.list_facts(identity.career_identity_id)),
        decision_id=existing.decision_id,
        action_count=len(plan.actions),
        created_decision=created_decision,
    )
