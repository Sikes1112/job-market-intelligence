from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from backend.career_decisions.exceptions import (
    CareerDecisionTransitionError,
    CareerDecisionValidationError,
)
from backend.career_decisions.models import (
    CareerAction,
    CareerActionPlan,
    CareerApplication,
    CareerApplicationTransition,
    CareerDecision,
    CareerOutcome,
    DecisionContextSnapshot,
    DecisionOption,
    DecisionVersion,
)
from backend.career_decisions.repository import CareerDecisionRepository
from backend.career_decisions.schemas import (
    ActionPlanCreateInput,
    ApplicationCreateInput,
    ApplicationTransitionInput,
    CareerActionInput,
    CareerActionType,
    DecisionCreateInput,
    DecisionOptionInput,
    OptionSelectInput,
    OutcomeCreateInput,
)
from backend.career_decisions.service import CareerDecisionService
from backend.career_identity.repository import CareerIdentityRepository
from backend.career_identity.schemas import (
    CareerFactState,
    CareerFactType,
    CareerIdentityFactInput,
    CareerIdentityPrivacyInput,
)
from backend.career_identity.service import CareerIdentityService
from backend.companies.models import Company
from backend.companies.repository import CompanyRepository
from backend.geography.models import Region, RegionAlias
from backend.geography.repository import RegionRepository
from backend.scoring.models import RegionMarketScore
from backend.scoring.repository import RegionScoreRepository
from backend.users.exceptions import CrossUserAccessBlocked
from backend.users.models import User
from backend.users.repository import UserRepository


def _decision_service(session: Session) -> CareerDecisionService:
    return CareerDecisionService(
        CareerDecisionRepository(session),
        CareerIdentityRepository(session),
        UserRepository(session),
        RegionRepository(session),
        CompanyRepository(session),
        RegionScoreRepository(session),
    )


def _identity_service(session: Session) -> CareerIdentityService:
    return CareerIdentityService(CareerIdentityRepository(session), UserRepository(session))


def _seed_user(session: Session, user_id: str = "user_layer36") -> str:
    session.add(User(user_id=user_id))
    session.flush()
    return user_id


def _seed_market(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Region(
                region_id="seattle",
                region_name="seattle",
                display_name="Seattle",
                region_type="metro",
            ),
            Company(
                company_id="acme_ai",
                company_name="Acme AI",
                normalized_company_name="acme ai",
                sector_primary="ai",
                classification_confidence="high_confidence",
            ),
            Company(
                company_id="weakco",
                company_name="WeakCo",
                normalized_company_name="weakco",
                sector_primary="software",
                classification_confidence="unknown",
            ),
            RegionMarketScore(
                region_score_id="score_boston",
                region_id="greater_boston",
                objective_opportunity_score=0.82,
                raw_total_score=0.82,
            ),
        ]
    )
    session.flush()


def _seed_identity(session: Session, user_id: str, *, consent: bool = True) -> None:
    service = _identity_service(session)
    service.get_or_create_identity(user_id)
    service.update_privacy(
        user_id,
        CareerIdentityPrivacyInput(
            ingestion_consent_granted=True,
            inference_consent_granted=True,
            downstream_personalization_consent_granted=consent,
        ),
    )
    service.upsert_fact(
        user_id,
        CareerIdentityFactInput(
            fact_type=CareerFactType.SKILL,
            payload={"name": "Product analytics"},
            state=CareerFactState.CONFIRMED,
        ),
    )
    service.upsert_fact(
        user_id,
        CareerIdentityFactInput(
            fact_type=CareerFactType.ROLE_PREFERENCE,
            payload={"role_title": "Product Management"},
            state=CareerFactState.CONFIRMED,
        ),
    )
    service.upsert_fact(
        user_id,
        CareerIdentityFactInput(
            fact_type=CareerFactType.INDUSTRY_PREFERENCE,
            payload={"industry": "AI", "preference_kind": "preferred"},
            state=CareerFactState.EXPLICIT,
        ),
    )
    service.upsert_fact(
        user_id,
        CareerIdentityFactInput(
            fact_type=CareerFactType.COMPENSATION_CONSTRAINT,
            payload={"minimum_amount": 110000, "target_amount": 140000},
            state=CareerFactState.EXPLICIT,
        ),
    )


