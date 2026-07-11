from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.admin.models import AdminOverride, AdminRepairAction
from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.api.protection import _public_demo_route_allowed
from backend.companies.models import Company
from backend.config.settings import Settings
from backend.data_standards.models import (
    DataStandardCandidateFactRecord,
    DataStandardPartnerSubmissionRecord,
)
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.opportunities.models import Opportunity, OpportunitySubmission
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore
from backend.users.models import User, UserPreferenceProfile


def _settings(app_env: str, **overrides) -> Settings:
    database_url = (
        "postgresql://user:secret@example.test/demo"
        if app_env in {"staging", "production", "prod"}
        else "sqlite:///explicit-demo.db"
    )
    return Settings(
        app_env=app_env,
        database_url=database_url,
        cors_allowed_origins=("https://demo.example" if app_env == "public_demo" else ""),
        **overrides,
        _env_file=None,
    )


def _api_client_for_env(session: Session, app_env: str, **settings_overrides) -> TestClient:
    app = create_app(
        engine=session.bind,
        settings=_settings(app_env, **settings_overrides),
    )

    def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    return TestClient(app)


def _auth_headers(subject: str = "auth0|public_demo_user") -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"User {suffix}",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _seed_public_world(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Region(
                region_id="greater_sf",
                region_name="greater_sf",
                display_name="Greater SF",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_a",
                company_name="Example",
                normalized_company_name="example",
                eligibility_status="eligible",
                sector_primary="ai",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id="p_a_boston",
                company_id="comp_a",
                region_id="greater_boston",
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
            ),
            CompanyRegionHiring(
                hiring_id="h_a_boston",
                company_id="comp_a",
                region_id="greater_boston",
                currently_hiring_flag=True,
                active_posting_count_now=3,
                role_family_summary={"product": 2},
            ),
            CompanyRegionEntryLevel(
                entry_level_id="e_a_boston",
                company_id="comp_a",
                region_id="greater_boston",
                internship_count=1,
                entry_level_access_score=0.6,
            ),
            RegionMarketScore(
                region_score_id="rms_boston",
                region_id="greater_boston",
                objective_opportunity_score=0.74,
                early_career_accessibility_score=0.7,
                score_ruleset_version="marketscore_v1",
            ),
            RegionMarketScore(
                region_score_id="rms_sf",
                region_id="greater_sf",
                objective_opportunity_score=0.66,
                early_career_accessibility_score=0.5,
                score_ruleset_version="marketscore_v1",
            ),
        ]
    )
    session.flush()


def _assert_public_demo_denied(response) -> None:
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["type"] == "public_demo_read_only"
    assert "approved read-only routes" in body["error"]["message"]


def test_public_demo_allows_frontend_public_read_and_metadata_routes(
    session: Session,
) -> None:
    client = _api_client_for_env(session, "public_demo")
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200

    _seed_public_world(session)

    get_paths = [
        "/regions",
        "/regions/search",
        "/regions/greater_boston",
        "/regions/greater_boston/sources",
        "/companies/search",
        "/companies/comp_a",
        "/companies/comp_a/regions",
        "/companies/comp_a/sources",
        "/compare?region_a=greater_boston&region_b=greater_sf",
        "/recommendations/goal-modes",
        "/trust/explanation?subject_type=opportunity&subject_id=missing",
        "/user-intelligence/dashboard",
        "/monetization/plans",
        "/monetization/features",
        "/monetization/reports",
        "/monetization/access-preview?feature_key=basic_recommendation_preview",
        "/billing/status",
    ]

    for path in get_paths:
        response = client.get(path)
        assert response.status_code == 200, path

    discovery = client.post(
        "/discover/personalized",
        json={"region_ids": ["greater_boston"], "role_targets": ["product"]},
    )
    assert discovery.status_code == 200
    assert discovery.json()["data"]["ranked_regions"][0]["region_id"] == "greater_boston"

    strategy = client.post(
        "/recommendations/strategy",
        json={"goal_mode": "maximize_entry_level_access"},
    )
    assert strategy.status_code == 200
    assert strategy.json()["data"]["ranked_region_recommendations"]

    action_plan = client.post(
        "/career-agent/action-plans",
        json={
            "plan_type": "regional_targeting_plan",
            "career_agent_request": {
                "question_type": "strongest_market_strategy",
                "target_region_ids": ["greater_boston", "greater_sf"],
                "include_forecasts": False,
            },
        },
    )
    assert action_plan.status_code == 200
    assert action_plan.json()["data"]["steps"]


