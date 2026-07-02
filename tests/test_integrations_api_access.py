from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.admin.roles import AdminRole
from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.institutions.models import Organization, OrganizationMembership
from backend.institutions.roles import OrganizationRole
from backend.integrations.models import ApiKey, ApiUsageRecord
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore
from backend.users.models import User


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


def _current_user_id(api_client, subject: str) -> tuple[dict[str, str], str]:
    headers = _auth_headers(subject)
    response = api_client.get("/me", headers=headers)
    assert response.status_code == 200
    return headers, response.json()["data"]["user"]["user_id"]


def _make_admin(session: Session, user_id: str) -> None:
    user = session.get(User, user_id)
    assert user is not None
    user.admin_role = AdminRole.ADMIN.value
    session.flush()


def _seed_org(
    session: Session,
    *,
    organization_id: str,
    user_id: str | None = None,
    role: OrganizationRole = OrganizationRole.ORG_ADMIN,
) -> None:
    if session.get(Organization, organization_id) is None:
        session.add(
            Organization(
                organization_id=organization_id,
                name=organization_id.replace("_", " ").title(),
                organization_type="career_center",
                status="active",
            )
        )
        session.flush()
    if user_id:
        session.add(
            OrganizationMembership(
                organization_membership_id=(
                    f"mem_{organization_id}_{user_id}_{role.value}".replace("|", "_")[:64]
                ),
                organization_id=organization_id,
                user_id=user_id,
                role=role.value,
                status="active",
            )
        )
        session.flush()


def _seed_market(session: Session) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.add(
        Company(
            company_id="comp_alpha",
            company_name="Alpha Systems",
            normalized_company_name="alpha systems",
            sector_primary="software",
            eligibility_status="eligible",
            classification_confidence="high",
            prestige_score=0.71,
        )
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id="presence_alpha_boston",
                company_id="comp_alpha",
                region_id="greater_boston",
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
                presence_confidence="high",
            ),
            CompanyRegionHiring(
                hiring_id="hiring_alpha_boston",
                company_id="comp_alpha",
                region_id="greater_boston",
                currently_hiring_flag=True,
                active_posting_count_now=12,
                posting_count_30d=18,
                posting_count_90d=42,
                hiring_confidence="high",
            ),
            CompanyRegionEntryLevel(
                entry_level_id="entry_alpha_boston",
                company_id="comp_alpha",
                region_id="greater_boston",
                internship_count=4,
                coop_count=2,
                entry_level_full_time_count=5,
                formal_early_career_program_flag=True,
                entry_level_access_score=0.82,
                entry_level_confidence="high",
            ),
            RegionMarketScore(
                region_score_id="score_boston",
                region_id="greater_boston",
                structural_ecosystem_score=0.73,
                live_market_score=0.68,
                objective_opportunity_score=0.81,
                raw_total_score=0.77,
                general_density_score=0.7,
                tech_market_density_score=0.72,
                early_career_accessibility_score=0.86,
                score_ruleset_version="internal_ruleset_v1",
            ),
        ]
    )
    session.flush()


def _create_api_client(
    api_client,
    headers: dict[str, str],
    *,
    scopes: list[str],
    organization_id: str | None = None,
    rate_limit_count: int = 60,
    rate_limit_window_seconds: int = 3600,
) -> dict:
    body = {
        "display_name": "Layer 17C test client",
        "scopes": scopes,
        "organization_id": organization_id,
        "rate_limit_count": rate_limit_count,
        "rate_limit_window_seconds": rate_limit_window_seconds,
        "allowed_origins": [],
    }
    response = api_client.post("/api/integrations/api-clients", headers=headers, json=body)
    assert response.status_code == 201
    return response.json()["data"]["api_client"]


def _create_api_key(
    api_client,
    headers: dict[str, str],
    api_client_id: str,
) -> dict:
    response = api_client.post(
        f"/api/integrations/api-clients/{api_client_id}/keys",
        headers=headers,
        json={},
    )
    assert response.status_code == 201
    return response.json()["data"]["api_key"]


def test_api_client_key_creation_reveals_raw_key_once(api_client, session: Session) -> None:
    headers, user_id = _current_user_id(api_client, "auth0|api_admin")
    _make_admin(session, user_id)

    client_payload = _create_api_client(api_client, headers, scopes=["region:read"])
    key_payload = _create_api_key(api_client, headers, client_payload["api_client_id"])

    assert key_payload["raw_key"].startswith("jmi_live_")
    assert key_payload["revealed_once"] is True
    assert "..." in key_payload["display_key"]

    row = session.get(ApiKey, key_payload["api_key_id"])
    assert row is not None
    assert not hasattr(row, "raw_key")
    assert row.key_hash != key_payload["raw_key"]
    assert row.display_key == key_payload["display_key"]

    listed = api_client.get("/api/integrations/api-clients", headers=headers)
    assert listed.status_code == 200
    serialized = json.dumps(listed.json())
    assert key_payload["raw_key"] not in serialized
    listed_key = listed.json()["data"]["api_clients"][0]["keys"][0]
    assert listed_key["raw_key"] is None
    assert listed_key["revealed_once"] is False


