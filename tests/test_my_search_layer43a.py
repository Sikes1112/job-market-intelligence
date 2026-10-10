from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.career_decisions.models import (
    CareerAction,
    CareerActionPlan,
    CareerApplication,
    CareerApplicationTransition,
    CareerDecision,
    DecisionOption,
    DecisionVersion,
)
from backend.career_decisions.repository import CareerDecisionRepository
from backend.career_decisions.schemas import (
    ActionPlanCreateInput,
    ApplicationCreateInput,
    ApplicationTransitionInput,
    CareerActionUpdateInput,
    OptionSelectInput,
)
from backend.career_decisions.service import CareerDecisionService
from backend.career_identity.repository import CareerIdentityRepository
from backend.companies.models import Company
from backend.companies.repository import CompanyRepository
from backend.current_opportunities.adapters import StaticOpportunityAdapter
from backend.current_opportunities.models import CurrentOpportunity
from backend.current_opportunities.repository import CurrentOpportunityRepository
from backend.current_opportunities.schemas import (
    AcquisitionMethod,
    AllowedUseClassification,
    CoverageStatus,
    LicenseTermsClassification,
    OpportunityCoverageInput,
    OpportunityKind,
    OpportunitySourceType,
    SourceRegistryInput,
    SourceTrustClassification,
)
from backend.current_opportunities.service import CurrentOpportunityService
from backend.explore.models import ExploreComparisonSnapshot, ExploreDecisionProvenance
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.my_search.schemas import TrackOpportunityInput
from backend.my_search.service import (
    MySearchService,
    SearchWorkspaceNotFound,
    SearchWorkspaceValidationError,
)
from backend.product_measurement.service import ProductMeasurementService
from backend.scoring.repository import RegionScoreRepository
from backend.users.models import SavedMarketArtifact, User
from backend.users.repository import UserRepository
from tests.test_api_user_routes import _auth_headers, _current_user_id

NOW = datetime(2026, 10, 9, 12, tzinfo=UTC)


def _decision_service(session: Session) -> CareerDecisionService:
    return CareerDecisionService(
        CareerDecisionRepository(session),
        CareerIdentityRepository(session),
        UserRepository(session),
        RegionRepository(session),
        CompanyRepository(session),
        RegionScoreRepository(session),
        ProductMeasurementService(session),
    )


def _seed_foundation(session: Session) -> None:
    session.add_all(
        [
            User(user_id="search_user"),
            User(user_id="other_user"),
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                public_slug="boston",
                region_type="greater_region",
            ),
            Region(
                region_id="greater_nyc",
                region_name="greater_nyc",
                display_name="Greater New York",
                public_slug="new-york",
                region_type="greater_region",
            ),
            Company(
                company_id="company_acme",
                company_name="Acme AI",
                normalized_company_name="acme ai",
                sector_primary="ai",
            ),
        ]
    )
    session.flush()


