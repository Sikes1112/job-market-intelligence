from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.institutions.models import Organization, OrganizationMembership
from backend.institutions.roles import OrganizationRole
from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.schemas import MarketSnapshotCreate
from backend.platform_intelligence.snapshots import HistoricalSnapshotService
from backend.presence.models import CompanyRegionPresence
from backend.users.models import SavedMarketArtifact, UserPreferenceProfile


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


def _seed_org(session: Session, organization_id: str) -> None:
    session.add(
        Organization(
            organization_id=organization_id,
            name="Layer 22 Demo University",
            organization_type="career_center",
            status="active",
        )
    )
    session.flush()


def _seed_membership(
    session: Session,
    *,
    organization_id: str,
    user_id: str,
    role: OrganizationRole,
    status: str = "active",
) -> None:
    session.add(
        OrganizationMembership(
            organization_membership_id=(
                f"mem_{organization_id}_{user_id}_{role.value}".replace("|", "_")[:64]
            ),
            organization_id=organization_id,
            user_id=user_id,
            role=role.value,
            status=status,
        )
    )
    session.flush()


def _seed_market_context(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="legacy_hub",
                region_name="Legacy Hub",
                display_name="Legacy Hub",
                region_type="metro",
            ),
            Region(
                region_id="emerging_cloud_hub",
                region_name="Emerging Cloud Hub",
                display_name="Emerging Cloud Hub",
                region_type="metro",
            ),
            Region(
                region_id="cyber_growth_region",
                region_name="Cyber Growth Region",
                display_name="Cyber Growth Region",
                region_type="metro",
            ),
            Company(
                company_id="comp_legacy",
                company_name="Legacy Systems",
                normalized_company_name="legacy systems",
                sector_primary="software",
            ),
            Company(
                company_id="comp_cloud",
                company_name="CloudScale",
                normalized_company_name="cloudscale",
                sector_primary="cloud",
            ),
            Company(
                company_id="comp_cyber",
                company_name="SecureWorks Lab",
                normalized_company_name="secureworks lab",
                sector_primary="cybersecurity",
            ),
            Company(
                company_id="comp_product",
                company_name="ProductWorks",
                normalized_company_name="productworks",
                sector_primary="product",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionHiring(
                hiring_id="hire_legacy",
                company_id="comp_legacy",
                region_id="legacy_hub",
                currently_hiring_flag=True,
                active_posting_count_now=8,
                annualized_trend_signal="decreasing",
                hiring_program_count=1,
                role_family_summary={"software_engineering": 2},
                hiring_confidence="medium",
            ),
            CompanyRegionHiring(
                hiring_id="hire_cloud",
                company_id="comp_cloud",
                region_id="emerging_cloud_hub",
                currently_hiring_flag=True,
                active_posting_count_now=45,
                annualized_trend_signal="increasing",
                hiring_program_count=3,
                role_family_summary={"cloud_infrastructure": 8, "ai_ml": 4},
                hiring_confidence="high",
            ),
            CompanyRegionHiring(
                hiring_id="hire_cyber",
                company_id="comp_cyber",
                region_id="cyber_growth_region",
                currently_hiring_flag=True,
                active_posting_count_now=35,
                annualized_trend_signal="increasing",
                hiring_program_count=2,
                role_family_summary={"security_engineering": 6},
                hiring_confidence="high",
            ),
            CompanyRegionHiring(
                hiring_id="hire_product",
                company_id="comp_product",
                region_id="emerging_cloud_hub",
                currently_hiring_flag=True,
                active_posting_count_now=25,
                annualized_trend_signal="increasing",
                hiring_program_count=2,
                role_family_summary={"product_management": 5},
                hiring_confidence="medium",
            ),
            CompanyRegionEntryLevel(
                entry_level_id="entry_legacy",
                company_id="comp_legacy",
                region_id="legacy_hub",
                internship_count=0,
                coop_count=0,
                entry_level_full_time_count=2,
                formal_early_career_program_flag=False,
                entry_level_access_score=22,
                entry_level_confidence="medium",
            ),
            CompanyRegionEntryLevel(
                entry_level_id="entry_cloud",
                company_id="comp_cloud",
                region_id="emerging_cloud_hub",
                internship_count=12,
                coop_count=3,
                entry_level_full_time_count=15,
                formal_early_career_program_flag=True,
                entry_level_access_score=82,
                entry_level_confidence="high",
            ),
            CompanyRegionEntryLevel(
                entry_level_id="entry_cyber",
                company_id="comp_cyber",
                region_id="cyber_growth_region",
                internship_count=7,
                coop_count=2,
                entry_level_full_time_count=10,
                formal_early_career_program_flag=True,
                entry_level_access_score=76,
                entry_level_confidence="high",
            ),
            CompanyRegionPresence(
                presence_id="presence_legacy",
                company_id="comp_legacy",
                region_id="legacy_hub",
                presence_status="present",
                office_evidence_flag=True,
                operations_evidence_flag=False,
                hiring_evidence_flag=True,
                presence_confidence="medium",
            ),
            CompanyRegionPresence(
                presence_id="presence_cloud",
                company_id="comp_cloud",
                region_id="emerging_cloud_hub",
                presence_status="present",
                office_evidence_flag=True,
                operations_evidence_flag=True,
                hiring_evidence_flag=True,
                presence_confidence="high",
            ),
            CompanyRegionPresence(
                presence_id="presence_cyber",
                company_id="comp_cyber",
                region_id="cyber_growth_region",
                presence_status="present",
                office_evidence_flag=False,
                operations_evidence_flag=True,
                hiring_evidence_flag=True,
                presence_confidence="high",
            ),
        ]
    )
    session.flush()


