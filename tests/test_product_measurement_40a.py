from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.admin.models import AdminEventLog
from backend.admin.roles import AdminRole
from backend.career_decisions.models import (
    CareerDecision,
    DecisionContextSnapshot,
    DecisionOption,
    DecisionRecommendation,
)
from backend.career_decisions.repository import CareerDecisionRepository
from backend.career_decisions.schemas import (
    ActionPlanCreateInput,
    ApplicationCreateInput,
    CareerActionUpdateInput,
    OptionSelectInput,
    OutcomeCreateInput,
)
from backend.career_decisions.service import CareerDecisionService
from backend.career_identity.models import CareerIdentity
from backend.career_identity.repository import CareerIdentityRepository
from backend.companies.repository import CompanyRepository
from backend.geography.repository import RegionRepository
from backend.product_measurement.models import (
    ProductAnalyticsEvent,
    ProductUserVisit,
    RecommendationFeedback,
)
from backend.product_measurement.schemas import (
    CohortCreate,
    CohortMembershipCreate,
    CommercialExperimentSignalCreate,
    CommercialOfferKey,
    CommercialSignalType,
    EntitlementGrantCreate,
    ExperimentAssignmentCreate,
    FeatureAccessMode,
    FeatureGateCreate,
    ProductEntitlementSource,
    ProductEventCreate,
    ProductEventSource,
    ProductEventType,
    RecommendationFeedbackCreate,
    StrategyChangeCreate,
    StrategyChangeType,
    SupportCaseCreate,
    SupportCaseStatus,
    SupportCaseType,
    SupportCaseUpdate,
)
from backend.product_measurement.service import (
    ProductMeasurementService,
    ProductMeasurementValidationError,
)
from backend.recommendations.models import RecommendationGoalMode
from backend.recommendations.ranking import rank_region_recommendations
from backend.scoring.repository import RegionScoreRepository
from backend.users.exceptions import CrossUserAccessBlocked
from backend.users.models import User
from backend.users.repository import UserRepository
from tests.test_api_user_routes import _auth_headers
from tests.test_career_decisions import (
    _decision_request as _layer36_decision_request,
)
from tests.test_career_decisions import (
    _seed_identity as _seed_layer36_identity,
)
from tests.test_career_decisions import (
    _seed_market as _seed_layer36_market,
)
from tests.test_recommendation_ranking import _region_output

NOW = datetime(2026, 9, 2, 12, tzinfo=UTC)


def _service(session: Session) -> ProductMeasurementService:
    return ProductMeasurementService(session, clock=lambda: NOW)


def _seed_user(session: Session, user_id: str = "user_40a") -> str:
    session.add(User(user_id=user_id))
    session.flush()
    return user_id


def _decision_service_with_measurement(
    session: Session,
    measurement_service: ProductMeasurementService,
) -> CareerDecisionService:
    return CareerDecisionService(
        CareerDecisionRepository(session),
        CareerIdentityRepository(session),
        UserRepository(session),
        RegionRepository(session),
        CompanyRepository(session),
        RegionScoreRepository(session),
        measurement_service,
    )


