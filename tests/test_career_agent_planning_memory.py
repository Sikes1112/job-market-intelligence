from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.career_agent.memory import (
    CareerMemoryPermissionError,
    CareerMemoryService,
)
from backend.career_agent.planning import CareerActionPlanningService
from backend.career_agent.schemas import (
    CareerActionPlan,
    CareerActionPlanRequest,
    CareerAgentEvidenceRef,
    CareerAgentEvidenceType,
    CareerAgentFreshness,
    CareerAgentFreshnessStatus,
    CareerAgentGuardrailStatus,
    CareerAgentGuardrailViolation,
    CareerAgentQuestionType,
    CareerAgentRequest,
    CareerAgentUncertainty,
    CareerMemoryCategory,
    CareerMemoryDeleteRequest,
    CareerMemoryEntryInput,
    CareerMemoryPermission,
    CareerMemoryUpdateRequest,
    CareerPlanMilestone,
    CareerPlanStep,
    CareerPlanTimeWindow,
    CareerPlanType,
    CareerPlanUserActionRequirement,
    validate_career_action_plan,
)
from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.schemas import MarketSnapshotCreate
from backend.platform_intelligence.snapshots import HistoricalSnapshotService
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore
from backend.shared.confidence import Confidence
from backend.users.models import User

NOW = datetime(2026, 6, 30, 12, tzinfo=UTC)


def _auth_headers(subject: str = "auth0|career_memory_user") -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"User {suffix}",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _current_user_id(api_client: TestClient, subject: str = "auth0|career_memory_user") -> str:
    response = api_client.get("/me", headers=_auth_headers(subject))
    assert response.status_code == 200
    return response.json()["data"]["user"]["user_id"]


def _seed_region(
    session: Session,
    *,
    region_id: str,
    display_name: str,
    objective: float,
    early: float,
    expires_at: datetime | None = None,
) -> None:
    session.add(
        Region(
            region_id=region_id,
            region_name=region_id,
            display_name=display_name,
            region_type="metro",
            market_support_status="supported",
        )
    )
    session.flush()
    session.add(
        RegionMarketScore(
            region_score_id=f"score_{region_id}",
            region_id=region_id,
            objective_opportunity_score=objective,
            early_career_accessibility_score=early,
            score_ruleset_version="career_plan_test",
        )
    )
    session.flush()
    session.add(
        Company(
            company_id=f"comp_{region_id}",
            company_name=f"{display_name} Systems",
            normalized_company_name=f"{display_name} systems".casefold(),
            sector_primary="software",
            eligibility_status="eligible",
            classification_confidence="high_confidence",
        )
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id=f"presence_{region_id}",
                company_id=f"comp_{region_id}",
                region_id=region_id,
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
                presence_confidence="high_confidence",
            ),
            CompanyRegionHiring(
                hiring_id=f"hiring_{region_id}",
                company_id=f"comp_{region_id}",
                region_id=region_id,
                currently_hiring_flag=True,
                active_posting_count_now=8,
                posting_count_30d=12,
                role_family_summary={"software_engineering": 5},
                hiring_confidence="high_confidence",
                freshness_expires_at=expires_at,
            ),
            CompanyRegionEntryLevel(
                entry_level_id=f"entry_{region_id}",
                company_id=f"comp_{region_id}",
                region_id=region_id,
                internship_count=3,
                coop_count=1,
                entry_level_full_time_count=4,
                formal_early_career_program_flag=True,
                entry_level_access_score=early,
                entry_level_confidence="high_confidence",
                freshness_expires_at=expires_at,
            ),
        ]
    )
    session.flush()


def _seed_user(session: Session, user_id: str) -> None:
    session.add(User(user_id=user_id))
    session.flush()


def _plan_request(
    plan_type: CareerPlanType = CareerPlanType.WEEKLY_JOB_SEARCH_PLAN,
) -> CareerActionPlanRequest:
    return CareerActionPlanRequest(
        plan_type=plan_type,
        career_goal="Find early-career software roles.",
        career_agent_request=CareerAgentRequest(
            question_type=CareerAgentQuestionType.WHAT_SHOULD_I_DO_THIS_MONTH,
            target_region_ids=("greater_boston", "greater_atlanta"),
            target_role_families=("software_engineering",),
            include_forecasts=False,
            limit=5,
        ),
    )