def test_public_demo_allows_imported_market_operation_reads_only() -> None:
    assert _public_demo_route_allowed("GET", "/markets/imported")
    assert _public_demo_route_allowed("GET", "/markets/imported/health")
    for endpoint in (
        "health",
        "sources",
        "facts",
        "gaps",
        "ranking-diagnostics",
        "refresh-readiness",
        "diff-preview",
    ):
        assert _public_demo_route_allowed("GET", f"/markets/imported/nyc/{endpoint}")
        assert not _public_demo_route_allowed("POST", f"/markets/imported/nyc/{endpoint}")
    assert not _public_demo_route_allowed("GET", "/markets/imported/nyc/apply")


def test_public_demo_denies_admin_and_override_mutations_before_auth(
    session: Session,
) -> None:
    _seed_public_world(session)
    client = _api_client_for_env(session, "public_demo")

    responses = [
        client.post(
            "/admin/overrides",
            json={
                "target_type": "company",
                "target_id": "comp_a",
                "override_type": "company_eligibility",
                "override_value": {"eligibility_status": "eligible"},
                "reason": "not allowed in public demo",
                "source_evidence": {"source_ids": ["source_a"]},
            },
        ),
        client.post(
            "/admin/overrides/override_1/activate",
            json={"reason": "not allowed in public demo"},
        ),
        client.post(
            "/admin/repair-actions/repair_1/execute",
            json={"reason": "not allowed in public demo"},
        ),
    ]

    for response in responses:
        _assert_public_demo_denied(response)
    assert session.query(AdminOverride).count() == 0
    assert session.query(AdminRepairAction).count() == 0


def test_public_demo_denies_billing_checkout_and_webhook_writes(
    session: Session,
) -> None:
    client = _api_client_for_env(session, "public_demo")

    _assert_public_demo_denied(
        client.post(
            "/billing/checkout-session",
            headers=_auth_headers(),
            json={"plan_key": "individual_monthly"},
        )
    )
    _assert_public_demo_denied(
        client.post(
            "/billing/stripe/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=bad"},
        )
    )


def test_public_demo_denies_layer_27_28_data_standards_routes(session: Session) -> None:
    client = _api_client_for_env(session, "public_demo")

    assert client.get("/data-standards/definitions").status_code == 200
    assert client.get("/data-standards/partner-schema").status_code == 200
    assert client.get("/data-standards/partners").status_code == 200
    assert client.get("/data-standards/partners/partner_state_university").status_code == 200
    assert client.get("/data-standards/quality-labels").status_code == 200
    assert client.get("/data-standards/governance-framework").status_code == 200
    _assert_public_demo_denied(
        client.post(
            "/data-standards/quality-labels/evaluate",
            json={"label": "verified_partner_data"},
        )
    )
    _assert_public_demo_denied(
        client.post(
            "/data-standards/partner-submissions/validate",
            json={"submission_id": "demo_sub"},
        )
    )
    _assert_public_demo_denied(
        client.post(
            "/data-standards/partner-submissions",
            json={"submission_id": "demo_sub"},
        )
    )
    _assert_public_demo_denied(
        client.post("/data-standards/partner-submissions/demo_sub/candidates")
    )
    _assert_public_demo_denied(
        client.post(
            "/data-standards/candidates/candidate_demo/review",
            json={
                "decision": "approve_for_merge",
                "reviewer_id": "demo_reviewer",
            },
        )
    )
    _assert_public_demo_denied(
        client.post("/data-standards/candidates/candidate_demo/merge-preview")
    )
    _assert_public_demo_denied(
        client.post(
            "/data-standards/candidates/candidate_demo/merge",
            json={"merged_by": "demo_admin", "reason": "not allowed"},
        )
    )

    assert session.query(DataStandardPartnerSubmissionRecord).count() == 0
    assert session.query(DataStandardCandidateFactRecord).count() == 0