def _seed_student_inputs(
    session: Session,
    *,
    user_id: str,
    regions: list[str],
    roles: list[str],
    companies: list[str],
) -> None:
    session.add(
        UserPreferenceProfile(
            user_id=user_id,
            role_interests=roles,
            industry_interests=["software"],
            preferred_regions=regions,
        )
    )
    for company_id in companies:
        session.add(
            SavedMarketArtifact(
                saved_artifact_id=f"saved_{user_id}_{company_id}".replace("|", "_")[:64],
                user_id=user_id,
                artifact_type="company",
                artifact_ref=company_id,
                label=None,
                snapshot={"source": "test"},
            )
        )
    session.flush()


def _seed_decision_org(
    api_client,
    session: Session,
    organization_id: str,
    *,
    student_count: int = 5,
) -> dict[str, tuple[dict[str, str], str]]:
    principals = {
        name: _current_user_id(api_client, f"auth0|{organization_id}_{name}")
        for name in ("admin", "advisor", "report", "student", "inactive")
    }
    _seed_org(session, organization_id)
    _seed_membership(
        session,
        organization_id=organization_id,
        user_id=principals["admin"][1],
        role=OrganizationRole.ORG_ADMIN,
    )
    _seed_membership(
        session,
        organization_id=organization_id,
        user_id=principals["advisor"][1],
        role=OrganizationRole.ADVISOR,
    )
    _seed_membership(
        session,
        organization_id=organization_id,
        user_id=principals["report"][1],
        role=OrganizationRole.REPORT_VIEWER,
    )
    _seed_membership(
        session,
        organization_id=organization_id,
        user_id=principals["student"][1],
        role=OrganizationRole.STUDENT,
    )
    _seed_membership(
        session,
        organization_id=organization_id,
        user_id=principals["inactive"][1],
        role=OrganizationRole.ORG_ADMIN,
        status="inactive",
    )
    student_ids = [principals["student"][1]]
    for index in range(2, student_count + 1):
        headers, user_id = _current_user_id(
            api_client,
            f"auth0|{organization_id}_student{index}",
        )
        principals[f"student{index}"] = (headers, user_id)
        _seed_membership(
            session,
            organization_id=organization_id,
            user_id=user_id,
            role=OrganizationRole.STUDENT,
        )
        student_ids.append(user_id)
    for user_id in student_ids:
        _seed_student_inputs(
            session,
            user_id=user_id,
            regions=["legacy_hub"],
            roles=["software_engineering"],
            companies=["comp_legacy"],
        )
    return principals


def _seed_predictive_history(session: Session) -> None:
    service = HistoricalSnapshotService(HistoryRepository(session))
    for idx, value in enumerate((0.35, 0.46, 0.58, 0.70), start=1):
        service.record_market_snapshot(
            MarketSnapshotCreate(
                market_snapshot_id=f"layer22_market_{idx}",
                region_id="emerging_cloud_hub",
                snapshot_date=date(2026, idx, 1),
                overall_score=value,
                entry_level_access_score=0.62 + (idx * 0.04),
                internship_density_score=0.45 + (idx * 0.08),
                ai_opportunity_score=value,
                product_opportunity_score=0.42 + (idx * 0.07),
                hidden_opportunity_score=0.34 + (idx * 0.06),
                confidence_score=0.82,
                coverage_tier="tier_2",
                freshness_state="fresh",
            )
        )