def _seed_pursuit(session: Session, suffix: str = "boston", *, user_id: str = "search_user") -> str:
    decision_id = f"decision_{suffix}"
    selected_id = f"option_{suffix}_selected"
    alternate_id = f"option_{suffix}_alternate"
    selected_region = "greater_boston" if suffix != "nyc" else "greater_nyc"
    alternate_region = "greater_nyc" if selected_region == "greater_boston" else "greater_boston"
    selected_title = "Greater Boston" if selected_region == "greater_boston" else "Greater New York"
    alternate_title = (
        "Greater New York" if selected_region == "greater_boston" else "Greater Boston"
    )
    decision = CareerDecision(
        decision_id=decision_id,
        user_id=user_id,
        decision_type="location_choice",
        status="decided",
        title=f"Prioritize {selected_title}",
        selected_option_id=selected_id,
        decision_date=NOW,
        priorities=[{"key": "ai_product", "label": "AI Product · Internship", "weight": 5}],
        constraints=[],
        current_version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    session.add(decision)
    session.add_all(
        [
            DecisionOption(
                option_id=selected_id,
                user_id=user_id,
                decision_id=decision_id,
                title=selected_title,
                scenario={
                    "region_id": selected_region,
                    "public_slug": (
                        "boston" if selected_region == "greater_boston" else "new-york"
                    ),
                },
                status="selected",
                position=0,
            ),
            DecisionOption(
                option_id=alternate_id,
                user_id=user_id,
                decision_id=decision_id,
                title=alternate_title,
                scenario={
                    "region_id": alternate_region,
                    "public_slug": ("new-york" if alternate_region == "greater_nyc" else "boston"),
                },
                status="rejected",
                position=1,
            ),
        ]
    )
    session.flush()
    return decision_id


def _seed_actions_and_application(session: Session, decision_id: str) -> None:
    plan = CareerActionPlan(
        action_plan_id="plan_boston",
        user_id="search_user",
        decision_id=decision_id,
        selected_option_id="option_boston_selected",
        title="Boston execution",
        status="active",
        plan_payload={},
    )
    session.add(plan)
    session.flush()
    session.add_all(
        [
            CareerAction(
                action_id="action_first",
                user_id="search_user",
                action_plan_id=plan.action_plan_id,
                decision_id=decision_id,
                option_id="option_boston_selected",
                action_type="research",
                status="open",
                title="Review Boston AI Product openings",
                due_at=NOW + timedelta(days=1),
                priority=1,
                position=0,
                metadata_json={},
            ),
            CareerAction(
                action_id="action_second",
                user_id="search_user",
                action_plan_id=plan.action_plan_id,
                decision_id=decision_id,
                option_id="option_boston_selected",
                action_type="company_targeting",
                status="open",
                title="Pick 10 target employers",
                due_at=NOW + timedelta(days=2),
                priority=2,
                position=1,
                metadata_json={},
            ),
            CareerApplication(
                application_id="application_manual",
                user_id="search_user",
                decision_id=decision_id,
                option_id="option_boston_selected",
                company_id=None,
                region_id=None,
                role_title="APM Intern",
                status="preparing",
                status_started_at=NOW,
                source_url="https://example.com/apply",
                metadata_json={"company_name": "Manual Co", "location_text": "Boston"},
                created_at=NOW,
                updated_at=NOW,
            ),
        ]
    )
    session.flush()


def _seed_comparison_and_saved(session: Session, decision_id: str) -> None:
    payload = {
        "compared_markets": [
            {"fit": {"region": {"display_name": "Greater Boston"}}},
            {"fit": {"region": {"display_name": "Greater New York"}}},
        ],
        "recommendation_summary": "New York has a slight governed edge.",
    }
    session.add(
        ExploreComparisonSnapshot(
            comparison_id="comparison_saved",
            user_id="search_user",
            snapshot_schema_version=1,
            comparison_identity="comparison-identity",
            selected_region_ids=["greater_boston", "greater_nyc"],
            selected_public_slugs=["boston", "new-york"],
            context_fingerprint="context-fingerprint",
            effective_context_summary={"goal": "ai_ml"},
            recommendation_state="near_tie",
            winner_region_ids=["greater_nyc"],
            tie_region_ids=[],
            confidence="medium",
            algorithm_version="explore_fit_v1",
            evidence_authority_version="layer_34",
            evidence_bundle="bundle",
            calibration_version="v1",
            snapshot_payload=payload,
            recommendation_summary="New York has a slight governed edge.",
            generated_at=NOW,
            saved_at=NOW,
            created_at=NOW,
        )
    )
    session.add(
        ExploreDecisionProvenance(
            provenance_id="provenance_boston",
            user_id="search_user",
            decision_id=decision_id,
            comparison_id="comparison_saved",
            context_fingerprint="context-fingerprint",
            market_set_fingerprint="market-set",
            system_recommendation_state="near_tie",
            system_recommended_region_ids=["greater_nyc"],
            user_selected_region_id="greater_boston",
            choice_matches_recommendation=False,
            created_at=NOW,
        )
    )
    session.add(
        SavedMarketArtifact(
            saved_artifact_id="saved_boston",
            user_id="search_user",
            artifact_type="region",
            artifact_ref="greater_boston",
            label="Boston",
            snapshot={},
        )
    )
    session.flush()


def _seed_current_opportunity(
    session: Session,
    *,
    market_id: str = "greater_boston",
    suffix: str = "boston",
    role_family: str = "product_management",
    opportunity_type: str = "internship",
    work_arrangement: str = "hybrid",
    title: str = "AI Product Intern",
) -> str:
    service = CurrentOpportunityService(CurrentOpportunityRepository(session))
    service.upsert_source(
        SourceRegistryInput(
            source_id=f"source_acme_{suffix}",
            provider="Acme",
            display_name="Acme Careers",
            source_type=OpportunitySourceType.API,
            acquisition_method=AcquisitionMethod.API_PULL,
            enabled=True,
            allowed_use=AllowedUseClassification.ALLOWED,
            license_terms=LicenseTermsClassification.PERMISSIVE,
            trust=SourceTrustClassification.HIGH,
            freshness_sla_hours=48,
            supported_markets=(market_id,),
            supported_opportunity_types=(OpportunityKind.INTERNSHIP,),
            ranking_use_allowed=True,
            display_use_allowed=True,
            provenance_requirements=("provider_record_id", "observed_at"),
        )
    )
    service.upsert_coverage(
        OpportunityCoverageInput(
            coverage_id=f"coverage_{suffix}",
            market_key=market_id,
            market_id=market_id,
            market_label="Greater Boston" if market_id == "greater_boston" else "Greater New York",
            role_family=role_family,
            opportunity_type=opportunity_type,
            status=CoverageStatus.PRODUCTION_READY,
            rationale="Curated current coverage.",
            source_basis={"sources": ["source_acme"]},
            minimum_expected_sources=1,
            freshness_max_age_hours=72,
            last_evaluated_at=NOW,
        )
    )
    service.refresh_source(
        StaticOpportunityAdapter(
            source_id=f"source_acme_{suffix}",
            collected_at=NOW,
            records=(
                {
                    "provider_record_id": f"acme-product-intern-{suffix}",
                    "observed_at": NOW,
                    "collected_at": NOW,
                    "raw_payload": {
                        "company_id": "company_acme",
                        "company_name": "Acme AI",
                        "title": title,
                        "seniority_level": "entry_level",
                        "role_family": role_family,
                        "market_id": market_id,
                        "location": (
                            "Greater Boston"
                            if market_id == "greater_boston"
                            else "Greater New York"
                        ),
                        "work_arrangement": work_arrangement,
                        "employment_type": "internship",
                        "opportunity_type": opportunity_type,
                        "application_url": f"https://jobs.example.com/acme-product-intern-{suffix}",
                        "source_url": f"https://jobs.example.com/acme-product-intern-{suffix}",
                    },
                },
            ),
        ),
        now=NOW,
    )
    return session.execute(
        select(CurrentOpportunity.current_opportunity_id).where(
            CurrentOpportunity.application_url
            == f"https://jobs.example.com/acme-product-intern-{suffix}"
        )
    ).scalar_one()


def test_workspace_groups_active_saved_history_and_advances_next_action(session: Session) -> None:
    _seed_foundation(session)
    decision_id = _seed_pursuit(session)
    _seed_pursuit(session, "nyc")
    _seed_actions_and_application(session, decision_id)
    _seed_comparison_and_saved(session, decision_id)

    workspace = MySearchService(session, clock=lambda: NOW).workspace("search_user")
    assert [item.decision_id for item in workspace.active_pursuits] == [
        "decision_boston",
        "decision_nyc",
    ]
    boston = next(item for item in workspace.active_pursuits if item.decision_id == decision_id)
    assert boston.next_action is not None
    assert boston.next_action.action_id == "action_first"
    assert boston.applications[0].company_name == "Manual Co"
    assert boston.source_comparison is not None
    assert boston.source_comparison.original_user_choice == "Greater Boston"
    assert boston.source_comparison.current_user_choice == "Greater Boston"
    assert boston.source_comparison.original_choice_matches_recommendation is False
    assert boston.source_comparison.current_choice_matches_recommendation is False
    assert boston.source_comparison.system_recommendation == ("Greater New York",)
    assert len(workspace.saved_comparisons) == 1
    assert len(workspace.saved_items) == 1

    _decision_service(session).update_action(
        "search_user",
        "action_first",
        CareerActionUpdateInput(status="completed"),
    )
    refreshed = MySearchService(session, clock=lambda: NOW).workspace("search_user")
    boston = next(item for item in refreshed.active_pursuits if item.decision_id == decision_id)
    assert boston.next_action is not None
    assert boston.next_action.action_id == "action_second"
    assert any(item.kind == "action_completed" for item in refreshed.history)

    _decision_service(session).update_action(
        "search_user",
        "action_first",
        CareerActionUpdateInput(status="open"),
    )
    reopened = session.get(CareerAction, "action_first")
    assert reopened is not None
    assert reopened.completed_at is None
    after_reopen = MySearchService(session, clock=lambda: NOW).workspace("search_user")
    assert any(item.kind == "action_completed" for item in after_reopen.history)


def test_apply_and_track_is_duplicate_safe_and_external_open_is_not_applied(
    session: Session,
) -> None:
    _seed_foundation(session)
    decision_id = _seed_pursuit(session)
    opportunity_id = _seed_current_opportunity(session)
    service = MySearchService(session, clock=lambda: NOW)

    first = service.track_opportunity(
        "search_user",
        TrackOpportunityInput(decision_id=decision_id, opportunity_id=opportunity_id),
    )
    repeated = service.track_opportunity(
        "search_user",
        TrackOpportunityInput(decision_id=decision_id, opportunity_id=opportunity_id),
    )
    assert first.created is True
    assert repeated.created is False
    assert repeated.application.application_id == first.application.application_id
    assert first.application.status == "preparing"
    assert first.external_application_url == "https://jobs.example.com/acme-product-intern-boston"

    stored = session.get(CareerApplication, first.application.application_id)
    assert stored is not None
    assert stored.status == "preparing"
    assert stored.applied_at is None
    assert stored.metadata_json["current_opportunity_id"] == opportunity_id
    assert session.query(CareerApplication).filter_by(user_id="search_user").count() == 1

    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            CareerApplication(
                application_id="racing_duplicate_application",
                user_id="search_user",
                decision_id=decision_id,
                option_id="option_boston_selected",
                region_id="greater_boston",
                current_opportunity_id=opportunity_id,
                role_title="Duplicate Product Intern",
                status="preparing",
                status_started_at=NOW,
                metadata_json={"current_opportunity_id": opportunity_id},
            )
        )
        session.flush()
    assert session.query(CareerApplication).filter_by(user_id="search_user").count() == 1

    transitioned = _decision_service(session).transition_application(
        "search_user",
        stored.application_id,
        ApplicationTransitionInput(to_status="applied", transitioned_at=NOW),
    )
    assert transitioned.status == "applied"
    assert transitioned.applied_at == NOW