def test_public_demo_denies_opportunity_submission_and_review_routes(
    session: Session,
) -> None:
    client = _api_client_for_env(session, "public_demo")

    _assert_public_demo_denied(
        client.post(
            "/opportunities/submissions",
            headers=_auth_headers(),
            json={
                "submission_id": "sub_demo_opportunity",
                "opportunity_id": "opp_demo_opportunity",
                "employer_name": "Demo Employer",
                "program_name": "Demo Internship",
                "program_type": "internship",
                "location_mode": "hybrid",
                "seniority_level": "internship",
                "eligibility_summary": "Demo eligibility.",
                "application_url": "https://example.com/apply",
                "role_family_bindings": [{"role_family": "software_engineering"}],
                "region_bindings": [{"region_label": "Greater Boston"}],
            },
        )
    )
    _assert_public_demo_denied(
        client.post(
            "/opportunities/submissions/sub_demo_opportunity/review",
            headers=_auth_headers(),
            json={
                "review_action": "approve_as_verified",
                "reviewer_id": "demo_reviewer",
            },
        )
    )

    assert session.query(Opportunity).count() == 0
    assert session.query(OpportunitySubmission).count() == 0


def test_public_demo_denies_protected_gets_that_can_create_user_state(
    session: Session,
) -> None:
    client = _api_client_for_env(session, "public_demo")

    _assert_public_demo_denied(client.get("/me", headers=_auth_headers()))
    _assert_public_demo_denied(client.get("/me/alerts", headers=_auth_headers()))
    _assert_public_demo_denied(client.get("/me/career-memory", headers=_auth_headers()))
    _assert_public_demo_denied(client.get("/me/career-agent/tools", headers=_auth_headers()))
    _assert_public_demo_denied(client.get("/admin/me", headers=_auth_headers()))
    _assert_public_demo_denied(
        client.post(
            "/me/explanations/region",
            headers=_auth_headers(),
            json={
                "evidence": {
                    "entity_type": "region",
                    "subject_refs": {"region_id": "greater_boston"},
                }
            },
        )
    )

    assert session.query(User).count() == 0


def test_public_demo_denies_user_preference_snapshot_and_artifact_writes(
    session: Session,
) -> None:
    client = _api_client_for_env(session, "public_demo")
    headers = _auth_headers()

    responses = [
        client.put(
            "/me/preferences",
            headers=headers,
            json={"role_interests": ["product"]},
        ),
        client.delete("/me/preferences", headers=headers),
        client.post(
            "/me/saved-market-artifacts",
            headers=headers,
            json={"artifact_type": "region", "artifact_ref": "greater_boston"},
        ),
        client.post(
            "/me/recommendation-snapshots",
            headers=headers,
            json={
                "personalized_output": {"ranked_regions": []},
                "recommendation_version": "personalized_rec_v1",
                "source_version_bundle": {"source": 1},
                "objective_output_refs": [{"output_type": "region"}],
                "recommendation_inputs_hash": "sha256:public-demo",
                "generated_at": "2026-05-25T12:00:00+00:00",
            },
        ),
        client.post("/me/alerts/user_alert_1/read", headers=headers),
        client.post("/me/alerts/user_alert_1/dismiss", headers=headers),
        client.delete("/me", headers=headers),
    ]

    for response in responses:
        _assert_public_demo_denied(response)
    assert session.query(User).count() == 0
    assert session.query(UserPreferenceProfile).count() == 0