def _decision_request() -> DecisionCreateInput:
    return DecisionCreateInput(
        decision_type="career_path",
        title="Choose next product path",
        planned_review_at=datetime.now(UTC) + timedelta(days=3),
        priorities=(
            {"key": "role_growth", "weight": 5},
            {"key": "compensation", "weight": 4},
        ),
        constraints=(
            {
                "key": "minimum_compensation",
                "field": "compensation_min",
                "operator": "gte",
                "value": 110000,
                "hard": True,
            },
        ),
        options=(
            DecisionOptionInput(
                title="Boston AI product",
                scenario={
                    "roles": ["Product Management"],
                    "region_ids": ["greater_boston"],
                    "company_ids": ["acme_ai"],
                    "industries": ["AI"],
                    "work_arrangement": "hybrid",
                    "compensation_min": 125000,
                },
            ),
            DecisionOptionInput(
                title="Seattle broad search",
                scenario={
                    "roles": ["Operations"],
                    "region_ids": ["seattle"],
                    "company_ids": ["weakco"],
                    "industries": ["Software"],
                    "compensation_min": 90000,
                },
            ),
        ),
    )


def test_decision_to_outcome_lifecycle_preserves_context_history_and_review(
    session: Session,
) -> None:
    user_id = _seed_user(session)
    _seed_market(session)
    _seed_identity(session, user_id)
    service = _decision_service(session)

    decision = service.create_decision(user_id, _decision_request())
    assert decision.context is not None
    assert decision.context.context["consent"]["usable"] is True
    assert decision.context.context["role_preferences"] == ["Product Management"]
    assert len(decision.options) == 2

    recommendation = service.compare_decision(user_id, decision.decision_id)
    assert recommendation.recommendation_status == "ready"
    assert recommendation.recommended_option_id == decision.options[0].option_id
    assert recommendation.evidence_sufficiency == "limited_evidence"
    boston_fit = next(
        item for item in recommendation.fit["options"] if item["title"] == "Boston AI product"
    )
    market_dimension = next(
        item for item in boston_fit["dimensions"] if item["name"] == "market_fit"
    )
    assert market_dimension["assessment"] == "strong"
    assert any(
        challenge["code"] == "compensation_minimum_violation"
        for challenge in recommendation.challenges
    )
    selected = service.select_option(
        user_id,
        decision.decision_id,
        OptionSelectInput(
            option_id=decision.options[0].option_id, user_note="Best supported path."
        ),
    )
    assert selected.status == "decided"
    assert selected.selected_option_id == decision.options[0].option_id

    reopened = service.reopen_decision(
        user_id, decision.decision_id, user_note="New information arrived."
    )
    assert reopened.status == "reconsidering"
    journal = service.journal(user_id, decision.decision_id)
    assert [entry.version_reason for entry in journal] == [
        "created",
        "recommendation_generated",
        "option_selected",
        "reopened",
    ]
    assert journal[2].selected_option_id == decision.options[0].option_id
    assert journal[2].recommendation_snapshot is not None

    plan = service.create_action_plan(user_id, decision.decision_id, ActionPlanCreateInput())
    assert plan.selected_option_id == decision.options[0].option_id
    assert {action.action_type for action in plan.actions} >= {
        "research",
        "preparation",
        "review_task",
    }

    app_action = plan.actions[1]
    application = service.create_application(
        user_id,
        ApplicationCreateInput(
            decision_id=decision.decision_id,
            action_id=app_action.action_id,
            option_id=decision.options[0].option_id,
            company_id="acme_ai",
            region_id="greater_boston",
            role_title="Product Manager",
            status="applied",
            follow_up_at=datetime.now(UTC) + timedelta(days=5),
        ),
    )
    assert application.status == "applied"
    assert len(application.transitions) == 1

    rejected = service.transition_application(
        user_id,
        application.application_id,
        ApplicationTransitionInput(to_status="rejected", reason="No interview loop."),
    )
    assert rejected.status == "rejected"
    assert [transition.to_status for transition in rejected.transitions] == ["applied", "rejected"]

    outcome = service.create_outcome(
        user_id,
        OutcomeCreateInput(
            outcome_type="rejection",
            title="Acme AI rejected application",
            application_id=application.application_id,
            recommendation_id=recommendation.recommendation_id,
            reflection="Need stronger domain examples.",
            metadata={"invalidated_assumptions": ["company was an accessible near-term target"]},
        ),
    )
    assert outcome.decision_id == decision.decision_id
    assert outcome.option_id == decision.options[0].option_id
    assert outcome.recommendation_id == recommendation.recommendation_id

    review = service.weekly_review(user_id)
    assert any(item["id"] == outcome.outcome_id for item in review.did_not_work)
    assert any(item["type"] == "decision_review" for item in review.reminders)
    assert any(item["invalidated_assumptions"] for item in review.invalidated_assumptions)

    final_journal = service.journal(user_id, decision.decision_id)
    assert final_journal[-1].version_reason == "outcome_recorded"
    assert session.query(CareerOutcome).count() == 1