def test_action_plan_includes_evidence_freshness_uncertainty_and_action_labels(
    session: Session,
) -> None:
    _seed_region(
        session,
        region_id="greater_boston",
        display_name="Greater Boston",
        objective=0.84,
        early=0.77,
        expires_at=NOW + timedelta(days=30),
    )

    plan = CareerActionPlanningService(session).generate_plan(
        _plan_request(),
        now=NOW,
    )

    assert plan.steps
    assert all(step.evidence_refs for step in plan.steps if step.strategic)
    assert plan.freshness.source_count > 0
    assert plan.uncertainty.confidence_level in Confidence
    assert {
        step.action_owner for step in plan.steps
    } >= {
        CareerPlanUserActionRequirement.SYSTEM_SUGGESTED,
        CareerPlanUserActionRequirement.USER_ACTION_REQUIRED,
    }
    assert plan.guardrails.evidence_requirement_met is True


def test_plan_validation_blocks_fabricated_opportunity_reference() -> None:
    freshness = CareerAgentFreshness(
        freshness_status=CareerAgentFreshnessStatus.FRESH,
        data_basis="test_fixture",
        source_count=1,
    )
    uncertainty = CareerAgentUncertainty(
        confidence_level=Confidence.MEDIUM,
        confidence_score=0.5,
        uncertainty_level="medium",
        reasons=("fixture",),
    )
    evidence = CareerAgentEvidenceRef(
        ref_id="region:greater_boston",
        evidence_type=CareerAgentEvidenceType.REGION,
        entity_type="region",
        entity_id="greater_boston",
        label="Greater Boston",
        summary="Stored region evidence.",
        data_basis="structured_fixture",
        freshness_status=CareerAgentFreshnessStatus.FRESH,
        source_count=1,
    )
    step = CareerPlanStep(
        step_id="step_fake_opp",
        rank=1,
        title="Unsupported opportunity step",
        description="This references a role that is not backed by opportunity evidence.",
        action_owner=CareerPlanUserActionRequirement.USER_ACTION_REQUIRED,
        milestone=CareerPlanMilestone(
            milestone_id="milestone_fake_opp",
            summary="Unsupported role checked.",
            outcome="This should fail validation.",
        ),
        evidence_refs=(evidence,),
        freshness=freshness,
        uncertainty=uncertainty,
        matched_opportunity_ids=("opp_fake",),
    )
    plan = CareerActionPlan(
        plan_id="plan_fake_opp",
        plan_type=CareerPlanType.WEEKLY_JOB_SEARCH_PLAN,
        generated_at=NOW,
        source_answer_id="answer_fake_opp",
        summary="Fixture plan.",
        time_window=CareerPlanTimeWindow(
            label="fixture window",
            start_date=NOW.date(),
            end_date=NOW.date(),
        ),
        steps=(step,),
        evidence_refs=(evidence,),
        freshness=freshness,
        source_freshness=(freshness,),
        uncertainty=uncertainty,
        guardrails=CareerAgentGuardrailStatus(
            passed=True,
            evidence_requirement_met=True,
        ),
    )

    with pytest.raises(CareerAgentGuardrailViolation):
        validate_career_action_plan(plan)


def test_action_plan_does_not_reintroduce_legacy_forecast_grounding(
    session: Session,
) -> None:
    _seed_region(
        session,
        region_id="greater_boston",
        display_name="Greater Boston",
        objective=0.84,
        early=0.77,
        expires_at=NOW - timedelta(days=1),
    )
    snapshot_service = HistoricalSnapshotService(HistoryRepository(session))
    for index, value in enumerate((0.30, 0.45, 0.58, 0.70), start=1):
        snapshot_service.record_market_snapshot(
            MarketSnapshotCreate(
                market_snapshot_id=f"career_plan_market_{index}",
                region_id="greater_boston",
                snapshot_date=date(2026, index, 1),
                overall_score=value,
                ai_opportunity_score=value,
                entry_level_access_score=0.70,
                confidence_score=0.70,
                coverage_tier="tier_2",
                freshness_state="fresh",
            )
        )

    plan = CareerActionPlanningService(session).generate_plan(
        CareerActionPlanRequest(
            plan_type=CareerPlanType.REGIONAL_TARGETING_PLAN,
            career_agent_request=CareerAgentRequest(
                question_type=CareerAgentQuestionType.STRONGEST_MARKET_STRATEGY,
                target_region_ids=("greater_boston",),
                include_forecasts=True,
            ),
        ),
        now=NOW,
    )

    warning_text = " ".join(
        (*plan.warnings, *(warning for step in plan.steps for warning in step.warnings))
    )
    assert "forecast" not in warning_text.casefold()
    assert "ranking evidence" in " ".join(plan.limitations).casefold()
    assert plan.risks


