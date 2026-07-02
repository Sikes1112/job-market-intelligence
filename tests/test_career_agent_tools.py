from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.career_agent.approvals import CareerAgentToolApprovalError
from backend.career_agent.memory import CareerMemoryService
from backend.career_agent.schemas import (
    CareerActionPlanRequest,
    CareerAgentQuestionType,
    CareerAgentRequest,
    CareerAgentRequestedToolAction,
    CareerAgentToolApproval,
    CareerAgentToolRequest,
    CareerAgentToolStatus,
    CareerAgentToolType,
    CareerMemoryCategory,
    CareerMemoryEntryInput,
    CareerMemoryPermission,
    CareerMemoryUpdateRequest,
)
from backend.career_agent.tools import CareerAgentToolService
from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.schemas import (
    EmployerInfluenceMetadataCreate,
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
from backend.opportunities.service import OpportunityService
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore
from backend.users.models import User

NOW = datetime(2026, 6, 30, 12, tzinfo=UTC)


def _auth_headers(subject: str = "auth0|tool_user") -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"User {suffix}",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _current_user_id(api_client: TestClient, subject: str = "auth0|tool_user") -> str:
    response = api_client.get("/me", headers=_auth_headers(subject))
    assert response.status_code == 200
    return response.json()["data"]["user"]["user_id"]


def _seed_user(session: Session, user_id: str) -> None:
    session.add(User(user_id=user_id))
    session.flush()


def _seed_region(
    session: Session,
    *,
    region_id: str = "greater_boston",
    display_name: str = "Greater Boston",
    expires_at: datetime | None = None,
) -> None:
    session.add(
        Region(
            region_id=region_id,
            region_name=region_id,
            display_name=display_name,
            region_type="metro",
        )
    )
    session.flush()
    session.add(
        RegionMarketScore(
            region_score_id=f"score_{region_id}",
            region_id=region_id,
            objective_opportunity_score=0.84,
            early_career_accessibility_score=0.77,
            score_ruleset_version="career_tool_test",
        )
    )
    session.flush()
    company_id = f"comp_{region_id}"
    session.add(
        Company(
            company_id=company_id,
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
                company_id=company_id,
                region_id=region_id,
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
                presence_confidence="high_confidence",
            ),
            CompanyRegionHiring(
                hiring_id=f"hiring_{region_id}",
                company_id=company_id,
                region_id=region_id,
                currently_hiring_flag=True,
                active_posting_count_now=8,
                posting_count_30d=12,
                role_family_summary={"software_engineering": 5},
                hiring_confidence="high_confidence",
                freshness_expires_at=expires_at or NOW + timedelta(days=30),
            ),
            CompanyRegionEntryLevel(
                entry_level_id=f"entry_{region_id}",
                company_id=company_id,
                region_id=region_id,
                internship_count=3,
                coop_count=1,
                entry_level_full_time_count=4,
                formal_early_career_program_flag=True,
                entry_level_access_score=0.77,
                entry_level_confidence="high_confidence",
                freshness_expires_at=expires_at or NOW + timedelta(days=30),
            ),
        ]
    )
    session.flush()


def _seed_opportunity(session: Session, *, paid_partner: bool = False) -> None:
    OpportunityService(OpportunityRepository(session)).create_opportunity(
        OpportunityCreate(
            opportunity_id="opp_tool_agent",
            employer_id="comp_greater_boston",
            employer_name="Greater Boston Systems",
            program_name="Grounded Internship",
            program_type=OpportunityProgramType.INTERNSHIP,
            location_mode=OpportunityLocationMode.HYBRID,
            seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
            eligibility_summary="Students and new graduates.",
            application_url="https://example.com/apply/tool-agent",
            source_url="https://example.com/source/tool-agent",
            source_type=OpportunitySourceType.EMPLOYER_OFFICIAL,
            application_deadline=date(2099, 1, 1),
            trust_label=OpportunityTrustLabel.VERIFIED,
            review_status=OpportunityReviewStatus.APPROVED,
            employer_influence=EmployerInfluenceMetadataCreate(
                partner_submitted=paid_partner,
                paid_partner=paid_partner,
                paid_partner_label="paid partner" if paid_partner else None,
                internal_review_notes="Internal-only note",
            ),
            sources=(
                OpportunitySourceCreate(
                    source_type=OpportunitySourceType.CAREER_CENTER,
                    source_url="https://example.edu/source/tool-agent",
                    source_name="Career Center",
                    collected_at=NOW,
                    verification_note="Public source checked.",
                ),
            ),
            region_bindings=(
                OpportunityRegionBindingCreate(
                    region_id="greater_boston",
                    region_label="Greater Boston",
                ),
            ),
            role_family_bindings=(
                OpportunityRoleFamilyBindingCreate(role_family="software_engineering"),
            ),
            created_at=NOW,
        )
    )