def _seed_decision_graph(session: Session, user_id: str = "user_40a") -> tuple[str, str]:
    _seed_user(session, user_id)
    identity = CareerIdentity(
        career_identity_id=f"identity_{user_id}",
        user_id=user_id,
        current_version=1,
        completeness_state="partial",
        sufficiency_state="sufficient",
        privacy_visibility="private",
    )
    session.add(identity)
    session.flush()
    context = DecisionContextSnapshot(
        context_snapshot_id=f"context_{user_id}",
        user_id=user_id,
        career_identity_id=identity.career_identity_id,
        career_identity_version=1,
        completeness_state="partial",
        sufficiency_state="sufficient",
        privacy_scope="owner_decision_only",
        context_payload={"facts": []},
        fact_refs=[],
    )
    session.add(context)
    session.flush()
    decision = CareerDecision(
        decision_id=f"decision_{user_id}",
        user_id=user_id,
        career_identity_id=identity.career_identity_id,
        current_context_snapshot_id=context.context_snapshot_id,
        decision_type="career_path",
        status="draft",
        title="Choose a path",
        priorities=[],
        constraints=[],
        current_version=1,
    )
    option = DecisionOption(
        option_id=f"option_{user_id}",
        user_id=user_id,
        decision_id=decision.decision_id,
        title="Target path",
        scenario={},
        status="active",
        position=0,
    )
    recommendation = DecisionRecommendation(
        recommendation_id=f"recommendation_{user_id}",
        user_id=user_id,
        decision_id=decision.decision_id,
        context_snapshot_id=context.context_snapshot_id,
        recommended_option_id=option.option_id,
        recommendation_status="ready",
        evidence_sufficiency="limited_evidence",
        confidence="medium",
        summary="Target path is best-supported.",
        fit_payload={},
        comparison_payload={"ranked_option_ids": [option.option_id]},
        evidence_payload={},
        challenge_payload=[],
        limitations=["Coverage is limited."],
        generated_at=NOW,
    )
    session.add_all([decision, option, recommendation])
    session.flush()
    return decision.decision_id, recommendation.recommendation_id


def test_event_model_validates_required_refs_and_sensitive_payloads(session: Session) -> None:
    decision_id, recommendation_id = _seed_decision_graph(session)

    with pytest.raises(ValidationError):
        ProductEventCreate(event_type=ProductEventType.RECOMMENDATION_GENERATED)
    with pytest.raises(ValidationError):
        ProductEventCreate(
            event_type=ProductEventType.DECISION_CREATED,
            decision_id=decision_id,
            payload={"resume_text": "do not copy this into analytics"},
        )

    event = _service(session).record_event(
        "user_40a",
        ProductEventCreate(
            event_type=ProductEventType.RECOMMENDATION_GENERATED,
            event_source=ProductEventSource.BACKEND,
            decision_id=decision_id,
            recommendation_id=recommendation_id,
            confidence_bucket="medium",
            coverage_status="limited_evidence",
            recommendation_state="ready",
            payload={"option_count": 1},
        ),
    )

    assert event.event_type == "recommendation_generated"
    assert event.schema_version == 1
    assert "resume_text" not in json.dumps(event.payload)


def test_explore_coverage_and_trust_events_match_frontend_contract(api_client) -> None:
    headers = _auth_headers("auth0|explore_measurement")
    coverage = api_client.post(
        "/me/product-events",
        headers=headers,
        json={
            "event_type": "coverage_limitation_viewed",
            "event_source": "frontend",
            "product_surface": "explore_market_detail",
            "coverage_status": "unsupported",
            "confidence_bucket": "low",
            "payload": {"region_id": "greater_boston"},
        },
    )
    trust = api_client.post(
        "/me/product-events",
        headers=headers,
        json={
            "event_type": "trust_explanation_viewed",
            "event_source": "frontend",
            "product_surface": "explore_market_detail",
            "confidence_bucket": "low",
            "payload": {"region_id": "greater_boston"},
        },
    )

    assert coverage.status_code == 201
    assert trust.status_code == 201