def _endpoint(organization_id: str, suffix: str, *, minimum_group_size: int = 5) -> str:
    return (
        f"/api/institutions/organizations/{organization_id}/{suffix}"
        f"?minimum_group_size={minimum_group_size}"
    )


def test_decision_dashboard_payload_includes_decision_sections_and_privacy_metadata(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_decision_org(api_client, session, "decision_dash_org")

    response = api_client.get(
        _endpoint("decision_dash_org", "decision-dashboard"),
        headers=principals["admin"][0],
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["target_markets"]
    assert data["regional_trends"]
    assert data["program_alignment"]
    assert data["employer_geography"]
    assert data["internship_access"]
    assert data["industry_demand"]
    assert data["recommended_actions"]
    assert data["privacy"]["aggregation_level"] == "mixed_aggregate"
    assert data["privacy"]["student_level_data_exposed"] is False
    assert data["summary"]["what_is_happening"]
    assert data["confidence"]["level"] in {"high", "medium", "low", "insufficient"}
    assert data["provenance"]


def test_decision_dashboard_does_not_expose_individual_student_records(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_decision_org(api_client, session, "decision_private_org")

    response = api_client.get(
        _endpoint("decision_private_org", "decision-dashboard"),
        headers=principals["admin"][0],
    )

    assert response.status_code == 200
    payload_text = json.dumps(response.json()["data"])
    for key, (_headers, user_id) in principals.items():
        if key in {"admin", "advisor", "report", "inactive"}:
            continue
        assert user_id not in payload_text
    assert "saved_artifact_id" not in payload_text
    assert "recommendation_snapshot_id" not in payload_text
    assert "student_user_id" not in payload_text
    assert "application_id" not in payload_text
    assert "student_application" not in payload_text


def test_curriculum_market_mapping_returns_deterministic_structured_outputs(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_decision_org(api_client, session, "curriculum_org")

    first = api_client.get(
        _endpoint("curriculum_org", "curriculum-market-map"),
        headers=principals["advisor"][0],
    )
    second = api_client.get(
        _endpoint("curriculum_org", "curriculum-market-map"),
        headers=principals["advisor"][0],
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_programs = first.json()["data"]["programs"]
    second_programs = second.json()["data"]["programs"]
    assert [row["program_name"] for row in first_programs] == [
        row["program_name"] for row in second_programs
    ]
    computer_science = next(
        row for row in first_programs if row["program_name"] == "Computer Science"
    )
    assert computer_science["relevant_role_families"]
    assert computer_science["strongest_aligned_markets"]
    assert computer_science["skills_with_rising_demand"]
    assert computer_science["employer_relationship_targets"]
    assert computer_science["advising_recommendations"]
    assert computer_science["confidence"]["level"] in {"high", "medium", "low"}


def test_workforce_reports_generate_complete_decision_ready_payloads(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_decision_org(api_client, session, "workforce_report_org")

    response = api_client.get(
        _endpoint(
            "workforce_report_org",
            "workforce-reports/regional_workforce_opportunity",
        ),
        headers=principals["report"][0],
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"]
    assert data["report_type"] == "regional_workforce_opportunity"
    assert data["key_findings"]
    assert data["recommended_actions"]
    assert data["supporting_metrics"]
    assert data["warnings"] is not None
    assert data["confidence"]["score"] >= 0
    assert data["freshness"]
    assert data["provenance"]
    assert "raw individual student" in data["privacy_statement"]
    assert data["privacy"]["student_level_data_exposed"] is False


def test_institutional_benchmarking_detects_market_and_access_gaps(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_decision_org(api_client, session, "benchmark_org")

    response = api_client.get(
        _endpoint("benchmark_org", "benchmarks"),
        headers=principals["admin"][0],
    )

    assert response.status_code == 200
    data = response.json()["data"]
    benchmark = data["benchmarks"][0]
    assert benchmark["benchmark_subject"] == "Student target-market alignment"
    assert benchmark["comparison_market_set"]
    assert benchmark["opportunity_score"] > 0
    assert benchmark["alignment_score"] < 100
    assert benchmark["emerging_region_gap"] > 0
    assert benchmark["employer_access_gap"] > 0
    assert benchmark["internship_access_gap"] > 0
    assert "Outdated-hub gap" in " ".join(benchmark["supporting_rationale"])


def test_forecast_notes_render_from_layer21_history_with_safe_reasoning_trail(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    _seed_predictive_history(session)
    principals = _seed_decision_org(api_client, session, "forecast_org")

    response = api_client.get(
        _endpoint("forecast_org", "decision-dashboard"),
        headers=principals["admin"][0],
    )

    assert response.status_code == 200
    forecast_notes = response.json()["data"]["forecast_notes"]
    assert forecast_notes
    first_note = forecast_notes[0]
    assert "forecast" in first_note["forecast_label"].casefold()
    assert first_note["confidence"]["level"]
    assert first_note["source_basis"]["source_count"] > 0
    assert first_note["historical_depth"]["observation_count"] > 0
    assert first_note["uncertainty"]["bounded"] is True
    assert first_note["reasoning_trail"]
    assert all(isinstance(step, str) for step in first_note["reasoning_trail"])
    assert "guarantee" not in json.dumps(first_note).casefold()


def test_privacy_suppression_metadata_is_consistent_across_layer22_payloads(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_decision_org(api_client, session, "suppression_consistency_org")
    student5_id = principals["student5"][1]
    profile = session.execute(
        select(UserPreferenceProfile).where(UserPreferenceProfile.user_id == student5_id)
    ).scalar_one()
    profile.preferred_regions = ["legacy_hub", "cyber_growth_region"]
    profile.role_interests = ["software_engineering", "secret_role"]
    session.flush()

    endpoints = (
        "decision-dashboard",
        "curriculum-market-map",
        "workforce-reports/regional_workforce_opportunity",
        "benchmarks",
    )
    for suffix in endpoints:
        response = api_client.get(
            _endpoint("suppression_consistency_org", suffix),
            headers=principals["admin"][0],
        )

        assert response.status_code == 200
        privacy = response.json()["data"]["privacy"]
        assert privacy["student_level_data_exposed"] is False
        assert privacy["suppression_applied"] is True
        assert "popular_target_markets" in privacy["suppressed_fields"]
        assert "target_market_low_sample_buckets" in privacy["suppressed_fields"]
        assert "secret_role" not in json.dumps(response.json()["data"])


def test_privacy_safe_aggregation_suppresses_small_cohort_layer22_outputs(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_decision_org(
        api_client,
        session,
        "small_cohort_org",
        student_count=3,
    )

    response = api_client.get(
        _endpoint("small_cohort_org", "decision-dashboard"),
        headers=principals["admin"][0],
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["privacy"]["suppression_applied"] is True
    assert data["privacy"]["minimum_cohort_size"] == 5
    assert data["privacy"]["cohort_size"] == 3
    assert "target_markets" in data["privacy"]["suppressed_fields"]
    assert data["target_markets"][0]["section_key"] == "target_markets_suppressed"


def test_layer22_institutional_permissions_are_enforced_server_side(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_decision_org(api_client, session, "permission_org")

    advisor_dashboard = api_client.get(
        _endpoint("permission_org", "decision-dashboard"),
        headers=principals["advisor"][0],
    )
    report_viewer_report = api_client.get(
        _endpoint(
            "permission_org",
            "workforce-reports/employer_geography",
        ),
        headers=principals["report"][0],
    )
    student_dashboard = api_client.get(
        _endpoint("permission_org", "decision-dashboard"),
        headers=principals["student"][0],
    )
    student_curriculum = api_client.get(
        _endpoint("permission_org", "curriculum-market-map"),
        headers=principals["student"][0],
    )
    student_benchmarks = api_client.get(
        _endpoint("permission_org", "benchmarks"),
        headers=principals["student"][0],
    )
    inactive_dashboard = api_client.get(
        _endpoint("permission_org", "decision-dashboard"),
        headers=principals["inactive"][0],
    )
    student_report = api_client.get(
        _endpoint(
            "permission_org",
            "workforce-reports/employer_geography",
        ),
        headers=principals["student"][0],
    )

    assert advisor_dashboard.status_code == 200
    assert report_viewer_report.status_code == 200
    assert student_dashboard.status_code == 403
    assert student_curriculum.status_code == 403
    assert student_benchmarks.status_code == 403
    assert inactive_dashboard.status_code == 403
    assert student_report.status_code == 403


def test_cross_org_layer22_access_is_denied_for_all_outputs(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    org_a = _seed_decision_org(api_client, session, "cross_org_a")
    _seed_decision_org(api_client, session, "cross_org_b")

    endpoints = (
        "decision-dashboard",
        "curriculum-market-map",
        "workforce-reports/regional_workforce_opportunity",
        "benchmarks",
    )
    for suffix in endpoints:
        response = api_client.get(
            _endpoint("cross_org_b", suffix),
            headers=org_a["advisor"][0],
        )
        assert response.status_code == 403
