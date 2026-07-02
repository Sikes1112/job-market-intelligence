from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore

FRESH_UNTIL = datetime(2099, 1, 1, 12, tzinfo=UTC)


def _seed_policy_region(session: Session, region_id: str = "dashboard_region") -> None:
    session.add(
        Region(
            region_id=region_id,
            region_name=region_id,
            display_name=region_id.replace("_", " ").title(),
            region_type="greater_region",
        )
    )
    session.add(
        RegionMarketScore(
            region_score_id=f"score_{region_id}",
            region_id=region_id,
            objective_opportunity_score=0.72,
            live_market_score=0.70,
            early_career_accessibility_score=0.62,
            score_ruleset_version="marketscore_v1",
        )
    )
    for index, sector in enumerate(["software", "ai", "cloud", "cybersecurity", "fintech"]):
        company_id = f"{region_id}_company_{index}"
        session.add(
            Company(
                company_id=company_id,
                company_name=f"Dashboard Company {index}",
                normalized_company_name=f"dashboard company {index}",
                sector_primary=sector,
                eligibility_status="eligible",
            )
        )
        session.flush()
        session.add(
            CompanyRegionPresence(
                presence_id=f"presence_{region_id}_{index}",
                company_id=company_id,
                region_id=region_id,
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
                presence_confidence="high",
                source_refs=[{"fact_source_link_id": f"p_src_{region_id}_{index}"}],
            )
        )
        session.add(
            CompanyRegionHiring(
                hiring_id=f"hiring_{region_id}_{index}",
                company_id=company_id,
                region_id=region_id,
                currently_hiring_flag=True,
                active_posting_count_now=12 - index,
                posting_count_30d=20 - index,
                hiring_confidence="high",
                freshness_expires_at=FRESH_UNTIL,
                source_refs=[{"fact_source_link_id": f"h_src_{region_id}_{index}"}],
            )
        )
        session.add(
            CompanyRegionEntryLevel(
                entry_level_id=f"entry_{region_id}_{index}",
                company_id=company_id,
                region_id=region_id,
                internship_count=2,
                coop_count=1,
                entry_level_full_time_count=1,
                formal_early_career_program_flag=True,
                entry_level_access_score=0.72,
                entry_level_confidence="high",
                freshness_expires_at=FRESH_UNTIL,
                source_refs=[{"fact_source_link_id": f"e_src_{region_id}_{index}"}],
            )
        )
    session.flush()


def test_workforce_dashboard_api_includes_required_policy_metadata(
    api_client,
    session: Session,
) -> None:
    _seed_policy_region(session)

    response = api_client.get("/policy/regions/dashboard_region/workforce-dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["region_summary"]["region_id"] == "dashboard_region"
    assert "core_metrics" in data
    assert "policy_findings" in data
    assert data["freshness"]["freshness_status"] == "fresh"
    assert data["confidence"]["level"] in {"medium", "high"}
    assert data["source_summary"]["source_count"] > 0
    assert data["public_safe"] is True
    assert body["metadata"]["freshness"]["freshness_status"] == "fresh"
    assert body["metadata"]["confidence"]["level"] in {"medium", "high"}
    assert "source_summary" in body["metadata"]
    assert body["metadata"]["public_safe"] is True


def test_policy_subset_endpoints_return_relevant_metric_groups(
    api_client,
    session: Session,
) -> None:
    _seed_policy_region(session, "subset_region")

    early = api_client.get("/policy/regions/subset_region/early-career-access")
    concentration = api_client.get("/policy/regions/subset_region/employer-concentration")

    assert early.status_code == 200
    assert concentration.status_code == 200
    early_data = early.json()["data"]
    concentration_data = concentration.json()["data"]
    assert "early_career_access_score" in early_data
    assert "internship_pipeline_score" in early_data
    assert "opportunity_concentration_score" not in early_data
    assert "opportunity_concentration_score" in concentration_data
    assert "employer_dependency_score" in concentration_data
    assert "early_career_access_score" not in concentration_data


def test_policy_dashboard_missing_region_returns_404(api_client) -> None:
    response = api_client.get("/policy/regions/ghost/workforce-dashboard")

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["data"] is None