def test_invalid_revoked_and_missing_scope_fail_safely(api_client, session: Session) -> None:
    _seed_market(session)
    headers, user_id = _current_user_id(api_client, "auth0|api_scope_admin")
    _make_admin(session, user_id)
    client_payload = _create_api_client(api_client, headers, scopes=["region:read"])
    key_payload = _create_api_key(api_client, headers, client_payload["api_client_id"])
    raw_key = key_payload["raw_key"]

    invalid = api_client.get(
        "/api/external/v1/regions",
        headers={"X-API-Key": "jmi_live_invalid"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "INVALID_API_KEY"

    missing_scope = api_client.get(
        "/api/external/v1/companies/comp_alpha/geography",
        headers={"X-API-Key": raw_key},
    )
    assert missing_scope.status_code == 403
    assert missing_scope.json()["error"]["code"] == "MISSING_SCOPE"

    revoked = api_client.post(
        f"/api/integrations/api-keys/{key_payload['api_key_id']}/revoke",
        headers=headers,
    )
    assert revoked.status_code == 200
    after_revoke = api_client.get(
        "/api/external/v1/regions",
        headers={"X-API-Key": raw_key},
    )
    assert after_revoke.status_code == 401
    assert after_revoke.json()["error"]["code"] == "INVALID_API_KEY"


def test_external_api_rate_limit_allows_exhausts_and_resets(
    api_client,
    session: Session,
) -> None:
    _seed_market(session)
    headers, user_id = _current_user_id(api_client, "auth0|api_rate_admin")
    _make_admin(session, user_id)
    client_payload = _create_api_client(
        api_client,
        headers,
        scopes=["region:read"],
        rate_limit_count=1,
        rate_limit_window_seconds=60,
    )
    key_payload = _create_api_key(api_client, headers, client_payload["api_client_id"])
    raw_key = key_payload["raw_key"]

    allowed = api_client.get(
        "/api/external/v1/regions",
        headers={"X-API-Key": raw_key},
    )
    assert allowed.status_code == 200
    assert allowed.json()["meta"]["rate_limit"]["remaining"] == 0

    exhausted = api_client.get(
        "/api/external/v1/regions",
        headers={"X-API-Key": raw_key},
    )
    assert exhausted.status_code == 429
    assert exhausted.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert exhausted.json()["meta"]["rate_limit"]["limit"] == 1

    for usage in session.query(ApiUsageRecord).all():
        usage.occurred_at = datetime.now(UTC) - timedelta(seconds=120)
    session.flush()

    reset = api_client.get(
        "/api/external/v1/regions",
        headers={"X-API-Key": raw_key},
    )
    assert reset.status_code == 200


def test_external_api_envelope_preserves_governance_and_strips_internal_fields(
    api_client,
    session: Session,
) -> None:
    _seed_market(session)
    headers, user_id = _current_user_id(api_client, "auth0|api_envelope_admin")
    _make_admin(session, user_id)
    client_payload = _create_api_client(
        api_client,
        headers,
        scopes=["region:read", "company_geography:read", "market_signal:read"],
    )
    key_payload = _create_api_key(api_client, headers, client_payload["api_client_id"])

    response = api_client.get(
        "/api/external/v1/regions/greater_boston/intelligence",
        headers={"X-API-Key": key_payload["raw_key"]},
    )

    assert response.status_code == 200
    envelope = response.json()
    assert envelope["data"]["region_id"] == "greater_boston"
    serialized = json.dumps(envelope)
    assert "raw_total_score" not in serialized
    assert "score_ruleset_version" not in serialized
    assert "internal_ruleset_v1" not in serialized
    assert envelope["meta"]["generated_at"]
    assert envelope["meta"]["freshness_status"] in {"fresh", "partial", "unknown"}
    assert envelope["meta"]["confidence"]
    assert envelope["meta"]["coverage_tier"]
    assert envelope["meta"]["source_governance"]
    assert envelope["meta"]["governance_warnings"]
    assert envelope["meta"]["rate_limit"]["limit"] == 60


def test_institution_scoped_external_api_preserves_partner_evidence_and_boundary(
    api_client,
    session: Session,
) -> None:
    _seed_market(session)
    headers, user_id = _current_user_id(api_client, "auth0|api_org_admin")
    _make_admin(session, user_id)
    _seed_org(session, organization_id="org_api_a", user_id=user_id)
    _seed_org(session, organization_id="org_api_b")

    imported = api_client.post(
        "/api/integrations/partner-imports",
        headers=headers,
        json={
            "organization_id": "org_api_a",
            "source_type": "local_employer_list",
            "import_format": "csv",
            "source_attribution": "Career center employer evidence",
            "content": (
                "employer_name,company_id,region,source_attribution\n"
                "Alpha Systems,comp_alpha,Greater Boston,Career center evidence\n"
            ),
        },
    )
    assert imported.status_code == 201
    import_id = imported.json()["data"]["partner_import"]["import_batch_id"]
    accepted = api_client.post(
        f"/api/integrations/partner-imports/{import_id}/accept",
        headers=headers,
        json={"reason": "API dashboard evidence test."},
    )
    assert accepted.status_code == 200

    scoped_client = _create_api_client(
        api_client,
        headers,
        scopes=["institution_dashboard:read"],
        organization_id="org_api_a",
    )
    key_payload = _create_api_key(api_client, headers, scoped_client["api_client_id"])

    dashboard = api_client.get(
        "/api/external/v1/institutions/org_api_a/dashboard",
        headers={"X-API-Key": key_payload["raw_key"]},
    )
    assert dashboard.status_code == 200
    envelope = dashboard.json()
    assert envelope["meta"]["partner_contributed_evidence"]
    assert envelope["meta"]["partner_contributed_evidence"][0]["canonical_truth"] is False
    assert (
        envelope["meta"]["partner_contributed_evidence"][0][
            "product_scoring_override_performed"
        ]
        is False
    )

    cross_org = api_client.get(
        "/api/external/v1/institutions/org_api_b/dashboard",
        headers={"X-API-Key": key_payload["raw_key"]},
    )
    assert cross_org.status_code == 403
    assert cross_org.json()["error"]["code"] == "MISSING_SCOPE"