def test_feedback_is_version_tied_preserved_and_measurable(session: Session) -> None:
    decision_id, recommendation_id = _seed_decision_graph(session)
    service = _service(session)

    first = service.submit_recommendation_feedback(
        "user_40a",
        RecommendationFeedbackCreate(
            decision_id=decision_id,
            recommendation_id=recommendation_id,
            useful=True,
            surprising=True,
            changed_decision=True,
            missing_alternative=True,
            missing_alternative_category="company",
            confidence_calibration="about_right",
            cohort_key="private_beta_a",
        ),
    )
    second = service.submit_recommendation_feedback(
        "user_40a",
        RecommendationFeedbackCreate(
            decision_id=decision_id,
            recommendation_id=recommendation_id,
            useful=False,
            surprising=False,
            changed_decision=False,
            missing_alternative=False,
            confidence_calibration="too_high",
            cohort_key="private_beta_a",
        ),
    )

    assert first.feedback_id != second.feedback_id
    assert session.query(RecommendationFeedback).count() == 2
    event_types = [row.event_type for row in session.query(ProductAnalyticsEvent).all()]
    assert "recommendation_feedback_submitted" in event_types
    assert "recommendation_changed_decision" in event_types
    summary = service.beta_analytics_summary(cohort_key="private_beta_a")
    assert summary.recommendation_feedback["total"] == 2
    assert summary.recommendation_feedback["changed_decision"] == 1

    other_decision_id, _other_rec_id = _seed_decision_graph(session, "user_other")
    with pytest.raises(ProductMeasurementValidationError):
        service.submit_recommendation_feedback(
            "user_40a",
            RecommendationFeedbackCreate(
                decision_id=other_decision_id,
                recommendation_id=recommendation_id,
                useful=True,
                surprising=False,
                changed_decision=False,
                missing_alternative=False,
                confidence_calibration="unsure",
            ),
        )


def test_cohort_feature_gate_entitlement_and_admin_audit(session: Session) -> None:
    _seed_user(session)
    _seed_user(session, "user_no_access")
    _seed_user(session, "admin_user")
    service = _service(session)

    service.upsert_cohort(
        CohortCreate(
            cohort_key="private_beta_a",
            name="Private beta A",
            status="active",
            starts_at=NOW - timedelta(days=1),
            feature_flags={"decision_feedback": True},
        ),
        actor_user_id="admin_user",
        role=AdminRole.ADMIN,
    )
    service.assign_cohort_membership(
        CohortMembershipCreate(user_id="user_40a", cohort_key="private_beta_a"),
        actor_user_id="admin_user",
        role=AdminRole.ADMIN,
    )
    service.upsert_feature_gate(
        FeatureGateCreate(
            feature_key="decision_feedback",
            enabled=True,
            access_mode=FeatureAccessMode.BETA_ONLY,
            cohort_keys=("private_beta_a",),
        ),
        actor_user_id="admin_user",
        role=AdminRole.ADMIN,
    )

    assert service.decide_feature_access("user_40a", "decision_feedback").allowed is True
    assert service.decide_feature_access("user_no_access", "decision_feedback").allowed is False

    service.upsert_feature_gate(
        FeatureGateCreate(
            feature_key="premium_scenarios",
            enabled=True,
            access_mode=FeatureAccessMode.ENTITLEMENT_REQUIRED,
        ),
        actor_user_id="admin_user",
        role=AdminRole.ADMIN,
    )
    assert service.decide_feature_access("user_40a", "premium_scenarios").allowed is False
    service.create_entitlement_grant(
        EntitlementGrantCreate(
            user_id="user_40a",
            feature_key="premium_scenarios",
            source_type=ProductEntitlementSource.ADMINISTRATIVE_GRANT,
            reason="beta validation grant",
        ),
        actor_user_id="admin_user",
        role=AdminRole.ADMIN,
    )
    access = service.decide_feature_access("user_40a", "premium_scenarios")
    assert access.allowed is True
    assert access.entitlement_source == "administrative_grant"
    assert session.query(AdminEventLog).count() >= 5