def _career_request(question_type: CareerAgentQuestionType = CareerAgentQuestionType.CITY_FIT):
    return CareerAgentRequest(
        question_type=question_type,
        target_region_ids=("greater_boston",),
        target_role_families=("software_engineering",),
        preferred_program_types=("internship",),
        preferred_location_modes=("hybrid",),
        include_forecasts=False,
        limit=3,
    )


def _plan_request() -> CareerActionPlanRequest:
    return CareerActionPlanRequest(
        plan_type="weekly_job_search_plan",
        career_goal="Find early-career software roles.",
        career_agent_request=_career_request(),
    )


def test_tool_preview_includes_evidence_freshness_uncertainty_and_privacy(
    session: Session,
) -> None:
    _seed_user(session, "user_tool_preview")
    _seed_region(session)

    preview = CareerAgentToolService(session).preview_tool(
        "user_tool_preview",
        CareerAgentToolRequest(
            tool_type=CareerAgentToolType.REMINDER,
            action_plan_request=_plan_request(),
        ),
        now=NOW,
    )

    assert preview.status is CareerAgentToolStatus.AWAITING_USER_APPROVAL
    assert preview.evidence_refs
    assert preview.freshness.source_count > 0
    assert preview.uncertainty.confidence_level.value in {"high", "medium", "low", "unknown"}
    assert preview.privacy_classification.value == "user_private"
    assert preview.approval_requirement.approval_required is True
    assert preview.user_visible_preview["runtime_wired"] is False


def test_approval_required_actions_cannot_bypass_explicit_approval(session: Session) -> None:
    _seed_user(session, "user_tool_approval")
    _seed_region(session)
    service = CareerAgentToolService(session)
    preview = service.preview_tool(
        "user_tool_approval",
        CareerAgentToolRequest(
            tool_type=CareerAgentToolType.WATCHLIST_UPDATE_SUGGESTION,
            career_agent_request=_career_request(),
        ),
        now=NOW,
    )

    with pytest.raises(CareerAgentToolApprovalError):
        service.approve_tool(
            "user_tool_approval",
            CareerAgentToolApproval(
                tool_request_id=preview.tool_request_id,
                explicit_user_approval=False,
            ),
            now=NOW,
        )

    approved = service.approve_tool(
        "user_tool_approval",
        CareerAgentToolApproval(
            tool_request_id=preview.tool_request_id,
            explicit_user_approval=True,
        ),
        now=NOW,
    )

    assert approved.status is CareerAgentToolStatus.APPROVED
    assert approved.runtime_execution_performed is False
    assert approved.tool_preview.user_visible_preview["runtime_wired"] is False


def test_export_preview_requires_approval_and_redacts_memory_by_default(session: Session) -> None:
    _seed_user(session, "user_tool_export")
    _seed_region(session)
    memory_profile = CareerMemoryService(session).update_memory(
        "user_tool_export",
        CareerMemoryUpdateRequest(
            explicit_user_permission=True,
            permissions=(
                CareerMemoryPermission(
                    category=CareerMemoryCategory.CAREER_CONSTRAINTS,
                    enabled=True,
                    personalize_allowed=True,
                ),
            ),
            entries=(
                CareerMemoryEntryInput(
                    category=CareerMemoryCategory.CAREER_CONSTRAINTS,
                    value="hybrid only",
                ),
            ),
        ),
    )

    preview = CareerAgentToolService(session).preview_tool(
        "user_tool_export",
        CareerAgentToolRequest(
            tool_type=CareerAgentToolType.CAREER_REPORT_EXPORT,
            career_agent_request=_career_request(),
            include_memory=True,
            include_private_memory_in_export=False,
        ),
        memory_profile=memory_profile,
        now=NOW,
    )

    assert preview.approval_requirement.approval_required is True
    assert preview.user_visible_preview["public_export_payload"]["private_memory_included"] is False
    assert "hybrid only" not in json.dumps(preview.user_visible_preview)
    assert "internal_review_notes" not in json.dumps(preview.model_dump(mode="json"))


