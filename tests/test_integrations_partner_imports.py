from __future__ import annotations

import json

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.institutions.models import Organization, OrganizationMembership
from backend.institutions.roles import OrganizationRole


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


def _seed_org_membership(
    session: Session,
    *,
    organization_id: str,
    user_id: str,
    role: OrganizationRole,
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


def _create_import(
    api_client,
    headers: dict[str, str],
    *,
    organization_id: str,
    source_type: str = "local_employer_list",
    import_format: str = "csv",
    source_attribution: str | None = "Career center partner list 2026",
    content: str,
):
    body = {
        "organization_id": organization_id,
        "source_type": source_type,
        "import_format": import_format,
        "content": content,
        "original_filename": f"partner-import.{import_format}",
    }
    if source_attribution is not None:
        body["source_attribution"] = source_attribution
    return api_client.post("/api/integrations/partner-imports", headers=headers, json=body)


def test_org_admin_can_create_csv_local_employer_import_and_accept(
    api_client,
    session: Session,
) -> None:
    _seed_market(session)
    headers, admin_id = _current_user_id(api_client, "auth0|partner_admin")
    _seed_org_membership(
        session,
        organization_id="org_imports",
        user_id=admin_id,
        role=OrganizationRole.ORG_ADMIN,
    )

    created = _create_import(
        api_client,
        headers,
        organization_id="org_imports",
        content=(
            "employer_name,company_id,region,source_attribution,observed_at\n"
            "Alpha Systems,comp_alpha,Greater Boston,Career center partner list,2026-01-10\n"
            "Beta Labs,,Greater Boston,Career center partner list,2026-01-11\n"
        ),
    )

    assert created.status_code == 201
    partner_import = created.json()["data"]["partner_import"]
    assert partner_import["status"] == "validated"
    assert partner_import["validation_result"]["accepted_record_count"] == 2
    assert partner_import["preview_records"][0]["partner_contributed_evidence"] is True
    assert partner_import["receipt"]["canonical_truth"] is False

    accepted = api_client.post(
        f"/api/integrations/partner-imports/{partner_import['import_batch_id']}/accept",
        headers=headers,
        json={"reason": "Approved as contributed partner evidence."},
    )

    assert accepted.status_code == 200
    accepted_import = accepted.json()["data"]["partner_import"]
    assert accepted_import["status"] == "accepted"
    assert accepted_import["accepted_record_count"] == 2
    assert accepted_import["records"][0]["evidence"]["partner_contributed"] is True
    assert accepted_import["records"][0]["evidence"]["canonical_truth"] is False
    company = session.get(Company, "comp_alpha")
    assert company is not None
    assert company.company_name == "Alpha Systems"


def test_partner_import_permissions_are_institution_scoped(api_client, session: Session) -> None:
    admin_headers, admin_id = _current_user_id(api_client, "auth0|import_admin")
    advisor_headers, advisor_id = _current_user_id(api_client, "auth0|import_advisor")
    student_headers, student_id = _current_user_id(api_client, "auth0|import_student")
    other_headers, other_id = _current_user_id(api_client, "auth0|import_other")
    _seed_org_membership(
        session,
        organization_id="org_a",
        user_id=admin_id,
        role=OrganizationRole.ORG_ADMIN,
    )
    _seed_org_membership(
        session,
        organization_id="org_a",
        user_id=advisor_id,
        role=OrganizationRole.ADVISOR,
    )
    _seed_org_membership(
        session,
        organization_id="org_a",
        user_id=student_id,
        role=OrganizationRole.STUDENT,
    )
    _seed_org_membership(
        session,
        organization_id="org_b",
        user_id=other_id,
        role=OrganizationRole.ORG_ADMIN,
    )

    advisor_created = _create_import(
        api_client,
        advisor_headers,
        organization_id="org_a",
        content="employer_name,region,source_attribution\nAlpha Systems,Boston,Advisor source\n",
    )
    assert advisor_created.status_code == 201
    batch_id = advisor_created.json()["data"]["partner_import"]["import_batch_id"]

    student_create = _create_import(
        api_client,
        student_headers,
        organization_id="org_a",
        content="employer_name,region,source_attribution\nAlpha Systems,Boston,Student source\n",
    )
    assert student_create.status_code == 403

    advisor_accept = api_client.post(
        f"/api/integrations/partner-imports/{batch_id}/accept",
        headers=advisor_headers,
        json={},
    )
    assert advisor_accept.status_code == 403

    outside_read = api_client.get(
        f"/api/integrations/partner-imports/{batch_id}",
        headers=other_headers,
    )
    assert outside_read.status_code == 403

    admin_accept = api_client.post(
        f"/api/integrations/partner-imports/{batch_id}/accept",
        headers=admin_headers,
        json={},
    )
    assert admin_accept.status_code == 200


def test_json_regional_workforce_data_parses_and_validates(
    api_client,
    session: Session,
) -> None:
    _seed_market(session)
    headers, admin_id = _current_user_id(api_client, "auth0|json_workforce")
    _seed_org_membership(
        session,
        organization_id="org_workforce",
        user_id=admin_id,
        role=OrganizationRole.ORG_ADMIN,
    )

    created = _create_import(
        api_client,
        headers,
        organization_id="org_workforce",
        source_type="regional_workforce_data",
        import_format="json",
        content=json.dumps(
            [
                {
                    "region": "Greater Boston",
                    "metric_name": "software_postings",
                    "metric_value": 124,
                    "metric_unit": "posting_count",
                    "observed_at": "2026-03-01",
                    "source_attribution": "Regional workforce board",
                }
            ]
        ),
    )

    assert created.status_code == 201
    result = created.json()["data"]["partner_import"]["validation_result"]
    assert result["status"] == "validated"
    assert result["accepted_record_count"] == 1
    assert result["can_accept"] is True


def test_validation_warnings_cover_missing_fields_duplicates_ambiguity_stale_dates_and_source(
    api_client,
    session: Session,
) -> None:
    headers, admin_id = _current_user_id(api_client, "auth0|warning_import")
    _seed_org_membership(
        session,
        organization_id="org_warnings",
        user_id=admin_id,
        role=OrganizationRole.ORG_ADMIN,
    )

    created = _create_import(
        api_client,
        headers,
        organization_id="org_warnings",
        source_attribution=None,
        content=(
            "employer_name,region,observed_at,extra_category\n"
            "Alpha,Unknown Market,2020-01-01,unsupported\n"
            "Alpha,,2020-01-01,unsupported\n"
        ),
    )

    assert created.status_code == 201
    result = created.json()["data"]["partner_import"]["validation_result"]
    codes = {warning["code"] for warning in result["warnings"]}
    assert {
        "missing_required_field",
        "unsupported_field",
        "duplicate_employer",
        "ambiguous_employer_name",
        "region_normalization_issue",
        "stale_date",
        "missing_source_attribution",
    }.issubset(codes)
    assert result["accepted_record_count"] == 0
    assert result["can_accept"] is False

    rejected_accept = api_client.post(
        f"/api/integrations/partner-imports/"
        f"{created.json()['data']['partner_import']['import_batch_id']}/accept",
        headers=headers,
        json={},
    )
    assert rejected_accept.status_code == 400


def test_student_pii_individual_outcomes_and_sensitive_demographics_are_quarantined(
    api_client,
    session: Session,
) -> None:
    headers, admin_id = _current_user_id(api_client, "auth0|privacy_import")
    _seed_org_membership(
        session,
        organization_id="org_privacy",
        user_id=admin_id,
        role=OrganizationRole.ORG_ADMIN,
    )

    created = _create_import(
        api_client,
        headers,
        organization_id="org_privacy",
        source_type="aggregated_career_center_outcome_data",
        content=(
            "program_or_cohort,graduation_year,outcome_category,aggregate_count,"
            "student_name,email,individual_salary,race,application_status,source_attribution\n"
            "Computer Science,2026,employed,4,Jane Example,jane@example.edu,"
            "90000,protected,applied,Career center aggregate\n"
        ),
    )

    assert created.status_code == 201
    result = created.json()["data"]["partner_import"]["validation_result"]
    codes = {warning["code"] for warning in result["warnings"]}
    assert "student_level_pii" in codes
    assert "individual_outcome_record" in codes
    assert "sensitive_demographic_attribute" in codes
    assert "ats_application_status_semantics" in codes
    assert result["quarantined_record_count"] == 1
    assert result["has_blocking_privacy_issue"] is True


def test_accepted_partner_evidence_is_labeled_in_downstream_exports(
    api_client,
    session: Session,
) -> None:
    _seed_market(session)
    headers, admin_id = _current_user_id(api_client, "auth0|downstream_import")
    _seed_org_membership(
        session,
        organization_id="org_downstream",
        user_id=admin_id,
        role=OrganizationRole.ORG_ADMIN,
    )
    created = _create_import(
        api_client,
        headers,
        organization_id="org_downstream",
        content=(
            "employer_name,company_id,region,source_attribution,observed_at\n"
            "Alpha Systems,comp_alpha,Greater Boston,Career center partner list,2026-01-10\n"
        ),
    )
    batch_id = created.json()["data"]["partner_import"]["import_batch_id"]
    accepted = api_client.post(
        f"/api/integrations/partner-imports/{batch_id}/accept",
        headers=headers,
        json={},
    )
    assert accepted.status_code == 200

    exported = api_client.post(
        "/api/integrations/exports",
        headers=headers,
        json={
            "product_object_type": "institutional_dashboard",
            "product_object_id": "org_downstream",
            "organization_id": "org_downstream",
            "export_format": "prepared_google_sheets",
        },
    )

    assert exported.status_code == 201
    text = json.dumps(exported.json()["data"]["export"])
    assert "partner_contributed_evidence" in text
    assert "Career center partner list" in text
    assert "canonical_truth" in text
    assert "product_scoring_override_performed" in text
    assert "raw_total_score" not in text
    company = session.get(Company, "comp_alpha")
    region = session.get(Region, "greater_boston")
    assert company is not None and company.company_name == "Alpha Systems"
    assert region is not None and region.display_name == "Greater Boston"