def test_two_market_pursuits_share_hard_scope_for_detail_summary_and_tracking(
    session: Session,
) -> None:
    _seed_foundation(session)
    boston_decision = _seed_pursuit(session)
    nyc_decision = _seed_pursuit(session, "nyc")
    boston_opportunity = _seed_current_opportunity(session)
    nyc_opportunity = _seed_current_opportunity(session, market_id="greater_nyc", suffix="nyc")

    opportunity_service = CurrentOpportunityService(CurrentOpportunityRepository(session))
    boston_matches = opportunity_service.strategic_matches(
        "search_user", decision_id=boston_decision, include_ineligible=False
    )
    nyc_matches = opportunity_service.strategic_matches(
        "search_user", decision_id=nyc_decision, include_ineligible=False
    )
    assert {item.opportunity.opportunity_id for item in boston_matches} == {boston_opportunity}
    assert {item.opportunity.opportunity_id for item in nyc_matches} == {nyc_opportunity}

    workspace = MySearchService(session, clock=lambda: NOW).workspace("search_user")
    summaries = {
        item.decision_id: {
            row["opportunity_id"] for row in item.current_opportunities.top_opportunities
        }
        for item in workspace.active_pursuits
    }
    assert summaries[boston_decision] == {boston_opportunity}
    assert summaries[nyc_decision] == {nyc_opportunity}

    my_search = MySearchService(session, clock=lambda: NOW)
    with pytest.raises(SearchWorkspaceValidationError):
        my_search.track_opportunity(
            "search_user",
            TrackOpportunityInput(decision_id=boston_decision, opportunity_id=nyc_opportunity),
        )
    assert session.query(CareerApplication).count() == 0

    tracked = my_search.track_opportunity(
        "search_user",
        TrackOpportunityInput(decision_id=boston_decision, opportunity_id=boston_opportunity),
    )
    assert tracked.created is True
    assert tracked.application.status == "preparing"
    assert tracked.application.decision_id == boston_decision