def test_beta_route_access_uses_existing_active_cohort_authority(
    api_client, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api_client.app.state.settings, "beta_access_required", True)
    headers = _auth_headers("auth0|controlled_beta_member")
    current = api_client.get("/me", headers=headers)
    assert current.status_code == 200
    user_id = current.json()["data"]["user"]["user_id"]

    denied = api_client.get("/me/explore/context", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["error"]["message"] == "Active beta access is required"

    _seed_user(session, "admin_beta_access")
    service = _service(session)
    service.upsert_cohort(
        CohortCreate(
            cohort_key="controlled_beta_1",
            name="Controlled beta 1",
            status="active",
        ),
        actor_user_id="admin_beta_access",
        role=AdminRole.ADMIN,
    )
    service.assign_cohort_membership(
        CohortMembershipCreate(user_id=user_id, cohort_key="controlled_beta_1"),
        actor_user_id="admin_beta_access",
        role=AdminRole.ADMIN,
    )

    allowed = api_client.get("/me/explore/context", headers=headers)
    assert allowed.status_code == 200
    assert allowed.json()["data"]["personalization_state"] == "general_market_intelligence"


def test_support_privacy_dispute_and_strategy_workflows(session: Session) -> None:
    decision_id, recommendation_id = _seed_decision_graph(session)
    _seed_user(session, "admin_user")
    service = _service(session)

    bad_data = service.create_support_case(
        "user_40a",
        SupportCaseCreate(
            case_type=SupportCaseType.BAD_DATA,
            title="Opportunity data is incorrect",
            subject_type="current_opportunity",
            subject_id="external_reference_only",
            priority="high",
        ),
    )
    dispute = service.create_support_case(
        "user_40a",
        SupportCaseCreate(
            case_type=SupportCaseType.RECOMMENDATION_ISSUE,
            title="Recommendation missed a path",
            decision_id=decision_id,
            recommendation_id=recommendation_id,
        ),
    )
    privacy = service.create_support_case(
        "user_40a",
        SupportCaseCreate(
            case_type=SupportCaseType.PRIVACY_ISSUE,
            title="Data export request",
            privacy_request_type="export",
        ),
    )
    updated = service.update_support_case(
        bad_data.support_case_id,
        SupportCaseUpdate(status=SupportCaseStatus.RESOLVED, resolution="Queued for review."),
        actor_user_id="admin_user",
        role=AdminRole.ADMIN,
    )
    strategy = service.record_strategy_change(
        "user_40a",
        StrategyChangeCreate(
            decision_id=decision_id,
            recommendation_id=recommendation_id,
            change_type=StrategyChangeType.TARGET_ROLE,
            previous_state={"target_role": "analyst"},
            new_state={"target_role": "product_manager"},
            reason_category="recommendation_review",
        ),
    )

    assert updated.status == "resolved"
    assert {case.support_case_id for case in service.list_support_cases("user_40a")} == {
        bad_data.support_case_id,
        dispute.support_case_id,
        privacy.support_case_id,
    }
    assert strategy.change_type == "target_role"
    events = [row.event_type for row in session.query(ProductAnalyticsEvent).all()]
    assert "support_case_created" in events
    assert "support_case_status_changed" in events
    assert "strategy_changed" in events

    _seed_user(session, "user_other")
    other_decision_id, _other_rec_id = _seed_decision_graph(session, "user_other2")
    with pytest.raises(CrossUserAccessBlocked):
        service.create_support_case(
            "user_40a",
            SupportCaseCreate(
                case_type=SupportCaseType.RECOMMENDATION_ISSUE,
                title="Cross user",
                decision_id=other_decision_id,
            ),
        )


def test_commercial_signals_do_not_record_fake_payment(session: Session) -> None:
    _seed_user(session)
    signal = _service(session).record_commercial_signal(
        "user_40a",
        CommercialExperimentSignalCreate(
            experiment_key="offer_test_decision_report",
            variant_key="report_copy_a",
            offer_key=CommercialOfferKey.ONE_TIME_DECISION_REPORT,
            signal_type=CommercialSignalType.INTERESTED,
            product_surface="decision_workspace",
        ),
    )

    assert signal.conversion_ref is None
    assert signal.signal_type == "interested"
    assert (
        session.query(ProductAnalyticsEvent).one().event_type
        == "commercial_offer_interest_recorded"
    )


def test_return_visit_semantics_with_cohort_and_experiment_segmentation(session: Session) -> None:
    _seed_user(session)
    _seed_user(session, "admin_user")
    clock = {"now": NOW}
    service = ProductMeasurementService(session, clock=lambda: clock["now"])
    service.upsert_cohort(
        CohortCreate(cohort_key="private_beta_a", name="Private beta A", status="active"),
        actor_user_id="admin_user",
        role=AdminRole.ADMIN,
    )
    service.assign_cohort_membership(
        CohortMembershipCreate(user_id="user_40a", cohort_key="private_beta_a"),
        actor_user_id="admin_user",
        role=AdminRole.ADMIN,
    )
    service.assign_experiment(
        ExperimentAssignmentCreate(
            user_id="user_40a",
            cohort_key="private_beta_a",
            experiment_key="offer_test",
            variant_key="report_a",
            assignment_basis="beta_fixture",
        ),
        actor_user_id="admin_user",
        role=AdminRole.ADMIN,
    )

    first = service.observe_authenticated_product_visit("user_40a")
    assert first.returned_event_id is None
    assert session.query(ProductUserVisit).count() == 1
    assert session.query(ProductAnalyticsEvent).filter_by(event_type="user_returned").count() == 0

    clock["now"] = NOW + timedelta(minutes=10)
    same_visit = service.observe_authenticated_product_visit("user_40a")
    assert same_visit.visit_id == first.visit_id
    assert session.query(ProductUserVisit).count() == 1
    assert session.query(ProductAnalyticsEvent).filter_by(event_type="user_returned").count() == 0

    clock["now"] = NOW + timedelta(minutes=45)
    returned = service.observe_authenticated_product_visit("user_40a")
    return_events = session.query(ProductAnalyticsEvent).filter_by(event_type="user_returned").all()
    assert returned.visit_id != first.visit_id
    assert returned.returned_event_id == return_events[0].event_id
    assert return_events[0].user_id == "user_40a"
    assert return_events[0].cohort_key == "private_beta_a"
    assert return_events[0].experiment_key == "offer_test"
    assert return_events[0].variant_key == "report_a"
    assert return_events[0].payload["previous_visit_id"] == first.visit_id

    clock["now"] = NOW + timedelta(minutes=50)
    service.observe_authenticated_product_visit("user_40a")
    assert session.query(ProductUserVisit).count() == 2
    assert session.query(ProductAnalyticsEvent).filter_by(event_type="user_returned").count() == 1


def test_get_me_automatically_emits_return_and_isolates_telemetry_failure(
    api_client,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _auth_headers("auth0|return_closeout")
    first = api_client.get("/me", headers=headers)
    assert first.status_code == 200
    user_id = first.json()["data"]["user"]["user_id"]
    assert session.query(ProductUserVisit).filter_by(user_id=user_id).count() == 1
    assert session.query(ProductAnalyticsEvent).filter_by(event_type="user_returned").count() == 0

    second = api_client.get("/me", headers=headers)
    assert second.status_code == 200
    assert session.query(ProductUserVisit).filter_by(user_id=user_id).count() == 1

    visit = session.query(ProductUserVisit).filter_by(user_id=user_id).one()
    visit.last_seen_at = datetime.now(UTC) - timedelta(hours=1)
    session.flush()
    returned = api_client.get("/me", headers=headers)
    assert returned.status_code == 200
    return_event = session.query(ProductAnalyticsEvent).filter_by(event_type="user_returned").one()
    assert return_event.user_id == user_id

    def fail_visit(*_args, **_kwargs) -> None:
        raise RuntimeError("telemetry write failed")

    monkeypatch.setattr(
        ProductMeasurementService,
        "observe_authenticated_product_visit",
        fail_visit,
    )
    isolated = api_client.get("/me", headers=_auth_headers("auth0|return_failure"))
    assert isolated.status_code == 200


def test_complete_funnel_counts_order_conversion_and_return_without_duplicate_inflation(
    session: Session,
) -> None:
    user_id = _seed_user(session, "user_funnel")
    _seed_user(session, "admin_user")
    clock = {"now": NOW}
    service = ProductMeasurementService(session, clock=lambda: clock["now"])
    service.upsert_cohort(
        CohortCreate(cohort_key="private_beta_a", name="Private beta A", status="active"),
        actor_user_id="admin_user",
        role=AdminRole.ADMIN,
    )
    service.assign_cohort_membership(
        CohortMembershipCreate(user_id=user_id, cohort_key="private_beta_a"),
        actor_user_id="admin_user",
        role=AdminRole.ADMIN,
    )
    _seed_layer36_market(session)
    _seed_layer36_identity(session, user_id)
    identity = session.query(CareerIdentity).filter_by(user_id=user_id).one()
    service.record_event(
        user_id, ProductEventCreate(event_type=ProductEventType.ONBOARDING_STARTED)
    )
    service.record_event(
        user_id, ProductEventCreate(event_type=ProductEventType.ONBOARDING_COMPLETED)
    )
    service.record_event(
        user_id,
        ProductEventCreate(
            event_type=ProductEventType.CAREER_IDENTITY_SUFFICIENT,
            career_identity_id=identity.career_identity_id,
        ),
    )
    for event_type, surface in (
        (ProductEventType.EXPLORE_CONTEXT_EVALUATED, "explore"),
        (ProductEventType.MARKET_INSPECTED, "explore_market_detail"),
        (ProductEventType.COMPARISON_SELECTION_READY, "explore"),
        (ProductEventType.COMPARISON_GENERATED, "explore_comparison"),
        (ProductEventType.COMPARISON_SAVED, "explore_comparison"),
        (ProductEventType.MY_SEARCH_VIEWED, "my_search"),
    ):
        service.record_event(
            user_id,
            ProductEventCreate(event_type=event_type, product_surface=surface),
        )

    decision_service = _decision_service_with_measurement(session, service)
    decision = decision_service.create_decision(user_id, _layer36_decision_request())
    recommendation = decision_service.compare_decision(user_id, decision.decision_id)
    assert recommendation.recommended_option_id is not None
    decision_service.select_option(
        user_id,
        decision.decision_id,
        OptionSelectInput(option_id=recommendation.recommended_option_id),
    )
    plan = decision_service.create_action_plan(
        user_id, decision.decision_id, ActionPlanCreateInput()
    )
    decision_service.update_action(
        user_id,
        plan.actions[0].action_id,
        CareerActionUpdateInput(status="completed"),
    )
    application = decision_service.create_application(
        user_id,
        ApplicationCreateInput(
            decision_id=decision.decision_id,
            action_id=plan.actions[1].action_id,
            option_id=recommendation.recommended_option_id,
            company_id="acme_ai",
            region_id="greater_boston",
            role_title="Product Manager",
            status="applied",
        ),
    )
    decision_service.create_outcome(
        user_id,
        OutcomeCreateInput(
            outcome_type="offer",
            title="Offer received",
            application_id=application.application_id,
            recommendation_id=recommendation.recommendation_id,
        ),
    )
    service.observe_authenticated_product_visit(user_id)
    clock["now"] = NOW + timedelta(minutes=45)
    service.observe_authenticated_product_visit(user_id)
    clock["now"] = NOW + timedelta(minutes=50)
    service.observe_authenticated_product_visit(user_id)

    summary = service.beta_analytics_summary(cohort_key="private_beta_a")
    stages = {stage.stage: stage for stage in summary.funnel}
    assert [stage.stage for stage in summary.funnel] == [
        "signed_in",
        "profile_essentials_sufficient",
        "explore_viewed",
        "market_inspected",
        "two_plus_markets_selected",
        "comparison_generated",
        "comparison_saved_or_prioritized",
        "my_search_viewed",
        "action_completed",
        "application_tracking_started",
        "return",
    ]
    assert stages["return"].user_count == 1
    assert stages["return"].event_count == 1
    assert all(stage.user_count == 1 for stage in summary.funnel)
    assert all(stage.conversion_from_previous in {None, 1.0} for stage in summary.funnel)


def test_batch_40b_domain_observation_points_are_wired_to_actual_product_paths(
    session: Session,
) -> None:
    user_id = _seed_user(session, "user_observation")
    _seed_layer36_market(session)
    _seed_layer36_identity(session, user_id)
    measurement = _service(session)
    decision_service = _decision_service_with_measurement(session, measurement)

    decision = decision_service.create_decision(user_id, _layer36_decision_request())
    recommendation = decision_service.compare_decision(user_id, decision.decision_id)
    assert recommendation.recommended_option_id is not None
    decision_service.select_option(
        user_id,
        decision.decision_id,
        OptionSelectInput(option_id=recommendation.recommended_option_id),
    )
    plan = decision_service.create_action_plan(
        user_id, decision.decision_id, ActionPlanCreateInput()
    )
    decision_service.update_action(
        user_id,
        plan.actions[0].action_id,
        CareerActionUpdateInput(status="completed"),
    )
    application = decision_service.create_application(
        user_id,
        ApplicationCreateInput(
            decision_id=decision.decision_id,
            action_id=plan.actions[1].action_id,
            option_id=recommendation.recommended_option_id,
            company_id="acme_ai",
            region_id="greater_boston",
            role_title="Product Manager",
            status="applied",
        ),
    )
    decision_service.create_outcome(
        user_id,
        OutcomeCreateInput(
            outcome_type="offer",
            title="Offer received",
            application_id=application.application_id,
            recommendation_id=recommendation.recommendation_id,
        ),
    )
    measurement.submit_recommendation_feedback(
        user_id,
        RecommendationFeedbackCreate(
            decision_id=decision.decision_id,
            recommendation_id=recommendation.recommendation_id,
            useful=True,
            surprising=False,
            changed_decision=True,
            missing_alternative=False,
            confidence_calibration="about_right",
        ),
    )

    event_types = [row.event_type for row in session.query(ProductAnalyticsEvent).all()]
    assert "decision_created" in event_types
    assert "decision_considered" in event_types
    assert "recommendation_generated" in event_types
    assert "decision_saved" in event_types
    assert "action_created" in event_types
    assert "action_succeeded" in event_types
    assert "application_recorded" in event_types
    assert "user_acted" in event_types
    assert "outcome_recorded" in event_types
    assert "recommendation_feedback_submitted" in event_types
    assert "recommendation_changed_decision" in event_types


def test_commercial_state_cannot_influence_core_recommendation_ranking(session: Session) -> None:
    _seed_user(session)
    _seed_user(session, "admin_user")
    service = _service(session)
    service.create_entitlement_grant(
        EntitlementGrantCreate(
            user_id="user_40a",
            feature_key="premium_scenarios",
            source_type=ProductEntitlementSource.PAID_PLAN,
            source_ref_id="plan_reference",
            reason="test commercial entitlement",
        ),
        actor_user_id="admin_user",
        role=AdminRole.ADMIN,
    )
    baseline = rank_region_recommendations(
        [
            _region_output(
                region_id="access_market",
                display_name="Access Market",
                early_access=0.92,
                prestige=0.25,
                present_companies=8,
                internships=9,
            ),
            _region_output(
                region_id="prestige_market",
                display_name="Prestige Market",
                early_access=0.3,
                prestige=0.95,
                present_companies=18,
                internships=1,
            ),
        ],
        goal_mode=RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS,
    )
    after_commercial_state = rank_region_recommendations(
        [
            _region_output(
                region_id="prestige_market",
                display_name="Prestige Market",
                early_access=0.3,
                prestige=0.95,
                present_companies=18,
                internships=1,
            ),
            _region_output(
                region_id="access_market",
                display_name="Access Market",
                early_access=0.92,
                prestige=0.25,
                present_companies=8,
                internships=9,
            ),
        ],
        goal_mode=RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS,
    )

    assert [item.target.target_id for item in baseline.ranked_recommendations] == [
        item.target.target_id for item in after_commercial_state.ranked_recommendations
    ]
    assert [item.final_score for item in baseline.ranked_recommendations] == [
        item.final_score for item in after_commercial_state.ranked_recommendations
    ]