@pytest.mark.parametrize(
    ("normalized_score", "expected_assessment"),
    ((0.82, "strong"), (0.62, "moderate"), (0.32, "weak")),
)
def test_layer36_market_fit_uses_normalized_score_scale_across_all_bands(
    session: Session,
    normalized_score: float,
    expected_assessment: str,
) -> None:
    user_id = _seed_user(session, f"scale_{str(normalized_score).replace('.', '_')}")
    _seed_market(session)
    score = session.get(RegionMarketScore, "score_boston")
    assert score is not None
    score.objective_opportunity_score = normalized_score
    score.raw_total_score = normalized_score
    _seed_identity(session, user_id)
    service = _decision_service(session)

    decision = service.create_decision(user_id, _decision_request())
    recommendation = service.compare_decision(user_id, decision.decision_id)
    boston_fit = next(
        item for item in recommendation.fit["options"] if item["title"] == "Boston AI product"
    )
    market_dimension = next(
        item for item in boston_fit["dimensions"] if item["name"] == "market_fit"
    )
    assert market_dimension["assessment"] == expected_assessment


def test_context_without_personalization_consent_abstains_and_hides_facts(
    session: Session,
) -> None:
    user_id = _seed_user(session, "no_consent_user")
    _seed_market(session)
    _seed_identity(session, user_id, consent=False)
    service = _decision_service(session)

    decision = service.create_decision(user_id, _decision_request())
    recommendation = service.compare_decision(user_id, decision.decision_id)

    assert decision.context is not None
    assert decision.context.context["consent"]["usable"] is False
    assert decision.context.fact_refs == ()
    assert recommendation.recommendation_status == "abstained"
    assert recommendation.evidence_sufficiency == "insufficient_evidence"
    assert recommendation.recommended_option_id is None


def test_legacy_decision_geography_is_resolved_without_rewriting_scenario(
    session: Session,
) -> None:
    user_id = _seed_user(session, "legacy_geo_decision_user")
    _seed_market(session)
    _seed_identity(session, user_id)
    session.add(
        RegionAlias(
            region_alias_id="legacy_boston_alias",
            region_id="greater_boston",
            alias="Boston-Cambridge",
            normalized_alias="boston cambridge",
            alias_type="alternate_name",
        )
    )
    session.flush()
    service = _decision_service(session)
    decision = service.create_decision(user_id, _decision_request())
    option = session.get(DecisionOption, decision.options[0].option_id)
    option.scenario = {**option.scenario, "region_ids": ["Boston-Cambridge"]}
    session.flush()

    recommendation = service.compare_decision(user_id, decision.decision_id)

    session.refresh(option)
    assert option.scenario["region_ids"] == ["Boston-Cambridge"]
    assert any(
        evidence["reference_type"] == "region_market_score"
        and evidence["reference_id"] == "greater_boston"
        for evidence in recommendation.evidence["supporting"]
    )


def test_new_application_alias_is_persisted_as_canonical_region_id(
    session: Session,
) -> None:
    user_id = _seed_user(session, "canonical_application_geo_user")
    _seed_market(session)
    _seed_identity(session, user_id)
    session.add(
        RegionAlias(
            region_alias_id="application_boston_alias",
            region_id="greater_boston",
            alias="Boston",
            normalized_alias="boston",
            alias_type="city_alias",
        )
    )
    session.flush()
    service = _decision_service(session)

    application = service.create_application(
        user_id,
        ApplicationCreateInput(region_id="Boston", role_title="Product Manager"),
    )

    assert application.region_id == "greater_boston"


def test_new_decision_region_ids_are_persisted_canonically(session: Session) -> None:
    user_id = _seed_user(session, "canonical_decision_geo_user")
    _seed_market(session)
    _seed_identity(session, user_id)
    session.add(
        RegionAlias(
            region_alias_id="decision_boston_alias",
            region_id="greater_boston",
            alias="Boston-Cambridge",
            normalized_alias="boston cambridge",
            alias_type="alternate_name",
        )
    )
    session.flush()
    service = _decision_service(session)

    decision = service.create_decision(
        user_id,
        DecisionCreateInput(
            decision_type="job_search_strategy",
            title="Canonical geography decision",
            options=(
                DecisionOptionInput(
                    title="Boston option",
                    scenario={"region_ids": ["Boston-Cambridge"]},
                ),
            ),
        ),
    )

    assert decision.options[0].scenario["region_ids"] == ["greater_boston"]


def test_ownership_and_cross_decision_option_invariants(session: Session) -> None:
    user_a = _seed_user(session, "owner_a")
    user_b = _seed_user(session, "owner_b")
    _seed_market(session)
    _seed_identity(session, user_a)
    _seed_identity(session, user_b)
    service = _decision_service(session)
    decision_a = service.create_decision(user_a, _decision_request())
    decision_b = service.create_decision(user_b, _decision_request())

    with pytest.raises(CrossUserAccessBlocked):
        service.decision_view(user_b, decision_a.decision_id)

    with pytest.raises(CrossUserAccessBlocked):
        service.select_option(
            user_a,
            decision_a.decision_id,
            OptionSelectInput(option_id=decision_b.options[0].option_id),
        )