def test_explicit_supported_pursuit_filters_are_shared_by_matching_and_tracking(
    session: Session,
) -> None:
    _seed_foundation(session)
    decision_id = _seed_pursuit(session)
    selected = session.get(DecisionOption, "option_boston_selected")
    assert selected is not None
    selected.scenario = {
        **selected.scenario,
        "role_family": "product_management",
        "opportunity_type": "internship",
        "work_arrangement": "hybrid",
    }
    matching_id = _seed_current_opportunity(session)
    wrong_role_id = _seed_current_opportunity(
        session,
        suffix="wrong-role",
        role_family="software_engineering",
        title="Software Engineering Intern",
    )
    wrong_work_id = _seed_current_opportunity(
        session,
        suffix="wrong-work",
        work_arrangement="remote",
        title="Remote AI Product Intern",
    )
    session.flush()

    opportunity_service = CurrentOpportunityService(CurrentOpportunityRepository(session))
    matches = opportunity_service.strategic_matches(
        "search_user", decision_id=decision_id, include_ineligible=False
    )
    assert {item.opportunity.opportunity_id for item in matches} == {matching_id}
    workspace = MySearchService(session).workspace("search_user")
    assert {
        item["opportunity_id"]
        for item in workspace.active_pursuits[0].current_opportunities.top_opportunities
    } == {matching_id}

    service = MySearchService(session)
    for ineligible_id in (wrong_role_id, wrong_work_id):
        with pytest.raises(SearchWorkspaceValidationError):
            service.track_opportunity(
                "search_user",
                TrackOpportunityInput(decision_id=decision_id, opportunity_id=ineligible_id),
            )

    decision = session.get(CareerDecision, decision_id)
    assert decision is not None
    decision.constraints = [
        {
            "key": "required_role_family",
            "field": "role_family",
            "operator": "equals",
            "value": "software_engineering",
            "hard": True,
        }
    ]
    session.flush()
    assert (
        opportunity_service.strategic_matches(
            "search_user", decision_id=decision_id, include_ineligible=False
        )
        == ()
    )


