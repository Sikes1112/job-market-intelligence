"""Slice 12 read-layer tests.

The ``api_client`` fixture (from ``conftest.py``) shares the in-memory
SQLite session with the test, so seeding through model classes is
immediately visible to the FastAPI routes.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.outputs.models import OutputMetadata
from backend.outputs.repository import OutputMetadataRepository
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore

# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_region(
    session: Session,
    *,
    region_id: str = "greater_boston",
    display_name: str | None = None,
) -> None:
    session.add(
        Region(
            region_id=region_id,
            region_name=region_id,
            display_name=display_name or region_id.replace("_", " ").title(),
            region_type="greater_region",
        )
    )
    session.flush()


def _seed_company(session: Session, *, company_id: str = "comp_a") -> None:
    session.add(
        Company(
            company_id=company_id,
            company_name=company_id,
            normalized_company_name=company_id,
            eligibility_status="eligible",
        )
    )
    session.flush()


def _seed_presence(
    session: Session, *, company_id: str, region_id: str
) -> None:
    session.add(
        CompanyRegionPresence(
            presence_id=f"p_{company_id}_{region_id}",
            company_id=company_id,
            region_id=region_id,
            presence_status="present",
            presence_basis="office_plus_hiring",
            office_evidence_flag=True,
            hiring_evidence_flag=True,
        )
    )
    session.flush()


def _seed_entry_level(
    session: Session,
    *,
    company_id: str,
    region_id: str,
) -> None:
    session.add(
        CompanyRegionEntryLevel(
            entry_level_id=f"e_{company_id}_{region_id}",
            company_id=company_id,
            region_id=region_id,
            internship_count=2,
            coop_count=1,
            entry_level_full_time_count=3,
            entry_level_access_score=0.7,
        )
    )
    session.flush()


def _seed_score(
    session: Session,
    *,
    region_id: str,
    objective: float = 0.74,
    early_career: float = 0.79,
) -> None:
    session.add(
        RegionMarketScore(
            region_score_id=f"rms_{region_id}",
            region_id=region_id,
            objective_opportunity_score=objective,
            early_career_accessibility_score=early_career,
            score_ruleset_version="marketscore_v1",
        )
    )
    session.flush()


# ---------------------------------------------------------------------------
# /health (carry-over)
# ---------------------------------------------------------------------------


def test_health_endpoint_is_liveness_only(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "jmi-backend"
    assert "checks" not in body


def test_health_still_works_through_api_client(api_client) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /regions
# ---------------------------------------------------------------------------


def test_get_regions_returns_lightweight_list(api_client, session) -> None:
    _seed_region(session, region_id="greater_boston", display_name="Greater Boston")
    _seed_region(session, region_id="greater_sf", display_name="Greater SF")
    response = api_client.get("/regions")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    region_ids = [r["region_id"] for r in body["data"]["regions"]]
    assert set(region_ids) == {"greater_boston", "greater_sf"}
    assert body["error"] is None


def test_get_regions_returns_empty_list_when_no_regions(api_client) -> None:
    response = api_client.get("/regions")
    assert response.status_code == 200
    assert response.json()["data"]["regions"] == []


def test_get_regions_does_not_compute_full_outputs(api_client, session) -> None:
    """The lightweight list must not include score sections — those are
    Slice 11 territory and should only appear in /regions/{id}."""
    _seed_region(session, region_id="greater_boston")
    response = api_client.get("/regions")
    entry = response.json()["data"]["regions"][0]
    assert "scores" not in entry
    assert "top_companies_present" not in entry


# ---------------------------------------------------------------------------
# GET /regions/{region_id}
# ---------------------------------------------------------------------------


def test_get_region_returns_assembled_payload(api_client, session) -> None:
    _seed_region(session, region_id="greater_boston", display_name="Greater Boston")
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    _seed_entry_level(session, company_id="comp_a", region_id="greater_boston")
    _seed_score(session, region_id="greater_boston")

    response = api_client.get("/regions/greater_boston")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["region_id"] == "greater_boston"
    assert body["data"]["display_name"] == "Greater Boston"
    # Stored Slice 10 score values pass through Slice 11 unchanged.
    assert body["data"]["scores"]["objective_opportunity_score"] == 0.74
    assert body["data"]["scores"]["early_career_accessibility_score"] == 0.79
    assert body["metadata"]["state"] == "fresh"
    assert body["error"] is None


def test_get_region_missing_returns_404_not_found_envelope(api_client) -> None:
    response = api_client.get("/regions/ghost")
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "NOT_FOUND"
    assert "ghost" in body["error"]["message"]
    assert body["data"] is None


def test_get_region_partial_when_score_missing(api_client, session) -> None:
    _seed_region(session, region_id="greater_boston")
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    # No RegionMarketScore.

    response = api_client.get("/regions/greater_boston")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["metadata"]["state"] == "partial"
    codes = [w["warning_code"] for w in body["metadata"]["warnings"]]
    assert "region_score_missing" in codes


def test_get_region_includes_freshness_metadata(api_client, session) -> None:
    _seed_region(session, region_id="greater_boston")
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    _seed_score(session, region_id="greater_boston")

    response = api_client.get("/regions/greater_boston")
    body = response.json()
    assert "freshness" in body["metadata"]
    freshness = body["metadata"]["freshness"]
    assert "is_stale" in freshness
    assert "freshness_expires_at" in freshness
    assert freshness["freshness_expires_at"] is None
    assert freshness["is_stale"] is False
    assert freshness["freshness_status"] == "unknown"


# ---------------------------------------------------------------------------
# GET /companies/{company_id}
# ---------------------------------------------------------------------------


def test_get_company_returns_assembled_payload(api_client, session) -> None:
    _seed_region(session, region_id="greater_boston")
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")

    response = api_client.get("/companies/comp_a")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["company_id"] == "comp_a"
    assert {r["region_id"] for r in body["data"]["regions_present"]} == {
        "greater_boston"
    }


def test_get_company_missing_returns_404(api_client) -> None:
    response = api_client.get("/companies/ghost")
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "NOT_FOUND"


def test_get_company_with_no_presence_is_partial(api_client, session) -> None:
    _seed_company(session, company_id="comp_a")
    response = api_client.get("/companies/comp_a")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    codes = [w["warning_code"] for w in body["metadata"]["warnings"]]
    assert "no_presence_for_company" in codes


# ---------------------------------------------------------------------------
# GET /compare
# ---------------------------------------------------------------------------


def test_get_compare_returns_comparison_payload(api_client, session) -> None:
    _seed_region(session, region_id="greater_boston", display_name="Greater Boston")
    _seed_region(session, region_id="greater_sf", display_name="Greater SF")
    _seed_score(session, region_id="greater_boston", objective=0.74)
    _seed_score(session, region_id="greater_sf", objective=0.70)

    response = api_client.get(
        "/compare", params={"region_a": "greater_boston", "region_b": "greater_sf"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["comparison_id"] == "greater_boston__greater_sf"
    winners = body["data"]["category_winners"]
    assert winners["objective_opportunity_score"] == "greater_boston"


def test_get_compare_uses_canonical_subject_id(api_client, session) -> None:
    _seed_region(session, region_id="greater_boston")
    _seed_region(session, region_id="greater_sf")
    _seed_score(session, region_id="greater_boston")
    _seed_score(session, region_id="greater_sf")

    a = api_client.get(
        "/compare", params={"region_a": "greater_boston", "region_b": "greater_sf"}
    ).json()
    b = api_client.get(
        "/compare", params={"region_a": "greater_sf", "region_b": "greater_boston"}
    ).json()
    assert a["data"]["comparison_id"] == b["data"]["comparison_id"]
    assert a["data"]["comparison_id"] == "greater_boston__greater_sf"


def test_get_compare_requires_both_params(api_client) -> None:
    response = api_client.get("/compare", params={"region_a": "greater_boston"})
    # FastAPI returns 422 for missing required query params.
    assert response.status_code == 422


def test_get_compare_rejects_identical_regions(api_client, session) -> None:
    _seed_region(session, region_id="greater_boston")
    response = api_client.get(
        "/compare",
        params={"region_a": "greater_boston", "region_b": "greater_boston"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_get_compare_missing_region_returns_404(api_client, session) -> None:
    _seed_region(session, region_id="greater_boston")
    response = api_client.get(
        "/compare", params={"region_a": "greater_boston", "region_b": "ghost"}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"


def test_get_compare_partial_when_one_score_missing(api_client, session) -> None:
    _seed_region(session, region_id="greater_boston")
    _seed_region(session, region_id="greater_sf")
    _seed_score(session, region_id="greater_boston")
    # No score for greater_sf.

    response = api_client.get(
        "/compare", params={"region_a": "greater_boston", "region_b": "greater_sf"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    codes = [w["warning_code"] for w in body["metadata"]["warnings"]]
    assert "region_score_missing" in codes
    # Empty winners when one side missing.
    assert body["data"]["category_winners"] == {}


# ---------------------------------------------------------------------------
# Integration: API does not recompute scoring or mutate canonical truth
# ---------------------------------------------------------------------------


def test_api_does_not_mutate_upstream_canonical_truth(api_client, session) -> None:
    region = Region(
        region_id="greater_boston",
        region_name="greater_boston",
        display_name="Greater Boston",
        region_type="greater_region",
    )
    company = Company(
        company_id="comp_a",
        company_name="A",
        normalized_company_name="a",
        eligibility_status="eligible",
    )
    session.add_all([region, company])
    session.flush()
    session.add(
        CompanyRegionPresence(
            presence_id="p_a_boston",
            company_id="comp_a",
            region_id="greater_boston",
            presence_status="present",
            presence_basis="office_plus_hiring",
            office_evidence_flag=True,
            hiring_evidence_flag=True,
        )
    )
    score = RegionMarketScore(
        region_score_id="rms_boston",
        region_id="greater_boston",
        objective_opportunity_score=0.74,
        score_ruleset_version="marketscore_v1",
    )
    session.add(score)
    session.flush()

    region_version_before = region.version
    company_version_before = company.version
    score_version_before = score.version
    score_value_before = score.objective_opportunity_score

    api_client.get("/regions/greater_boston")
    api_client.get("/companies/comp_a")

    session.refresh(region)
    session.refresh(company)
    session.refresh(score)
    assert region.version == region_version_before
    assert company.version == company_version_before
    assert score.version == score_version_before
    assert score.objective_opportunity_score == score_value_before


def test_api_passes_through_stored_score_values_unchanged(
    api_client, session
) -> None:
    """If the API recomputed scores, this absurd value would not survive
    the round-trip."""
    _seed_region(session, region_id="greater_boston")
    session.add(
        RegionMarketScore(
            region_score_id="rms_b",
            region_id="greater_boston",
            objective_opportunity_score=42.0,  # absurd
            score_ruleset_version="marketscore_v1",
        )
    )
    session.flush()
    response = api_client.get("/regions/greater_boston")
    assert (
        response.json()["data"]["scores"]["objective_opportunity_score"] == 42.0
    )


def test_api_get_output_endpoints_do_not_create_output_metadata(
    api_client, session
) -> None:
    """GET output routes assemble payloads in memory and do not populate the
    OutputMetadata cache table."""
    _seed_region(session, region_id="greater_boston")
    _seed_region(session, region_id="greater_sf")
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    _seed_score(session, region_id="greater_boston")
    _seed_score(session, region_id="greater_sf")

    api_client.get("/regions/greater_boston")
    api_client.get("/companies/comp_a")
    api_client.get(
        "/compare", params={"region_a": "greater_boston", "region_b": "greater_sf"}
    )

    repo = OutputMetadataRepository(session)
    assert repo.list() == []


def test_api_get_region_does_not_update_existing_output_metadata(
    api_client, session
) -> None:
    _seed_region(session, region_id="greater_boston")
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    _seed_score(session, region_id="greater_boston")
    row = OutputMetadata(
        output_id="out_region_greater_boston",
        output_type="region_output",
        subject_id="greater_boston",
        artifact_hash="sentinel_hash",
        source_version_bundle={"sentinel": 1},
    )
    session.add(row)
    session.flush()
    version_before = row.version
    state_before = row.state

    response = api_client.get("/regions/greater_boston")
    assert response.status_code == 200

    session.refresh(row)
    assert row.version == version_before
    assert row.state == state_before
    assert row.artifact_hash == "sentinel_hash"
    assert row.source_version_bundle == {"sentinel": 1}