def test_public_demo_denies_canonical_write_shaped_requests_even_without_routes(
    session: Session,
) -> None:
    _seed_public_world(session)
    client = _api_client_for_env(session, "public_demo")

    response = client.patch(
        "/regions/greater_boston",
        json={"display_name": "Mutated Boston"},
    )

    _assert_public_demo_denied(response)
    assert session.get(Region, "greater_boston").display_name == "Greater Boston"


def test_public_demo_rate_limit_applies_to_public_read_routes_but_not_monitors(
    session: Session,
) -> None:
    _seed_public_world(session)
    client = _api_client_for_env(
        session,
        "public_demo",
        rate_limit_requests=2,
        rate_limit_window_seconds=60,
    )

    assert client.get("/regions").status_code == 200
    assert client.get("/regions/search").status_code == 200
    response = client.get("/regions", headers={"X-Request-ID": "rate-demo-1"})

    assert response.status_code == 429
    assert response.headers["x-request-id"] == "rate-demo-1"
    assert response.headers["retry-after"]
    assert response.json() == {
        "error": {
            "type": "rate_limited",
            "message": "Too many requests",
            "request_id": "rate-demo-1",
        }
    }
    assert "Traceback" not in response.text
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_public_demo_oversized_allowed_post_is_rejected_safely(
    session: Session,
) -> None:
    _seed_public_world(session)
    client = _api_client_for_env(
        session,
        "public_demo",
        max_request_body_bytes=24,
        rate_limit_requests=10,
    )

    response = client.post(
        "/discover/personalized",
        headers={"X-Request-ID": "large-public-demo-1"},
        json={
            "region_ids": ["greater_boston", "greater_sf"],
            "role_targets": ["product", "cybersecurity"],
            "notes": "x" * 200,
        },
    )

    assert response.status_code == 413
    assert response.headers["x-request-id"] == "large-public-demo-1"
    assert response.json() == {
        "error": {
            "type": "request_too_large",
            "message": "Request body too large",
            "request_id": "large-public-demo-1",
        }
    }
    assert "cybersecurity" not in response.text
    assert "Traceback" not in response.text


def test_public_demo_mutation_denial_still_precedes_rate_limit(
    session: Session,
) -> None:
    _seed_public_world(session)
    client = _api_client_for_env(session, "public_demo", rate_limit_requests=1)

    assert client.get("/regions").status_code == 200
    response = client.post(
        "/admin/overrides",
        json={"target_id": "comp_a", "reason": "not allowed"},
    )

    _assert_public_demo_denied(response)


def test_public_demo_denial_response_is_safe_and_monitorable(session: Session) -> None:
    client = _api_client_for_env(session, "public_demo")

    response = client.post(
        "/admin/overrides",
        headers={"X-Request-ID": "public-demo-safe-error-1"},
        json={"reason": "postgresql://user:secret@example/db"},
    )

    _assert_public_demo_denied(response)
    assert response.headers["x-request-id"] == "public-demo-safe-error-1"
    assert response.json()["error"]["request_id"] == "public-demo-safe-error-1"
    assert "secret" not in response.text
    assert "Traceback" not in response.text


def test_ingestion_and_refresh_api_routes_are_not_registered(session: Session) -> None:
    client = _api_client_for_env(session, "public_demo")
    routes = {route.path for route in client.app.routes if hasattr(route, "path")}

    assert not any(path.startswith("/ingestion") for path in routes)
    assert not any(path.startswith("/refresh") for path in routes)
    assert not any(path.startswith("/admin/refresh") for path in routes)


def test_local_private_demo_and_staging_do_not_get_global_read_only_block(
    session: Session,
) -> None:
    for app_env in ("local", "private_demo", "staging"):
        client = _api_client_for_env(session, app_env)

        response = client.post("/definitely-not-a-route", json={"probe": True})

        assert response.status_code != 403
        assert response.json()["error"]["type"] == "not_found"