def test_repeated_action_plan_generation_reuses_one_active_plan_and_reader_is_robust(
    session: Session,
) -> None:
    _seed_foundation(session)
    decision_id = _seed_pursuit(session)
    service = _decision_service(session)

    first = service.create_action_plan("search_user", decision_id, ActionPlanCreateInput())
    first_action_ids = [item.action_id for item in first.actions]
    service.update_action(
        "search_user",
        first_action_ids[0],
        CareerActionUpdateInput(status="completed"),
    )
    repeated = service.create_action_plan("search_user", decision_id, ActionPlanCreateInput())

    assert repeated.action_plan_id == first.action_plan_id
    assert [item.action_id for item in repeated.actions] == first_action_ids
    assert repeated.actions[0].status == "completed"
    assert (
        session.query(CareerActionPlan).filter_by(decision_id=decision_id, status="active").count()
        == 1
    )
    assert service.decision_view("search_user", decision_id).action_plan is not None
    assert MySearchService(session).workspace("search_user").active_pursuits[0].next_action

    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            CareerActionPlan(
                action_plan_id="legacy_duplicate_plan",
                user_id="search_user",
                decision_id=decision_id,
                selected_option_id="option_boston_selected",
                title="Legacy duplicate",
                status="active",
                plan_payload={"legacy": True},
                created_at=NOW - timedelta(days=1),
                updated_at=NOW - timedelta(days=1),
            )
        )
        session.flush()
    assert service.decision_view("search_user", decision_id).action_plan is not None