def test_invalid_nested_plan_write_does_not_create_orphan_rows(session: Session) -> None:
    user_id = _seed_user(session, "transaction_user")
    _seed_market(session)
    _seed_identity(session, user_id)
    service = _decision_service(session)
    decision_a = service.create_decision(user_id, _decision_request())
    decision_b = service.create_decision(user_id, _decision_request())

    with pytest.raises(CrossUserAccessBlocked):
        service.create_action_plan(
            user_id,
            decision_a.decision_id,
            ActionPlanCreateInput(
                actions=(
                    CareerActionInput(
                        action_type=CareerActionType.APPLICATION,
                        title="Invalid cross-decision action",
                        option_id=decision_b.options[0].option_id,
                    ),
                )
            ),
        )

    assert session.query(CareerActionPlan).count() == 0
    assert session.query(CareerAction).count() == 0


def test_application_transitions_allow_direct_rejection_and_reject_nonsense(
    session: Session,
) -> None:
    user_id = _seed_user(session, "application_user")
    service = _decision_service(session)
    application = service.create_application(
        user_id,
        ApplicationCreateInput(role_title="Analyst", status="applied"),
    )

    rejected = service.transition_application(
        user_id,
        application.application_id,
        ApplicationTransitionInput(to_status="rejected"),
    )
    assert rejected.status == "rejected"
    assert session.query(CareerApplicationTransition).count() == 2

    with pytest.raises(CareerDecisionTransitionError):
        service.transition_application(
            user_id,
            application.application_id,
            ApplicationTransitionInput(to_status="offer"),
        )


def _auth_headers(subject: str) -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"User {suffix}",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def test_career_decision_api_flow_and_owner_boundary(api_client, session: Session) -> None:
    _seed_market(session)
    owner_headers = _auth_headers("auth0|layer36_api_owner")
    other_headers = _auth_headers("auth0|layer36_api_other")
    owner_id = api_client.get("/me", headers=owner_headers).json()["data"]["user"]["user_id"]
    api_client.get("/me", headers=other_headers)
    _seed_identity(session, owner_id)

    created = api_client.post(
        "/me/decisions",
        headers=owner_headers,
        json=_decision_request().model_dump(mode="json"),
    )
    assert created.status_code == 201
    decision = created.json()["data"]["decision"]
    decision_id = decision["decision_id"]

    forbidden = api_client.get(f"/me/decisions/{decision_id}", headers=other_headers)
    assert forbidden.status_code == 404

    compared = api_client.post(f"/me/decisions/{decision_id}/compare", headers=owner_headers)
    assert compared.status_code == 200
    recommendation = compared.json()["data"]["recommendation"]
    assert recommendation["recommended_option_id"] == decision["options"][0]["option_id"]

    selected = api_client.post(
        f"/me/decisions/{decision_id}/select",
        headers=owner_headers,
        json={"option_id": decision["options"][0]["option_id"], "user_note": "Select A."},
    )
    assert selected.status_code == 200

    planned = api_client.post(
        f"/me/decisions/{decision_id}/plan",
        headers=owner_headers,
        json={},
    )
    assert planned.status_code == 201
    action = planned.json()["data"]["action_plan"]["actions"][0]

    application = api_client.post(
        "/me/applications",
        headers=owner_headers,
        json={
            "decision_id": decision_id,
            "action_id": action["action_id"],
            "option_id": decision["options"][0]["option_id"],
            "status": "applied",
            "role_title": "Product Manager",
        },
    )
    assert application.status_code == 201
    application_id = application.json()["data"]["application"]["application_id"]

    outcome = api_client.post(
        "/me/outcomes",
        headers=owner_headers,
        json={
            "outcome_type": "offer",
            "title": "Offer received",
            "application_id": application_id,
            "recommendation_id": recommendation["recommendation_id"],
        },
    )
    assert outcome.status_code == 201

    review = api_client.get("/me/reviews/weekly", headers=owner_headers)
    assert review.status_code == 200
    assert review.json()["data"]["review"]["worked"]


def test_compare_validation_failure_does_not_create_context_snapshot(session: Session) -> None:
    user_id = _seed_user(session, "empty_decision_user")
    service = _decision_service(session)
    decision = service.create_decision(
        user_id,
        DecisionCreateInput(decision_type="role_choice", title="Empty option decision"),
    )
    before = session.query(DecisionContextSnapshot).count()

    with pytest.raises(CareerDecisionValidationError):
        service.compare_decision(user_id, decision.decision_id)

    assert session.query(DecisionContextSnapshot).count() == before
    assert session.query(CareerDecision).count() == 1
    assert session.query(DecisionVersion).count() == 1
    assert session.query(CareerApplication).count() == 0