def test_notification_and_watchlist_previews_require_approval(session: Session) -> None:
    _seed_user(session, "user_tool_state")
    _seed_region(session)
    service = CareerAgentToolService(session)

    for tool_type in (
        CareerAgentToolType.WATCHLIST_UPDATE_SUGGESTION,
        CareerAgentToolType.NOTIFICATION_PREFERENCE,
    ):
        preview = service.preview_tool(
            "user_tool_state",
            CareerAgentToolRequest(
                tool_type=tool_type,
                career_agent_request=_career_request(),
            ),
            now=NOW,
        )
        assert preview.approval_requirement.approval_required is True
        assert preview.runtime_execution_performed is False


def test_outreach_can_be_drafted_but_not_sent(session: Session) -> None:
    _seed_user(session, "user_tool_outreach")
    _seed_region(session)
    service = CareerAgentToolService(session)

    draft = service.preview_tool(
        "user_tool_outreach",
        CareerAgentToolRequest(
            tool_type=CareerAgentToolType.OUTREACH_DRAFT,
            career_agent_request=_career_request(),
            draft_recipient_role="alumni contact",
            user_context_claims=("I am a senior studying computer science.",),
        ),
        now=NOW,
    )

    assert draft.status is CareerAgentToolStatus.DRAFTED
    assert draft.approval_requirement.approval_required is False
    assert draft.user_visible_preview["send_enabled"] is False
    assert "Evidence-backed context" in draft.user_visible_preview["draft_body"]
    assert "User-provided context" in draft.user_visible_preview["draft_body"]

    blocked = service.preview_tool(
        "user_tool_outreach",
        CareerAgentToolRequest(
            tool_type=CareerAgentToolType.OUTREACH_DRAFT,
            career_agent_request=_career_request(),
            requested_action=CareerAgentRequestedToolAction.SEND,
        ),
        now=NOW + timedelta(seconds=1),
    )
    assert blocked.status is CareerAgentToolStatus.BLOCKED
    assert blocked.action_boundary.value == "external_contact"
    assert blocked.approval_requirement.boundary is blocked.action_boundary

    with pytest.raises(CareerAgentToolApprovalError):
        service.approve_tool(
            "user_tool_outreach",
            CareerAgentToolApproval(
                tool_request_id=blocked.tool_request_id,
                explicit_user_approval=True,
            ),
            now=NOW,
        )
    with pytest.raises(CareerAgentToolApprovalError):
        service.reject_tool(
            "user_tool_outreach",
            CareerAgentToolApproval(tool_request_id=blocked.tool_request_id),
            now=NOW,
        )


def test_application_checklist_does_not_imply_submission_and_blocks_autonomous_application(
    session: Session,
) -> None:
    _seed_user(session, "user_tool_application")
    _seed_region(session)
    _seed_opportunity(session)
    service = CareerAgentToolService(session)

    checklist = service.preview_tool(
        "user_tool_application",
        CareerAgentToolRequest(
            tool_type=CareerAgentToolType.APPLICATION_PREP_CHECKLIST,
            career_agent_request=_career_request(CareerAgentQuestionType.WHERE_SHOULD_I_APPLY),
            target_opportunity_ids=("opp_tool_agent",),
        ),
        now=NOW,
    )

    assert checklist.status is CareerAgentToolStatus.PREVIEW_READY
    assert checklist.user_visible_preview["submission_performed"] is False
    assert "submitted" not in json.dumps(checklist.user_visible_preview).casefold()

    blocked = service.preview_tool(
        "user_tool_application",
        CareerAgentToolRequest(
            tool_type=CareerAgentToolType.JOB_APPLICATION_SUBMISSION,
            career_agent_request=_career_request(CareerAgentQuestionType.WHERE_SHOULD_I_APPLY),
            requested_action=CareerAgentRequestedToolAction.SUBMIT_APPLICATION,
        ),
        now=NOW + timedelta(seconds=1),
    )
    assert blocked.status is CareerAgentToolStatus.BLOCKED

    with pytest.raises(CareerAgentToolApprovalError):
        service.approve_tool(
            "user_tool_application",
            CareerAgentToolApproval(
                tool_request_id=blocked.tool_request_id,
                explicit_user_approval=True,
            ),
            now=NOW,
        )
    with pytest.raises(CareerAgentToolApprovalError):
        service.reject_tool(
            "user_tool_application",
            CareerAgentToolApproval(tool_request_id=blocked.tool_request_id),
            now=NOW,
        )