def test_current_choice_match_is_derived_without_mutating_original_provenance(
    session: Session,
) -> None:
    _seed_foundation(session)
    decision_id = _seed_pursuit(session)
    _seed_comparison_and_saved(session, decision_id)
    service = _decision_service(session)

    initial = MySearchService(session).workspace("search_user").active_pursuits[0]
    assert initial.source_comparison is not None
    assert initial.source_comparison.original_user_choice == "Greater Boston"
    assert initial.source_comparison.current_user_choice == "Greater Boston"
    assert initial.source_comparison.current_choice_matches_recommendation is False

    service.select_option(
        "search_user",
        decision_id,
        OptionSelectInput(option_id="option_boston_alternate"),
    )
    matching = MySearchService(session).workspace("search_user").active_pursuits[0]
    assert matching.source_comparison is not None
    assert matching.source_comparison.original_user_choice == "Greater Boston"
    assert matching.source_comparison.original_choice_matches_recommendation is False
    assert matching.source_comparison.current_user_choice == "Greater New York"
    assert matching.source_comparison.current_choice_matches_recommendation is True

    provenance = session.execute(
        select(ExploreDecisionProvenance).where(
            ExploreDecisionProvenance.decision_id == decision_id
        )
    ).scalar_one()
    assert provenance.user_selected_region_id == "greater_boston"
    assert provenance.system_recommended_region_ids == ["greater_nyc"]
    assert provenance.choice_matches_recommendation is False

    service.select_option(
        "search_user",
        decision_id,
        OptionSelectInput(option_id="option_boston_selected"),
    )
    changed_back = MySearchService(session).workspace("search_user").active_pursuits[0]
    assert changed_back.source_comparison is not None
    assert changed_back.source_comparison.current_choice_matches_recommendation is False


@pytest.mark.parametrize("invalid_status", ["applied", "interview", "offer", "rejected"])
def test_track_api_rejects_later_initial_status_without_creating_application(
    api_client,
    session: Session,
    invalid_status: str,
) -> None:
    _current_user_id(api_client, "auth0|track-status")
    response = api_client.post(
        "/me/search-workspace/applications/track",
        headers=_auth_headers("auth0|track-status"),
        json={
            "decision_id": "decision-does-not-matter",
            "opportunity_id": "opportunity-does-not-matter",
            "initial_status": invalid_status,
        },
    )
    assert response.status_code == 422
    assert session.query(CareerApplication).count() == 0


def test_track_api_rejects_wrong_market_and_accepts_pre_submission_status(
    api_client,
    session: Session,
) -> None:
    user_id = _current_user_id(api_client, "auth0|track-market")
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                public_slug="boston",
                region_type="greater_region",
            ),
            Region(
                region_id="greater_nyc",
                region_name="greater_nyc",
                display_name="Greater New York",
                public_slug="new-york",
                region_type="greater_region",
            ),
            Company(
                company_id="company_acme",
                company_name="Acme AI",
                normalized_company_name="acme ai",
                sector_primary="ai",
            ),
        ]
    )
    session.flush()
    decision_id = _seed_pursuit(session, "api-market", user_id=user_id)
    boston_opportunity = _seed_current_opportunity(session)
    nyc_opportunity = _seed_current_opportunity(session, market_id="greater_nyc", suffix="nyc")
    headers = _auth_headers("auth0|track-market")

    rejected = api_client.post(
        "/me/search-workspace/applications/track",
        headers=headers,
        json={
            "decision_id": decision_id,
            "opportunity_id": nyc_opportunity,
            "initial_status": "preparing",
        },
    )
    assert rejected.status_code == 422
    assert session.query(CareerApplication).filter_by(user_id=user_id).count() == 0

    accepted = api_client.post(
        "/me/search-workspace/applications/track",
        headers=headers,
        json={
            "decision_id": decision_id,
            "opportunity_id": boston_opportunity,
            "initial_status": "considering",
        },
    )
    assert accepted.status_code == 201
    assert accepted.json()["data"]["application"]["status"] == "considering"


