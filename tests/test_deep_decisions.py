from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from backend.career_decisions.repository import CareerDecisionRepository
from backend.career_decisions.schemas import (
    ApplicationCreateInput,
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
from backend.deep_decisions.models import (
    DecisionFactor,
    LongitudinalContextSnapshot,
    RecommendationEvolution,
    StrategicCareerReview,
)
from backend.deep_decisions.repository import DeepDecisionRepository
from backend.deep_decisions.schemas import DeepDecisionAnalysisRequest
from backend.deep_decisions.service import DeepDecisionService
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region, RegionAlias
from backend.geography.repository import RegionRepository
from backend.hiring.models import CompanyRegionHiring
from backend.presence.models import CompanyRegionPresence
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


def _deep_service(session: Session) -> DeepDecisionService:
    return DeepDecisionService(
        session,
        DeepDecisionRepository(session),
        CareerDecisionRepository(session),
        UserRepository(session),
    )


def _identity_service(session: Session) -> CareerIdentityService:
    return CareerIdentityService(CareerIdentityRepository(session), UserRepository(session))


def _seed_user(session: Session, user_id: str = "layer37_user") -> str:
    session.add(User(user_id=user_id))
    session.flush()
    return user_id


def _seed_identity(session: Session, user_id: str) -> None:
    service = _identity_service(session)
    service.get_or_create_identity(user_id)
    service.update_privacy(
        user_id,
        CareerIdentityPrivacyInput(
            ingestion_consent_granted=True,
            inference_consent_granted=True,
            downstream_personalization_consent_granted=True,
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
            payload={"role_title": "Applied AI Product"},
            state=CareerFactState.CONFIRMED,
        ),
    )
    service.upsert_fact(
        user_id,
        CareerIdentityFactInput(
            fact_type=CareerFactType.CAREER_GOAL,
            payload={
                "goal_type": "near_term_objective",
                "description": "Move into applied AI product leadership",
                "priority": 5,
            },
            state=CareerFactState.EXPLICIT,
        ),
    )


def _seed_market(session: Session, *, stale: bool = False) -> None:
    expires_at = (
        datetime.now(UTC) - timedelta(days=1) if stale else datetime.now(UTC) + timedelta(days=30)
    )
    session.add_all(
        [
            Region(
                region_id="boston",
                region_name="boston",
                display_name="Boston",
                region_type="metro",
            ),
            Region(
                region_id="remote_us",
                region_name="remote_us",
                display_name="Remote US",
                region_type="remote",
            ),
            Company(
                company_id="acme_ai",
                company_name="Acme AI",
                normalized_company_name="acme ai",
                sector_primary="ai",
                classification_confidence="high_confidence",
            ),
            Company(
                company_id="profile_only",
                company_name="Profile Only",
                normalized_company_name="profile only",
                sector_primary="software",
                classification_confidence="low",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id="presence_acme_boston",
                company_id="acme_ai",
                region_id="boston",
                presence_status="present",
                hiring_evidence_flag=True,
                presence_confidence="medium",
            ),
            CompanyRegionHiring(
                hiring_id="hiring_acme_boston",
                company_id="acme_ai",
                region_id="boston",
                currently_hiring_flag=True,
                active_posting_count_now=12,
                role_family_summary={"product": 7, "ai": 5},
                hiring_confidence="medium",
                freshness_expires_at=expires_at,
            ),
            CompanyRegionEntryLevel(
                entry_level_id="entry_acme_boston",
                company_id="acme_ai",
                region_id="boston",
                entry_level_full_time_count=3,
                formal_early_career_program_flag=True,
                entry_level_access_score=64.0,
                freshness_expires_at=expires_at,
            ),
            RegionMarketScore(
                region_score_id="score_boston",
                region_id="boston",
                objective_opportunity_score=78.0,
                raw_total_score=78.0,
                early_career_accessibility_score=62.0,
            ),
        ]
    )
    session.flush()


def _decision_request() -> DecisionCreateInput:
    return DecisionCreateInput(
        decision_type="career_path",
        title="Choose a deeper AI product path",
        priorities=(
            {"key": "role_fit", "weight": 5},
            {"key": "compensation", "weight": 4},
            {"key": "learning_speed", "weight": 3},
        ),
        constraints=(
            {
                "key": "minimum_compensation",
                "field": "compensation_min",
                "operator": "gte",
                "value": 120000,
                "hard": True,
            },
        ),
        options=(
            DecisionOptionInput(
                title="Boston AI product offer",
                scenario={
                    "roles": ["Applied AI Product"],
                    "region_ids": ["boston"],
                    "company_ids": ["acme_ai"],
                    "required_skills": ["Product analytics", "ML systems"],
                    "base_salary": 135000,
                    "total_compensation": 155000,
                    "benefits": {"health": "known"},
                    "education_type": "targeted course",
                    "education_cost": 1500,
                    "duration_months": 2,
                    "skills_taught": ["ML systems"],
                    "relocation_required": True,
                    "cost_of_living_index": 128,
                    "work_arrangement": "hybrid",
                    "compensation_min": 135000,
                },
            ),
            DecisionOptionInput(
                title="Remote broad software search",
                scenario={
                    "roles": ["Software Engineer"],
                    "region_ids": ["remote_us"],
                    "company_ids": ["profile_only"],
                    "required_skills": ["Distributed systems"],
                    "compensation_source": "estimate",
                    "base_salary": 110000,
                    "total_compensation": 190000,
                    "education_type": "masters",
                    "program_cost": 72000,
                    "duration_months": 24,
                    "relocation": False,
                    "work_arrangement": "remote",
                    "compensation_min": 110000,
                },
            ),
            DecisionOptionInput(
                title="Unpriced relocation experiment",
                scenario={
                    "roles": ["Product Strategy"],
                    "location": "unknown_region",
                    "relocation_required": True,
                    "required_skills": ["Market sizing"],
                },
            ),
        ),
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


def test_deep_analysis_reuses_layer36_decision_and_produces_shared_factors(
    session: Session,
) -> None:
    user_id = _seed_user(session)
    _seed_identity(session, user_id)
    _seed_market(session, stale=True)
    decision_service = _decision_service(session)
    decision = decision_service.create_decision(user_id, _decision_request())
    recommendation = decision_service.compare_decision(user_id, decision.decision_id)

    analysis = _deep_service(session).generate_analysis(
        user_id,
        decision.decision_id,
        DeepDecisionAnalysisRequest(),
    )

    assert analysis.decision_id == decision.decision_id
    assert {factor.domain for factor in analysis.factors} >= {
        "company",
        "compensation",
        "skill_gap",
        "education_roi",
        "relocation",
        "timing_pivot",
    }
    assert all(
        factor.recommendation_id == recommendation.recommendation_id for factor in analysis.factors
    )
    assert any(
        factor.category == "cost" and factor.factor_key == "education_cost"
        for factor in analysis.factors
    )
    assert any(
        factor.evidence_kind == "conflicting"
        and factor.factor_key == "conflicting_compensation_sources"
        for factor in analysis.factors
    )
    assert any(
        factor.evidence_kind == "proxy" and factor.source_id == "profile_only"
        for factor in analysis.factors
    )
    assert any(factor.freshness_status == "stale" for factor in analysis.factors)
    assert any(
        "not a confirmed absence" in factor.explanation
        for factor in analysis.factors
        if factor.factor_key == "likely_skill_gaps"
    )
    assert analysis.longitudinal_context.evidence["bounded"] is True
    assert "does not overwrite explicit intent" in analysis.longitudinal_context.evidence["safety"]
    assert analysis.recommendation_evolution is not None
    assert (
        analysis.recommendation_evolution.evidence_basis[
            "prior_recommendations_are_not_independent_evidence"
        ]
        is True
    )


def test_deep_decision_resolves_historical_region_alias_like_layer36(
    session: Session,
) -> None:
    user_id = _seed_user(session)
    _seed_identity(session, user_id)
    _seed_market(session)
    session.add(
        RegionAlias(
            region_alias_id="legacy_greater_boston",
            region_id="boston",
            alias="greater_boston",
            normalized_alias="greater boston",
            alias_type="legacy_id",
        )
    )
    session.flush()
    decision_service = _decision_service(session)
    decision = decision_service.create_decision(user_id, _decision_request())
    option = decision.options[0]
    option_row = CareerDecisionRepository(session).get_option(option.option_id)
    assert option_row is not None
    historical_scenario = dict(option_row.scenario)
    historical_scenario["region_ids"] = ["greater_boston"]
    option_row.scenario = historical_scenario
    session.flush()

    recommendation = decision_service.compare_decision(user_id, decision.decision_id)
    analysis = _deep_service(session).generate_analysis(user_id, decision.decision_id)

    assert recommendation.recommendation_id
    factor = next(
        factor
        for factor in analysis.factors
        if factor.factor_key == "regional_market_opportunity"
        and factor.option_id == option.option_id
    )
    assert factor.source_id == "boston"
    assert factor.normalized_value["canonical_region_id"] == "boston"
    assert factor.normalized_value["historical_region_reference"] == "greater_boston"
    assert option_row.scenario["region_ids"] == ["greater_boston"]


def test_contradictory_outcomes_preserve_uncertainty_in_strategic_review(
    session: Session,
) -> None:
    user_id = _seed_user(session, "layer37_contradictory")
    _seed_identity(session, user_id)
    _seed_market(session)
    decision_service = _decision_service(session)
    decision = decision_service.create_decision(user_id, _decision_request())
    recommendation = decision_service.compare_decision(user_id, decision.decision_id)
    option_id = recommendation.recommended_option_id
    assert option_id is not None
    statuses = ["offer", "rejected", "rejected", "withdrawn"]
    for index, status in enumerate(statuses):
        app = decision_service.create_application(
            user_id,
            ApplicationCreateInput(
                decision_id=decision.decision_id,
                option_id=option_id,
                company_id="acme_ai",
                region_id="boston",
                role_title=f"Applied AI Product {index}",
                status=status,
            ),
        )
        decision_service.create_outcome(
            user_id,
            OutcomeCreateInput(
                outcome_type="offer" if status == "offer" else "rejection",
                title=f"Application {status}",
                application_id=app.application_id,
                recommendation_id=recommendation.recommendation_id,
            ),
        )

    analysis = _deep_service(session).generate_analysis(user_id, decision.decision_id)

    assert analysis.strategic_review.application_summary["offer"] == 1
    assert analysis.strategic_review.application_summary["rejected"] == 2
    assert analysis.strategic_review.application_summary["withdrawn"] == 1
    assert analysis.strategic_review.uncertainty in {"medium", "high"}
    assert "Strategy failed" not in str(analysis.strategic_review.model_dump())


def test_many_old_behavior_records_do_not_overwrite_current_explicit_intent(
    session: Session,
) -> None:
    user_id = _seed_user(session, "layer37_temporal_dominance")
    _seed_identity(session, user_id)
    _seed_market(session)
    decision_service = _decision_service(session)
    decision = decision_service.create_decision(user_id, _decision_request())
    recommendation = decision_service.compare_decision(user_id, decision.decision_id)
    second_option_id = decision.options[1].option_id
    for index in range(35):
        decision_service.create_application(
            user_id,
            ApplicationCreateInput(
                decision_id=decision.decision_id,
                option_id=second_option_id,
                company_id="profile_only",
                region_id="remote_us",
                role_title=f"Software Engineer old route {index}",
                status="rejected",
            ),
        )

    analysis = _deep_service(session).generate_analysis(user_id, decision.decision_id)
    explicit_intent = analysis.longitudinal_context.context["explicit_intent"]
    observed_behavior = analysis.longitudinal_context.context["observed_behavior"]

    assert recommendation.recommended_option_id != second_option_id
    assert explicit_intent["role_preferences"] == ["Applied AI Product"]
    assert observed_behavior["applications"][0]["role_title"].startswith("Software Engineer")
    assert explicit_intent != observed_behavior
    assert "does not overwrite explicit intent" in analysis.longitudinal_context.evidence["safety"]
    assert analysis.strategic_review.active_risks

    assert session.query(DecisionFactor).count() == len(analysis.factors)
    assert session.query(LongitudinalContextSnapshot).count() == 1
    assert session.query(RecommendationEvolution).count() == 1
    assert session.query(StrategicCareerReview).count() == 1


def test_sparse_history_and_unknown_evidence_do_not_generate_unsupported_blind_spots(
    session: Session,
) -> None:
    user_id = _seed_user(session, "layer37_sparse")
    service = _decision_service(session)
    decision = service.create_decision(
        user_id,
        DecisionCreateInput(
            decision_type="career_strategy",
            title="Sparse strategy decision",
            options=(DecisionOptionInput(title="Explore", scenario={}),),
        ),
    )

    analysis = _deep_service(session).generate_analysis(user_id, decision.decision_id)

    assert analysis.recommendation_evolution is None
    assert analysis.advisory_findings == ()
    assert any(
        factor.evidence_kind == "unavailable" and factor.evidence_strength == "unavailable"
        for factor in analysis.factors
    )
    assert (
        analysis.longitudinal_context.context["explicit_intent"]["decision_title"] == decision.title
    )


def test_advisor_distinguishes_stated_intent_from_observed_behavior(
    session: Session,
) -> None:
    user_id = _seed_user(session, "layer37_advisor")
    _seed_identity(session, user_id)
    _seed_market(session)
    decision_service = _decision_service(session)
    decision = decision_service.create_decision(user_id, _decision_request())
    recommendation = decision_service.compare_decision(user_id, decision.decision_id)
    second_option_id = decision.options[1].option_id
    decision_service.select_option(
        user_id,
        decision.decision_id,
        OptionSelectInput(option_id=second_option_id, user_note="Prefer remote flexibility."),
    )
    for index in range(3):
        decision_service.create_application(
            user_id,
            ApplicationCreateInput(
                decision_id=decision.decision_id,
                option_id=second_option_id,
                company_id="profile_only",
                region_id="remote_us",
                role_title=f"Software Engineer {index}",
                status="rejected",
            ),
        )

    analysis = _deep_service(session).generate_analysis(user_id, decision.decision_id)
    finding_types = {finding.finding_type for finding in analysis.advisory_findings}

    assert recommendation.recommended_option_id != second_option_id
    assert "stated_goal_behavior_mismatch" in finding_types
    assert "repeated_rejection_pattern" in finding_types
    assert "recommendation_repeatedly_ignored" in finding_types
    context = analysis.longitudinal_context.context
    assert context["explicit_intent"]["role_preferences"] == ["Applied AI Product"]
    assert context["observed_behavior"]["selected_option_id"] == second_option_id
    assert context["explicit_intent"] != context["observed_behavior"]


def test_recommendation_evolution_classifies_confidence_and_context_changes(
    session: Session,
) -> None:
    user_id = _seed_user(session, "layer37_evolution")
    _seed_identity(session, user_id)
    _seed_market(session)
    decision_service = _decision_service(session)
    decision = decision_service.create_decision(user_id, _decision_request())
    first = decision_service.compare_decision(user_id, decision.decision_id)
    _identity_service(session).upsert_fact(
        user_id,
        CareerIdentityFactInput(
            fact_type=CareerFactType.GEOGRAPHIC_CONSTRAINT,
            payload={"location": "Remote US", "constraint_kind": "target"},
            state=CareerFactState.EXPLICIT,
        ),
    )
    second = decision_service.compare_decision(user_id, decision.decision_id)

    analysis = _deep_service(session).generate_analysis(user_id, decision.decision_id)

    assert first.recommendation_id != second.recommendation_id
    assert analysis.recommendation_evolution is not None
    assert analysis.recommendation_evolution.previous_recommendation_id == first.recommendation_id
    assert analysis.recommendation_evolution.current_recommendation_id == second.recommendation_id
    assert any(
        change["type"] in {"context_snapshot_changed", "confidence_changed"}
        for change in analysis.recommendation_evolution.meaningful_changes
    )


def test_deep_decision_api_auth_and_owner_boundaries(api_client, session: Session) -> None:
    _seed_market(session)
    owner_headers = _auth_headers("auth0|layer37_owner")
    other_headers = _auth_headers("auth0|layer37_other")
    owner_id = api_client.get("/me", headers=owner_headers).json()["data"]["user"]["user_id"]
    api_client.get("/me", headers=other_headers)
    _seed_identity(session, owner_id)
    created = api_client.post(
        "/me/decisions",
        headers=owner_headers,
        json=_decision_request().model_dump(mode="json"),
    )
    assert created.status_code == 201
    decision_id = created.json()["data"]["decision"]["decision_id"]
    compared = api_client.post(f"/me/decisions/{decision_id}/compare", headers=owner_headers)
    assert compared.status_code == 200

    unauthenticated = api_client.post(
        f"/me/decisions/{decision_id}/deep-analysis",
        json={},
    )
    assert unauthenticated.status_code == 401

    forbidden = api_client.post(
        f"/me/decisions/{decision_id}/deep-analysis",
        headers=other_headers,
        json={},
    )
    assert forbidden.status_code == 404

    generated = api_client.post(
        f"/me/decisions/{decision_id}/deep-analysis",
        headers=owner_headers,
        json={"include_domains": ["company", "compensation", "skill_gap"]},
    )
    assert generated.status_code == 201
    analysis = generated.json()["data"]["analysis"]
    assert analysis["decision_id"] == decision_id
    assert {factor["domain"] for factor in analysis["factors"]} == {
        "company",
        "compensation",
        "skill_gap",
    }

    latest = api_client.get(f"/me/decisions/{decision_id}/deep-analysis", headers=owner_headers)
    assert latest.status_code == 200
    reviews = api_client.get(
        "/me/strategic-reviews",
        headers=owner_headers,
        params={"decision_id": decision_id},
    )
    assert reviews.status_code == 200
    assert reviews.json()["data"]["strategic_reviews"][0]["decision_id"] == decision_id


def test_deep_decision_service_rejects_cross_user_decisions(session: Session) -> None:
    owner_id = _seed_user(session, "layer37_owner_service")
    other_id = _seed_user(session, "layer37_other_service")
    decision = _decision_service(session).create_decision(
        owner_id,
        DecisionCreateInput(
            decision_type="offer_comparison",
            title="Owner decision",
            options=(DecisionOptionInput(title="Offer", scenario={}),),
        ),
    )

    with pytest.raises(CrossUserAccessBlocked):
        _deep_service(session).generate_analysis(other_id, decision.decision_id)


def test_outcomes_feed_strategic_review_without_becoming_self_validating_evidence(
    session: Session,
) -> None:
    user_id = _seed_user(session, "layer37_outcomes")
    _seed_identity(session, user_id)
    _seed_market(session)
    decision_service = _decision_service(session)
    decision = decision_service.create_decision(user_id, _decision_request())
    recommendation = decision_service.compare_decision(user_id, decision.decision_id)
    decision_service.select_option(
        user_id,
        decision.decision_id,
        OptionSelectInput(option_id=recommendation.recommended_option_id),
    )
    application = decision_service.create_application(
        user_id,
        ApplicationCreateInput(
            decision_id=decision.decision_id,
            option_id=recommendation.recommended_option_id,
            company_id="acme_ai",
            region_id="boston",
            role_title="Applied AI Product Manager",
            status="offer",
        ),
    )
    decision_service.create_outcome(
        user_id,
        OutcomeCreateInput(
            outcome_type="offer",
            title="Offer received",
            application_id=application.application_id,
            recommendation_id=recommendation.recommendation_id,
            reflection="The applied AI product path converted to an offer.",
        ),
    )

    analysis = _deep_service(session).generate_analysis(user_id, decision.decision_id)

    assert analysis.strategic_review.outcome_summary["offer"] == 1
    assert analysis.strategic_review.application_summary["offer"] == 1
    assert all(
        finding.finding_type != "recommendation_repeatedly_ignored"
        for finding in analysis.advisory_findings
    )
    assert analysis.recommendation_evolution is not None
    assert (
        analysis.recommendation_evolution.evidence_basis[
            "prior_recommendations_are_not_independent_evidence"
        ]
        is True
    )