def test_memory_is_off_by_default_and_requires_permission(session: Session) -> None:
    service = CareerMemoryService(session)
    profile = service.get_profile("user_memory_default")

    assert profile.memory_enabled is False
    assert profile.entries == ()
    assert all(permission.enabled is False for permission in profile.permissions)

    with pytest.raises(CareerMemoryPermissionError):
        service.update_memory(
            "user_memory_default",
            CareerMemoryUpdateRequest(
                entries=(
                    CareerMemoryEntryInput(
                        category=CareerMemoryCategory.SAVED_COMPANIES,
                        value="comp_a",
                    ),
                ),
            ),
        )


def test_memory_categories_are_scoped_and_deletable(session: Session) -> None:
    _seed_user(session, "user_memory_scoped")
    service = CareerMemoryService(session)
    profile = service.update_memory(
        "user_memory_scoped",
        CareerMemoryUpdateRequest(
            explicit_user_permission=True,
            permissions=(
                CareerMemoryPermission(
                    category=CareerMemoryCategory.SAVED_COMPANIES,
                    enabled=True,
                    personalize_allowed=True,
                ),
                CareerMemoryPermission(
                    category=CareerMemoryCategory.TARGET_REGIONS,
                    enabled=True,
                    personalize_allowed=True,
                ),
            ),
            entries=(
                CareerMemoryEntryInput(
                    category=CareerMemoryCategory.SAVED_COMPANIES,
                    value="comp_a",
                ),
                CareerMemoryEntryInput(
                    category=CareerMemoryCategory.TARGET_REGIONS,
                    value="greater_boston",
                ),
            ),
        ),
    )

    assert [entry.value for entry in profile.entries_by_category["saved_companies"]] == [
        "comp_a"
    ]
    assert [entry.value for entry in profile.entries_by_category["target_regions"]] == [
        "greater_boston"
    ]

    deleted = service.delete_memory(
        "user_memory_scoped",
        CareerMemoryDeleteRequest(categories=(CareerMemoryCategory.SAVED_COMPANIES,)),
    )

    assert deleted.entries_by_category["saved_companies"] == ()
    assert deleted.entries_by_category["target_regions"]


def test_rejected_markets_and_applied_roles_affect_plans_only_with_permission(
    session: Session,
) -> None:
    _seed_user(session, "user_memory_plans")
    _seed_region(
        session,
        region_id="greater_boston",
        display_name="Greater Boston",
        objective=0.90,
        early=0.80,
        expires_at=NOW + timedelta(days=30),
    )
    _seed_region(
        session,
        region_id="greater_atlanta",
        display_name="Greater Atlanta",
        objective=0.70,
        early=0.68,
        expires_at=NOW + timedelta(days=30),
    )
    planning = CareerActionPlanningService(session)
    request = _plan_request(CareerPlanType.REGIONAL_TARGETING_PLAN)

    without_memory = planning.generate_plan(request, now=NOW)
    assert "greater_boston" in {
        ref.entity_id
        for step in without_memory.steps
        for ref in step.evidence_refs
    }

    memory_profile = CareerMemoryService(session).update_memory(
        "user_memory_plans",
        CareerMemoryUpdateRequest(
            explicit_user_permission=True,
            permissions=(
                CareerMemoryPermission(
                    category=CareerMemoryCategory.REJECTED_MARKETS,
                    enabled=True,
                    personalize_allowed=True,
                ),
                CareerMemoryPermission(
                    category=CareerMemoryCategory.APPLIED_ROLES,
                    enabled=True,
                    personalize_allowed=True,
                ),
            ),
            entries=(
                CareerMemoryEntryInput(
                    category=CareerMemoryCategory.REJECTED_MARKETS,
                    value="greater_boston",
                ),
                CareerMemoryEntryInput(
                    category=CareerMemoryCategory.APPLIED_ROLES,
                    value="software_engineering_internship",
                ),
            ),
        ),
    )
    with_memory = planning.generate_plan(request, memory_profile=memory_profile, now=NOW)
    evidence_entity_ids = {
        ref.entity_id
        for step in with_memory.steps
        for ref in step.evidence_refs
    }

    assert evidence_entity_ids == {"greater_boston"}
    assert "All grounded recommendations matched rejected markets" in " ".join(
        with_memory.warnings
    )
    assert "already-applied roles" in " ".join(with_memory.warnings)
    assert with_memory.memory_personalization
    assert all(
        "memory" not in ref.data_basis
        for step in with_memory.steps
        for ref in step.evidence_refs
    )