def test_manual_application_rolls_up_and_valid_transitions_remain_layer_36_owned(
    session: Session,
) -> None:
    _seed_foundation(session)
    decision_id = _seed_pursuit(session)
    service = _decision_service(session)
    manual = service.create_application(
        "search_user",
        ApplicationCreateInput(
            decision_id=decision_id,
            option_id="option_boston_selected",
            role_title="Technical Product Intern",
            status="preparing",
            source_url="https://manual.example/apply",
            metadata={"company_name": "Manual Labs", "location_text": "Cambridge"},
        ),
    )
    workspace = MySearchService(session, clock=lambda: NOW).workspace("search_user")
    pursuit = workspace.active_pursuits[0]
    assert pursuit.applications[0].application_id == manual.application_id
    assert pursuit.applications[0].company_name == "Manual Labs"
    assert pursuit.applications[0].status == "preparing"
    assert pursuit.applications[0].market_name == "Cambridge"

    applied = service.transition_application(
        "search_user",
        manual.application_id,
        ApplicationTransitionInput(to_status="applied", transitioned_at=NOW),
    )
    assert applied.status == "applied"
    transition = session.execute(
        select(CareerApplicationTransition).where(
            CareerApplicationTransition.application_id == manual.application_id,
            CareerApplicationTransition.from_status == "preparing",
        )
    ).scalar_one()
    assert transition.to_status == "applied"


def test_workspace_is_owner_scoped_and_query_count_is_bounded(session: Session) -> None:
    _seed_foundation(session)
    decision_ids = [_seed_pursuit(session, suffix) for suffix in ("boston", "nyc", "strategy")]
    for decision_index, decision_id in enumerate(decision_ids):
        plan = CareerActionPlan(
            action_plan_id=f"plan_performance_{decision_index}",
            user_id="search_user",
            decision_id=decision_id,
            selected_option_id=f"option_{('boston', 'nyc', 'strategy')[decision_index]}_selected",
            title=f"Performance plan {decision_index}",
            status="active",
            plan_payload={},
        )
        session.add(plan)
        session.flush()
        for item_index in range(4 if decision_index == 0 else 3):
            session.add(
                CareerAction(
                    action_id=f"action_performance_{decision_index}_{item_index}",
                    user_id="search_user",
                    action_plan_id=plan.action_plan_id,
                    decision_id=decision_id,
                    option_id=plan.selected_option_id,
                    action_type="research",
                    status="open",
                    title=f"Research step {decision_index + 1}.{item_index + 1}",
                    priority=item_index + 1,
                    position=item_index,
                    metadata_json={},
                )
            )
    for item_index in range(10):
        decision_index = item_index % len(decision_ids)
        session.add(
            CareerApplication(
                application_id=f"application_performance_{item_index}",
                user_id="search_user",
                decision_id=decision_ids[decision_index],
                option_id=(f"option_{('boston', 'nyc', 'strategy')[decision_index]}_selected"),
                company_id="company_acme",
                region_id="greater_boston" if decision_index != 1 else "greater_nyc",
                role_title=f"Product role {item_index + 1}",
                status="preparing" if item_index % 2 == 0 else "applied",
                status_started_at=NOW,
                metadata_json={"company_name": "Acme AI"},
            )
        )
    _seed_comparison_and_saved(session, decision_ids[0])
    _seed_current_opportunity(session)
    other_decision = _seed_pursuit(session, "other", user_id="other_user")
    session.add(
        CareerApplication(
            application_id="other_application",
            user_id="other_user",
            decision_id=other_decision,
            option_id="option_other_selected",
            role_title="Private role",
            status="preparing",
            status_started_at=NOW,
            metadata_json={"company_name": "Private Co"},
        )
    )
    session.flush()

    selects = 0

    def count_selects(_conn, _cursor, statement, _parameters, _context, _executemany):  # noqa: ANN001
        nonlocal selects
        if statement.lstrip().upper().startswith("SELECT"):
            selects += 1

    event.listen(session.bind, "before_cursor_execute", count_selects)
    try:
        workspace = MySearchService(session, clock=lambda: NOW).workspace("search_user")
    finally:
        event.remove(session.bind, "before_cursor_execute", count_selects)

    assert len(workspace.active_pursuits) == 3
    assert sum(item.open_action_count for item in workspace.active_pursuits) == 10
    assert len(workspace.applications) == 10
    assert len(workspace.saved_comparisons) == 1
    assert len(workspace.saved_items) == 1
    assert all(item.role_title != "Private role" for item in workspace.applications)
    assert selects == 17

    try:
        MySearchService(session).track_opportunity(
            "search_user",
            TrackOpportunityInput(
                decision_id=other_decision,
                opportunity_id="not-visible",
            ),
        )
    except SearchWorkspaceNotFound:
        pass
    else:
        raise AssertionError("cross-user pursuit access must be blocked")


