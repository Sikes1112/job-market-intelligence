from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.companies.models import Company
from backend.config.settings import Settings
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.opportunities.models import Opportunity, OpportunityReviewActionRecord
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
    OpportunitySourceType,
    OpportunityTrustLabel,
)
from backend.opportunities.service import OpportunityService
from backend.scoring.models import RegionMarketScore
from backend.trust.report_schemas import UserReportCreate
from backend.trust.reports import UserReportService
from backend.trust.schemas import (
    TrustAssessmentSubjectType,
    UserReportSeverity,
    UserReportType,
)
from backend.users.models import SavedMarketArtifact

NOW = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)


def test_dashboard_endpoint_returns_structured_empty_response(api_client: TestClient) -> None:
    response = api_client.get("/user-intelligence/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    payload = body["data"]
    assert payload["dashboard_version"] == "30.1"
    assert payload["recommended_regions"] == []
    assert payload["recommended_companies"] == []
    assert payload["recommended_opportunities"] == []
    assert payload["market_warnings"] == []
    assert payload["forecast_changes"] == []
    assert payload["saved_items"] == []
    assert payload["recommended_next_actions"] == []
    assert payload["trust_context"]["uses_existing_metadata_only"] is False
    assert payload["trust_context"]["layer_30_full_trust_engine_available"] is True


def test_dashboard_surfaces_existing_metadata_without_mutation(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_market(session)
    _seed_partner_opportunity(session)
    before_counts = _table_counts(session)

    response = api_client.get("/user-intelligence/dashboard")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["summary"]["recommendation_count"] == 4
    assert payload["recommended_regions"][0]["region_id"] == "greater_boston"
    assert payload["recommended_regions"][0]["freshness"] == "unknown"
    assert payload["recommended_regions"][0]["confidence"] == "warning"
    assert payload["recommended_regions"][0]["ranking_influence_allowed"] is None
    assert payload["recommended_regions"][0]["trust_tier"] is None
    assert payload["recommended_companies"][0]["company_id"] == "comp_alpha"
    assert "Source evidence is unknown" in payload["recommended_companies"][0]["warnings"][0]

    opportunity = payload["recommended_opportunities"][0]
    assert opportunity["opportunity_id"] == "opp_partner_unverified"
    assert opportunity["trust_label"] == "partner_submitted"
    assert opportunity["trust_tier"] == "partner_submitted"
    assert opportunity["evidence_summary"]["trust_tier"] == "partner_submitted"
    assert opportunity["review_status"] == "pending_review"
    assert opportunity["partner_submitted"] is True
    assert opportunity["ranking_influence_allowed"] is False
    assert opportunity["risk_level"] == "medium"
    assert opportunity["routing_outcome"] == "visible_with_warning"
    assert opportunity["ranking_influence_decision"] == "denied"
    assert "partner_submitted_not_verified" in opportunity[
        "ranking_influence_reason_codes"
    ]
    assert opportunity["trust_explanation"]["trust_label"] == "Partner-submitted"
    assert opportunity["trust_explanation"]["risk_label"] == "Use with caution"
    assert opportunity["trust_explanation"]["routing_label"] == "Visible with warning"
    assert opportunity["trust_explanation"]["ranking_influence_label"] == (
        "Excluded from rankings"
    )
    assert opportunity["trust_explanation"]["ranking_influence_allowed"] is False
    assert any("not allowed to influence rankings" in item for item in opportunity["warnings"])
    assert payload["market_warnings"]
    assert payload["recommended_next_actions"]

    serialized = str(payload)
    assert "Internal routing note must not leak" not in serialized
    assert "reviewer_identity" not in serialized
    assert "reviewer_id" not in serialized
    assert _table_counts(session) == before_counts


def test_dashboard_limits_do_not_fabricate_items(api_client: TestClient, session: Session) -> None:
    _seed_market(session)
    response = api_client.get(
        "/user-intelligence/dashboard"
        "?region_limit=0&company_limit=0&opportunity_limit=0&forecast_limit=0"
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["summary"]["recommendation_count"] == 0
    assert payload["recommended_regions"] == []
    assert payload["recommended_companies"] == []
    assert payload["recommended_opportunities"] == []
    assert payload["forecast_changes"] == []


def test_dashboard_surfaces_safe_exception_status(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_market(session)
    _seed_partner_opportunity(session)
    UserReportService(session, clock=lambda: NOW).submit_report(
        UserReportCreate(
            subject_type=TrustAssessmentSubjectType.OPPORTUNITY,
            subject_id="opp_partner_unverified",
            report_type=UserReportType.SPAM,
            severity=UserReportSeverity.CRITICAL,
        )
    )

    response = api_client.get("/user-intelligence/dashboard")

    assert response.status_code == 200
    opportunity = response.json()["data"]["recommended_opportunities"][0]
    assert opportunity["exception_status"]["public_safe_status"] == "blocked"
    assert opportunity["trust_explanation"]["exception_status"]["label"] == "Blocked"
    assert any(
        action["action_code"] == "avoid_exception_item"
        for action in response.json()["data"]["recommended_next_actions"]
    )
    serialized = response.text
    assert "internal_notes" not in serialized
    assert "assigned_owner" not in serialized


def test_dashboard_surfaces_authenticated_saved_items(
    api_client: TestClient,
    session: Session,
) -> None:
    headers = _auth_headers("auth0|dashboard_saved")
    profile = api_client.get("/me", headers=headers)
    user_id = profile.json()["data"]["user"]["user_id"]
    session.add(
        SavedMarketArtifact(
            saved_artifact_id="saved_region_boston",
            user_id=user_id,
            artifact_type="region",
            artifact_ref="greater_boston",
            label="Greater Boston",
            notes="Watch this market",
        )
    )
    session.flush()

    response = api_client.get("/user-intelligence/dashboard", headers=headers)

    assert response.status_code == 200
    saved_items = response.json()["data"]["saved_items"]
    assert saved_items == [
        {
            "item_id": "saved_region_boston",
            "item_type": "region",
            "label": "Greater Boston",
            "target_route": "/markets/region/greater_boston",
            "metadata": {
                "artifact_ref": "greater_boston",
                "notes": "Watch this market",
            },
        }
    ]


def test_public_demo_allows_user_intelligence_dashboard(session: Session) -> None:
    _seed_market(session)
    app = create_app(
        engine=session.bind,
        settings=Settings(
            app_env="public_demo",
            database_url="sqlite:///explicit-demo.db",
            cors_allowed_origins="https://demo.example",
            _env_file=None,
        ),
    )

    def _override_get_session() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    client = TestClient(app)

    response = client.get("/user-intelligence/dashboard")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["dashboard_version"] == "30.1"
    assert "recommended_regions" in payload


def _seed_market(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="metro",
            ),
            Region(
                region_id="greater_atlanta",
                region_name="greater_atlanta",
                display_name="Greater Atlanta",
                region_type="metro",
            ),
            Company(
                company_id="comp_alpha",
                company_name="Alpha Systems",
                normalized_company_name="alpha systems",
                sector_primary="software",
                eligibility_status="eligible",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            RegionMarketScore(
                region_score_id="score_boston",
                region_id="greater_boston",
                objective_opportunity_score=0.82,
                early_career_accessibility_score=0.71,
                score_ruleset_version="canonical_v1",
            ),
            RegionMarketScore(
                region_score_id="score_atlanta",
                region_id="greater_atlanta",
                objective_opportunity_score=0.61,
                early_career_accessibility_score=0.66,
                score_ruleset_version="canonical_v1",
            ),
            CompanyRegionHiring(
                hiring_id="hiring_alpha_boston",
                company_id="comp_alpha",
                region_id="greater_boston",
                currently_hiring_flag=True,
                active_posting_count_now=4,
                hiring_confidence="medium",
            ),
            CompanyRegionEntryLevel(
                entry_level_id="entry_alpha_boston",
                company_id="comp_alpha",
                region_id="greater_boston",
                internship_count=2,
                formal_early_career_program_flag=True,
                entry_level_access_score=0.74,
                entry_level_confidence="medium",
            ),
        ]
    )
    session.flush()


def _auth_headers(subject: str = "auth0|dashboard_user") -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"User {suffix}",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _seed_partner_opportunity(session: Session) -> None:
    OpportunityService(OpportunityRepository(session)).create_opportunity(
        OpportunityCreate(
            opportunity_id="opp_partner_unverified",
            employer_id="comp_alpha",
            employer_name="Alpha Systems",
            program_name="Partner Submitted Analyst Internship",
            program_type=OpportunityProgramType.INTERNSHIP,
            location_mode=OpportunityLocationMode.HYBRID,
            seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
            eligibility_summary="Entry-level analyst internship.",
            application_url="https://example.com/apply/partner",
            source_url="https://example.com/source/partner",
            source_type=OpportunitySourceType.PARTNER_SUBMITTED,
            application_deadline=date(2099, 1, 1),
            trust_label=OpportunityTrustLabel.PARTNER_SUBMITTED,
            review_status=OpportunityReviewStatus.PENDING_REVIEW,
            employer_influence=EmployerInfluenceMetadataCreate(
                partner_submitted=True,
                paid_partner=False,
                internal_review_notes="Internal routing note must not leak",
            ),
            region_bindings=(
                OpportunityRegionBindingCreate(
                    region_id="greater_boston",
                    region_label="Greater Boston",
                ),
            ),
            role_family_bindings=(
                OpportunityRoleFamilyBindingCreate(role_family="data_analytics"),
            ),
            created_at=NOW,
        )
    )
    session.flush()


def _table_counts(session: Session) -> dict[str, int]:
    return {
        "regions": session.scalar(select(func.count()).select_from(Region)) or 0,
        "companies": session.scalar(select(func.count()).select_from(Company)) or 0,
        "scores": session.scalar(select(func.count()).select_from(RegionMarketScore)) or 0,
        "opportunities": session.scalar(select(func.count()).select_from(Opportunity)) or 0,
        "opportunity_reviews": (
            session.scalar(select(func.count()).select_from(OpportunityReviewActionRecord))
            or 0
        ),
    }