def test_memory_routes_are_protected_scoped_and_export_owner_memory_only(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_region(
        session,
        region_id="greater_boston",
        display_name="Greater Boston",
        objective=0.84,
        early=0.77,
        expires_at=NOW + timedelta(days=30),
    )
    user_a_headers = _auth_headers("auth0|cm_a")
    user_b_headers = _auth_headers("auth0|cm_b")
    _current_user_id(api_client, "auth0|cm_a")
    _current_user_id(api_client, "auth0|cm_b")

    unauthenticated = api_client.get("/me/career-memory")
    assert unauthenticated.status_code == 401

    saved = api_client.put(
        "/me/career-memory",
        headers=user_a_headers,
        json={
            "explicit_user_permission": True,
            "permissions": [
                {
                    "category": "rejected_markets",
                    "enabled": True,
                    "personalize_allowed": True,
                }
            ],
            "entries": [
                {"category": "rejected_markets", "value": "greater_boston"}
            ],
        },
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["memory_enabled"] is True

    user_b_profile = api_client.get("/me/career-memory", headers=user_b_headers)
    assert user_b_profile.status_code == 200
    assert user_b_profile.json()["data"]["entries"] == []

    public_plan = api_client.post(
        "/career-agent/action-plans",
        json=_plan_request().model_dump(mode="json"),
    )
    assert public_plan.status_code == 200
    assert "career_memory" not in public_plan.text
    assert "rejected_markets" not in public_plan.text

    exported = api_client.get("/me/export", headers=user_a_headers)
    assert exported.status_code == 200
    memory_export = exported.json()["data"]["career_agent_memory"]
    assert memory_export["permissions"][0]["category"] == "rejected_markets"
    assert memory_export["entries"][0]["category"] == "rejected_markets"
    assert memory_export["entries"][0]["value"] == "greater_boston"

    user_b_export = api_client.get("/me/export", headers=user_b_headers)
    assert user_b_export.status_code == 200
    assert user_b_export.json()["data"]["career_agent_memory"]["entries"] == []

    deleted = api_client.request(
        "DELETE",
        "/me/career-memory",
        headers=user_a_headers,
        json={"clear_all": True},
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["memory_enabled"] is False


def test_action_plan_api_route_returns_grounded_schema(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_region(
        session,
        region_id="greater_boston",
        display_name="Greater Boston",
        objective=0.84,
        early=0.77,
        expires_at=NOW + timedelta(days=30),
    )

    response = api_client.post(
        "/career-agent/action-plans",
        json=_plan_request().model_dump(mode="json"),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["plan_type"] == "weekly_job_search_plan"
    assert data["steps"]
    assert data["freshness"]
    assert data["uncertainty"]
    assert data["steps"][0]["evidence_refs"]
    assert "internal_review_notes" not in response.text


def test_public_action_plan_rejects_memory_flag(api_client: TestClient) -> None:
    response = api_client.post(
        "/career-agent/action-plans",
        json=_plan_request().model_copy(update={"include_memory": True}).model_dump(mode="json"),
    )

    assert response.status_code == 400