def test_closing_pursuit_removes_it_from_active_without_deleting_history(session: Session) -> None:
    _seed_foundation(session)
    decision_id = _seed_pursuit(session)
    session.add(
        DecisionVersion(
            decision_version_id="version_selected",
            user_id="search_user",
            decision_id=decision_id,
            version_number=1,
            version_reason="option_selected",
            decision_snapshot={},
            options_snapshot=[{"option_id": "option_boston_selected", "title": "Greater Boston"}],
            selected_option_id="option_boston_selected",
            created_at=NOW,
        )
    )
    session.flush()
    before = MySearchService(session, clock=lambda: NOW).workspace("search_user")
    assert len(before.active_pursuits) == 1

    decision = session.get(CareerDecision, decision_id)
    assert decision is not None
    decision.status = "completed"
    decision.updated_at = NOW + timedelta(hours=1)
    session.flush()

    after = MySearchService(session, clock=lambda: NOW).workspace("search_user")
    assert after.active_pursuits == ()
    assert any(item.kind == "option_selected" for item in after.history)


def test_workspace_api_requires_auth_and_never_exposes_another_users_pursuit(
    api_client, session: Session
) -> None:
    user_a = _current_user_id(api_client, "auth0|search_a")
    _current_user_id(api_client, "auth0|search_b")
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                public_slug="boston",
                region_type="greater_region",
            ),
            Region(
                region_id="greater_nyc",
                region_name="greater_nyc",
                display_name="Greater New York",
                public_slug="new-york",
                region_type="greater_region",
            ),
        ]
    )
    session.flush()
    decision_id = _seed_pursuit(session, "api", user_id=user_a)

    assert api_client.get("/me/search-workspace").status_code == 401
    owner = api_client.get("/me/search-workspace", headers=_auth_headers("auth0|search_a"))
    assert owner.status_code == 200
    assert [item["decision_id"] for item in owner.json()["data"]["active_pursuits"]] == [
        decision_id
    ]

    other = api_client.get("/me/search-workspace", headers=_auth_headers("auth0|search_b"))
    assert other.status_code == 200
    assert other.json()["data"]["active_pursuits"] == []
    cross_user_write = api_client.post(
        "/me/search-workspace/applications/track",
        headers=_auth_headers("auth0|search_b"),
        json={"decision_id": decision_id, "opportunity_id": "not-visible"},
    )
    assert cross_user_write.status_code == 404