def test_unsupported_fabricated_opportunity_action_is_blocked(session: Session) -> None:
    _seed_user(session, "user_tool_fabricated")
    _seed_region(session)

    preview = CareerAgentToolService(session).preview_tool(
        "user_tool_fabricated",
        CareerAgentToolRequest(
            tool_type=CareerAgentToolType.APPLICATION_PREP_CHECKLIST,
            career_agent_request=_career_request(),
            target_opportunity_ids=("opp_fake",),
        ),
        now=NOW,
    )

    assert preview.status is CareerAgentToolStatus.BLOCKED
    assert "opp_fake" in preview.user_visible_preview["unsupported_opportunity_ids"]


def test_paid_partner_influence_is_disclosed_without_internal_notes(session: Session) -> None:
    _seed_user(session, "user_tool_partner")
    _seed_region(session)
    _seed_opportunity(session, paid_partner=True)

    preview = CareerAgentToolService(session).preview_tool(
        "user_tool_partner",
        CareerAgentToolRequest(
            tool_type=CareerAgentToolType.APPLICATION_PREP_CHECKLIST,
            career_agent_request=_career_request(CareerAgentQuestionType.WHERE_SHOULD_I_APPLY),
        ),
        now=NOW,
    )

    text = json.dumps(preview.model_dump(mode="json"))
    assert "Paid partner status is disclosed" in text or "Paid/partner influence" in text
    assert "Internal-only note" not in text
    assert "internal_review_notes" not in text


def test_tool_records_are_user_scoped_and_routes_are_protected(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_region(session)
    user_a_headers = _auth_headers("auth0|tool_a")
    user_b_headers = _auth_headers("auth0|tool_b")
    _current_user_id(api_client, "auth0|tool_a")
    _current_user_id(api_client, "auth0|tool_b")

    unauthenticated = api_client.get("/me/career-agent/tools")
    assert unauthenticated.status_code == 401

    created = api_client.post(
        "/me/career-agent/tools/preview",
        headers=user_a_headers,
        json={
            "tool_type": "reminder",
            "action_plan_request": _plan_request().model_dump(mode="json"),
        },
    )
    assert created.status_code == 200
    tool_id = created.json()["data"]["tool_request_id"]

    user_b_list = api_client.get("/me/career-agent/tools", headers=user_b_headers)
    assert user_b_list.status_code == 200
    assert user_b_list.json()["data"]["tool_previews"] == []

    missing_for_b = api_client.get(f"/me/career-agent/tools/{tool_id}", headers=user_b_headers)
    assert missing_for_b.status_code == 404

    bypass = api_client.post(
        "/me/career-agent/tools/approve",
        headers=user_a_headers,
        json={"tool_request_id": tool_id, "explicit_user_approval": False},
    )
    assert bypass.status_code == 400

    approved = api_client.post(
        "/me/career-agent/tools/approve",
        headers=user_a_headers,
        json={"tool_request_id": tool_id, "explicit_user_approval": True},
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["runtime_execution_performed"] is False


def test_rejection_transition_is_valid_and_prevents_later_approval(session: Session) -> None:
    _seed_user(session, "user_tool_reject")
    _seed_region(session)
    service = CareerAgentToolService(session)
    preview = service.preview_tool(
        "user_tool_reject",
        CareerAgentToolRequest(
            tool_type=CareerAgentToolType.NOTIFICATION_PREFERENCE,
            career_agent_request=_career_request(),
        ),
        now=NOW,
    )

    rejected = service.reject_tool(
        "user_tool_reject",
        CareerAgentToolApproval(tool_request_id=preview.tool_request_id),
        now=NOW,
    )
    assert rejected.status is CareerAgentToolStatus.REJECTED

    with pytest.raises(CareerAgentToolApprovalError):
        service.approve_tool(
            "user_tool_reject",
            CareerAgentToolApproval(
                tool_request_id=preview.tool_request_id,
                explicit_user_approval=True,
            ),
            now=NOW,
        )
