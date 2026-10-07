from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.outputs.models import OutputMetadata
from backend.presence.models import CompanyRegionPresence
from backend.provenance.repository import ProvenanceRepository
from backend.provenance.service import (
    FactSourceLinkDefinition,
    ProvenanceService,
    SourceObservationDefinition,
    SourceRefDefinition,
)
from backend.scoring.models import RegionMarketScore
from backend.shared.confidence import Confidence
from backend.shared.provenance import (
    DataOrigin,
    FactBindingType,
    LicenseTermsCategory,
    ObservationStatus,
    SourceType,
)

NOW = datetime.now(UTC).replace(microsecond=0)


def _seed_region(
    session: Session,
    *,
    region_id: str,
    display_name: str | None = None,
    region_type: str = "metro",
) -> Region:
    row = Region(
        region_id=region_id,
        region_name=region_id,
        display_name=display_name or region_id.replace("_", " ").title(),
        region_type=region_type,
        labor_market_group="tech_hub",
    )
    session.add(row)
    session.flush()
    return row


def _seed_company(
    session: Session,
    *,
    company_id: str,
    name: str | None = None,
    sector: str | None = "ai",
    industry: str | None = "cloud",
) -> Company:
    row = Company(
        company_id=company_id,
        company_name=name or company_id.replace("_", " ").title(),
        normalized_company_name=(name or company_id).casefold(),
        sector_primary=sector,
        sector_secondary=industry,
        eligibility_status="eligible",
    )
    session.add(row)
    session.flush()
    return row


def _seed_score(
    session: Session,
    *,
    region_id: str,
    opportunity: float,
) -> RegionMarketScore:
    row = RegionMarketScore(
        region_score_id=f"rms_{region_id}",
        region_id=region_id,
        objective_opportunity_score=opportunity,
        score_ruleset_version="marketscore_v1",
    )
    session.add(row)
    session.flush()
    return row


def _seed_presence(
    session: Session,
    *,
    company_id: str,
    region_id: str,
    status: str = "present",
) -> CompanyRegionPresence:
    row = CompanyRegionPresence(
        presence_id=f"p_{company_id}_{region_id}",
        company_id=company_id,
        region_id=region_id,
        presence_status=status,
        presence_basis="office_plus_hiring",
        office_evidence_flag=True,
        hiring_evidence_flag=True,
    )
    session.add(row)
    session.flush()
    return row


def _seed_hiring(
    session: Session,
    *,
    company_id: str,
    region_id: str,
    current: bool,
    role_family_summary: dict[str, int] | None = None,
    freshness_expires_at: datetime | None = None,
) -> CompanyRegionHiring:
    row = CompanyRegionHiring(
        hiring_id=f"h_{company_id}_{region_id}",
        company_id=company_id,
        region_id=region_id,
        currently_hiring_flag=current,
        active_posting_count_now=3 if current else None,
        role_family_summary=role_family_summary,
        freshness_expires_at=freshness_expires_at,
    )
    session.add(row)
    session.flush()
    return row


def _seed_entry_level(
    session: Session,
    *,
    company_id: str,
    region_id: str,
    access: bool,
    freshness_expires_at: datetime | None = None,
) -> CompanyRegionEntryLevel:
    row = CompanyRegionEntryLevel(
        entry_level_id=f"e_{company_id}_{region_id}",
        company_id=company_id,
        region_id=region_id,
        internship_count=1 if access else None,
        coop_count=None,
        entry_level_full_time_count=None,
        entry_level_access_score=0.8 if access else None,
        freshness_expires_at=freshness_expires_at,
    )
    session.add(row)
    session.flush()
    return row


def _link_fact(
    session: Session,
    *,
    fact_type: FactBindingType,
    fact_id: str,
    link_id: str,
    source_id: str = "source_real",
    data_origin: DataOrigin = DataOrigin.REAL_OBSERVED,
    collected_at: datetime = NOW,
    observation_status: ObservationStatus = ObservationStatus.POSITIVE_OBSERVED,
) -> None:
    service = ProvenanceService(ProvenanceRepository(session))
    service.upsert_source_ref(
        SourceRefDefinition(
            source_id=source_id,
            source_type=SourceType.COMPANY_OFFICIAL,
            source_name=f"{source_id} official source",
            url_or_provider=f"https://example.test/{source_id}",
            collected_at=collected_at,
            observed_at=collected_at,
            license_or_terms_category=LicenseTermsCategory.PUBLIC,
            confidence=Confidence.HIGH,
            data_origin=data_origin,
        )
    )
    observation_id = f"obs_{link_id}"
    service.upsert_observation(
        SourceObservationDefinition(
            observation_id=observation_id,
            source_id=source_id,
            collected_at=collected_at,
            observed_at=collected_at,
            data_origin=data_origin,
            observation_status=observation_status,
            confidence=Confidence.HIGH,
        )
    )
    service.upsert_fact_source_link(
        FactSourceLinkDefinition(
            link_id=link_id,
            observation_id=observation_id,
            fact_type=fact_type,
            fact_id=fact_id,
            data_origin=data_origin,
            observation_status=observation_status,
            confidence=Confidence.HIGH,
        )
    )
    session.flush()


def _seed_region_search_fixture(session: Session) -> None:
    _seed_region(session, region_id="greater_boston", display_name="Greater Boston")
    _seed_region(session, region_id="greater_sf", display_name="Greater SF")
    _seed_region(session, region_id="tri_state", display_name="Tri State", region_type="state")
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a", region_id="greater_boston")
    hiring = _seed_hiring(
        session,
        company_id="comp_a",
        region_id="greater_boston",
        current=True,
        freshness_expires_at=NOW + timedelta(days=7),
    )
    _seed_score(session, region_id="greater_boston", opportunity=0.91)
    _seed_score(session, region_id="greater_sf", opportunity=0.42)
    _link_fact(
        session,
        fact_type=FactBindingType.COMPANY_REGION_HIRING,
        fact_id=hiring.hiring_id,
        link_id="link_real_boston_hiring",
    )
    _link_fact(
        session,
        fact_type=FactBindingType.REGION,
        fact_id="greater_sf",
        link_id="link_demo_sf_region",
        source_id="mvp_demo_seed",
        data_origin=DataOrigin.DEMO_SEED,
    )


def test_regions_search_returns_stable_schema(api_client, session: Session) -> None:
    _seed_region_search_fixture(session)

    response = api_client.get("/regions/search")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["count"] == 3
    row = body["data"]["regions"][0]
    assert set(row) == {
        "region_id",
        "name",
        "region_name",
        "region_type",
        "parent_region_id",
        "labor_market_group",
        "priority_market",
        "opportunity_score",
        "coverage",
        "sector_coverage",
        "freshness",
        "has_real_data",
    }
    assert row["coverage"]["heuristic"] is True
    assert row["coverage"]["coverage_tier"] == row["coverage"]["tier"]
    assert (
        row["coverage"]["coverage_quality_score"]["overall_score"]
        == (row["coverage"]["quality_score"])
    )
    assert row["coverage"]["tier"] in {"tier_1", "tier_2", "tier_3", "tier_4"}
    assert row["priority_market"] is None
    assert set(row["coverage"]["components"]) == {
        "company_coverage",
        "hiring_coverage",
        "entry_level_coverage",
        "freshness",
        "source_diversity",
        "confidence",
    }
    assert row["sector_coverage"] == {}
    assert set(row["freshness"]) == {
        "freshness_status",
        "data_basis",
        "last_collected_at",
        "source_count",
        "low_confidence_warning",
    }


def test_search_routes_are_not_shadowed_by_dynamic_id_routes(api_client) -> None:
    regions = api_client.get("/regions/search")
    companies = api_client.get("/companies/search")

    assert regions.status_code == 200
    assert regions.json()["data"] == {"regions": [], "count": 0}
    assert companies.status_code == 200
    assert companies.json()["data"] == {"companies": [], "count": 0}


def test_regions_search_filters_query_region_type_and_score(api_client, session: Session) -> None:
    _seed_region_search_fixture(session)

    query = api_client.get("/regions/search", params={"query": "boston"}).json()
    region_type = api_client.get("/regions/search", params={"region_type": "state"}).json()
    score = api_client.get("/regions/search", params={"min_opportunity_score": "0.9"}).json()
    boundary_score = api_client.get(
        "/regions/search", params={"min_opportunity_score": "0.91"}
    ).json()

    assert [r["region_id"] for r in query["data"]["regions"]] == ["greater_boston"]
    assert [r["region_id"] for r in region_type["data"]["regions"]] == ["tri_state"]
    assert [r["region_id"] for r in score["data"]["regions"]] == ["greater_boston"]
    assert [r["region_id"] for r in boundary_score["data"]["regions"]] == ["greater_boston"]


def test_regions_search_empty_and_unknown_filters_are_clear(api_client, session: Session) -> None:
    _seed_region_search_fixture(session)

    empty_query = api_client.get("/regions/search", params={"query": ""})
    whitespace_query = api_client.get("/regions/search", params={"query": "  "})
    unknown_region_type = api_client.get(
        "/regions/search", params={"region_type": "not_a_region_type"}
    )
    invalid_freshness = api_client.get(
        "/regions/search", params={"freshness_status": "not_freshness"}
    )

    assert empty_query.status_code == 422
    assert whitespace_query.status_code == 200
    assert whitespace_query.json()["data"]["regions"] == []
    assert unknown_region_type.status_code == 200
    assert unknown_region_type.json()["data"] == {"regions": [], "count": 0}
    assert invalid_freshness.status_code == 422


def test_regions_search_filters_real_data_and_freshness(api_client, session: Session) -> None:
    _seed_region_search_fixture(session)

    real = api_client.get("/regions/search", params={"has_real_data": "true"}).json()
    fresh = api_client.get("/regions/search", params={"freshness_status": "fresh"}).json()
    demo = api_client.get("/regions/search", params={"freshness_status": "seeded_demo"}).json()

    assert [r["region_id"] for r in real["data"]["regions"]] == ["greater_boston"]
    assert [r["region_id"] for r in fresh["data"]["regions"]] == ["greater_boston"]
    assert [r["region_id"] for r in demo["data"]["regions"]] == ["greater_sf"]


def test_regions_search_distinguishes_placeholder_coverage(api_client, session: Session) -> None:
    _seed_region_search_fixture(session)

    body = api_client.get("/regions/search", params={"query": "tri"}).json()
    [row] = body["data"]["regions"]

    assert row["region_id"] == "tri_state"
    assert row["coverage"]["tier"] == "tier_4"
    assert row["coverage"]["should_rank_as_confident_recommendation"] is False


def test_regions_search_does_not_label_seeded_demo_as_real_imported(
    api_client, session: Session
) -> None:
    _seed_region_search_fixture(session)

    body = api_client.get("/regions/search", params={"query": "SF"}).json()
    [row] = body["data"]["regions"]

    assert row["freshness"]["data_basis"] == "seeded_demo"
    assert row["freshness"]["freshness_status"] == "seeded_demo"
    assert row["has_real_data"] is False


def _seed_company_search_fixture(session: Session) -> None:
    _seed_region(session, region_id="greater_boston", display_name="Greater Boston")
    _seed_region(session, region_id="greater_sf", display_name="Greater SF")
    _seed_company(
        session,
        company_id="comp_ai",
        name="AI Platform Co",
        sector="ai",
        industry="cloud",
    )
    _seed_company(
        session,
        company_id="comp_bio",
        name="Biotech Co",
        sector="biotech",
        industry="life_sciences",
    )
    _seed_company(
        session,
        company_id="comp_demo",
        name="Demo Co",
        sector="software",
        industry="demo",
    )
    presence = _seed_presence(
        session,
        company_id="comp_ai",
        region_id="greater_boston",
        status="present",
    )
    hiring = _seed_hiring(
        session,
        company_id="comp_ai",
        region_id="greater_boston",
        current=True,
        role_family_summary={"product": 4, "ai_cloud_adjacent": 2},
        freshness_expires_at=NOW + timedelta(days=7),
    )
    entry = _seed_entry_level(
        session,
        company_id="comp_ai",
        region_id="greater_boston",
        access=True,
        freshness_expires_at=NOW + timedelta(days=90),
    )
    _seed_presence(
        session,
        company_id="comp_bio",
        region_id="greater_sf",
        status="watchlist",
    )
    _seed_hiring(
        session,
        company_id="comp_bio",
        region_id="greater_sf",
        current=False,
        role_family_summary={"research": 1},
    )
    _link_fact(
        session,
        fact_type=FactBindingType.COMPANY_REGION_PRESENCE,
        fact_id=presence.presence_id,
        link_id="link_real_ai_presence",
    )
    _link_fact(
        session,
        fact_type=FactBindingType.COMPANY_REGION_HIRING,
        fact_id=hiring.hiring_id,
        link_id="link_real_ai_hiring",
    )
    _link_fact(
        session,
        fact_type=FactBindingType.COMPANY_REGION_ENTRY_LEVEL,
        fact_id=entry.entry_level_id,
        link_id="link_real_ai_entry",
    )
    _link_fact(
        session,
        fact_type=FactBindingType.COMPANY,
        fact_id="comp_demo",
        link_id="link_demo_company",
        source_id="mvp_demo_seed",
        data_origin=DataOrigin.DEMO_SEED,
    )


def test_companies_search_returns_stable_schema(api_client, session: Session) -> None:
    _seed_company_search_fixture(session)

    response = api_client.get("/companies/search")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["count"] == 3
    row = body["data"]["companies"][0]
    assert set(row) == {
        "company_id",
        "name",
        "sector",
        "industry",
        "role_families",
        "matched_region_ids",
        "matched_region_coverage",
        "current_hiring",
        "has_entry_level_access",
        "presence_status",
        "freshness",
        "has_real_data",
    }
    assert isinstance(row["matched_region_coverage"], dict)
    assert set(row["freshness"]) == {
        "freshness_status",
        "data_basis",
        "last_collected_at",
        "source_count",
        "low_confidence_warning",
    }


def test_companies_search_filters_query_sector_industry_and_role_family(
    api_client, session: Session
) -> None:
    _seed_company_search_fixture(session)

    query = api_client.get("/companies/search", params={"query": "platform"}).json()
    sector = api_client.get("/companies/search", params={"sector": "biotech"}).json()
    industry = api_client.get("/companies/search", params={"industry": "cloud"}).json()
    role = api_client.get("/companies/search", params={"role_family": "product"}).json()

    assert [c["company_id"] for c in query["data"]["companies"]] == ["comp_ai"]
    assert [c["company_id"] for c in sector["data"]["companies"]] == ["comp_bio"]
    assert [c["company_id"] for c in industry["data"]["companies"]] == ["comp_ai"]
    assert [c["company_id"] for c in role["data"]["companies"]] == ["comp_ai"]


def test_companies_search_empty_and_unknown_filters_are_clear(api_client, session: Session) -> None:
    _seed_company_search_fixture(session)

    empty_query = api_client.get("/companies/search", params={"query": ""})
    whitespace_query = api_client.get("/companies/search", params={"query": "  "})
    unknown_region = api_client.get("/companies/search", params={"region_id": "missing_region"})
    unknown_presence = api_client.get(
        "/companies/search", params={"presence_status": "not_a_presence_status"}
    )

    assert empty_query.status_code == 422
    assert whitespace_query.status_code == 200
    assert whitespace_query.json()["data"]["companies"] == []
    assert unknown_region.status_code == 404
    assert unknown_region.json()["error"]["code"] == "NOT_FOUND"
    assert unknown_presence.status_code == 200
    assert unknown_presence.json()["data"] == {"companies": [], "count": 0}


def test_companies_search_filters_region_hiring_entry_level_and_presence(
    api_client, session: Session
) -> None:
    _seed_company_search_fixture(session)

    region = api_client.get("/companies/search", params={"region_id": "greater_boston"}).json()
    hiring = api_client.get("/companies/search", params={"current_hiring": "true"}).json()
    entry = api_client.get("/companies/search", params={"has_entry_level_access": "true"}).json()
    presence = api_client.get("/companies/search", params={"presence_status": "watchlist"}).json()

    assert [c["company_id"] for c in region["data"]["companies"]] == ["comp_ai"]
    assert region["data"]["companies"][0]["matched_region_ids"] == ["greater_boston"]
    assert [c["company_id"] for c in hiring["data"]["companies"]] == ["comp_ai"]
    assert [c["company_id"] for c in entry["data"]["companies"]] == ["comp_ai"]
    assert [c["company_id"] for c in presence["data"]["companies"]] == ["comp_bio"]


def test_companies_search_false_filters_are_deterministic(api_client, session: Session) -> None:
    _seed_company_search_fixture(session)

    not_hiring = api_client.get("/companies/search", params={"current_hiring": "false"}).json()
    no_entry_level = api_client.get(
        "/companies/search", params={"has_entry_level_access": "false"}
    ).json()

    assert [c["company_id"] for c in not_hiring["data"]["companies"]] == [
        "comp_bio",
        "comp_demo",
    ]
    assert [c["company_id"] for c in no_entry_level["data"]["companies"]] == [
        "comp_bio",
        "comp_demo",
    ]


def test_companies_search_includes_freshness_and_real_data_metadata(
    api_client, session: Session
) -> None:
    _seed_company_search_fixture(session)

    body = api_client.get("/companies/search", params={"query": "AI Platform"}).json()
    [row] = body["data"]["companies"]

    assert row["current_hiring"] is True
    assert row["has_entry_level_access"] is True
    assert row["freshness"]["data_basis"] == "real_imported"
    assert row["freshness"]["freshness_status"] == "fresh"
    assert row["freshness"]["source_count"] == 1
    assert row["has_real_data"] is True
    assert "greater_boston" in row["matched_region_coverage"]
    assert row["matched_region_coverage"]["greater_boston"]["heuristic"] is True


def test_companies_search_does_not_derive_from_region_output_metadata(
    api_client, session: Session
) -> None:
    session.add(
        OutputMetadata(
            output_id="out_region_ghost",
            output_type="region_output",
            subject_id="greater_boston",
            source_version_bundle={"company_versions": {"ghost_company": 1}},
        )
    )
    session.flush()

    body = api_client.get("/companies/search", params={"query": "ghost_company"}).json()

    assert body["data"]["companies"] == []
    assert body["data"]["count"] == 0


def test_companies_search_does_not_label_seeded_demo_as_real_imported(
    api_client, session: Session
) -> None:
    _seed_company_search_fixture(session)

    body = api_client.get("/companies/search", params={"query": "Demo Co"}).json()
    [row] = body["data"]["companies"]

    assert row["freshness"]["data_basis"] == "seeded_demo"
    assert row["freshness"]["freshness_status"] == "seeded_demo"
    assert row["has_real_data"] is False


def test_company_geography_returns_canonical_regions_and_freshness(
    api_client, session: Session
) -> None:
    _seed_company_search_fixture(session)

    response = api_client.get("/companies/comp_ai/regions")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["company_id"] == "comp_ai"
    assert body["data"]["company_name"] == "AI Platform Co"
    assert body["data"]["count"] == 1
    [row] = body["data"]["regions"]
    assert set(row) == {
        "region_id",
        "region_name",
        "priority_market",
        "presence_status",
        "current_hiring",
        "has_entry_level_access",
        "coverage",
        "sector_coverage",
        "freshness",
        "has_real_data",
    }
    assert row["region_id"] == "greater_boston"
    assert row["region_name"] == "Greater Boston"
    assert row["priority_market"] is None
    assert row["presence_status"] == "present"
    assert row["current_hiring"] is True
    assert row["has_entry_level_access"] is True
    assert row["coverage"]["heuristic"] is True
    assert row["coverage"]["coverage_tier"] == row["coverage"]["tier"]
    assert row["coverage"]["tier"] in {"tier_1", "tier_2", "tier_3", "tier_4"}
    assert row["sector_coverage"]
    assert {item["coverage_level"] for item in row["sector_coverage"].values()} == {"unknown"}
    assert row["freshness"]["data_basis"] == "real_imported"
    assert row["freshness"]["freshness_status"] == "fresh"
    assert row["freshness"]["source_count"] == 1
    assert row["has_real_data"] is True


def test_company_geography_does_not_label_seeded_demo_as_real_imported(
    api_client, session: Session
) -> None:
    _seed_region(session, region_id="demo_region", display_name="Demo Region")
    _seed_company(session, company_id="demo_company", name="Demo Company")
    presence = _seed_presence(
        session,
        company_id="demo_company",
        region_id="demo_region",
        status="present",
    )
    _link_fact(
        session,
        fact_type=FactBindingType.COMPANY_REGION_PRESENCE,
        fact_id=presence.presence_id,
        link_id="link_demo_company_region",
        source_id="mvp_demo_seed",
        data_origin=DataOrigin.DEMO_SEED,
    )

    body = api_client.get("/companies/demo_company/regions").json()
    [row] = body["data"]["regions"]

    assert row["freshness"]["data_basis"] == "seeded_demo"
    assert row["freshness"]["freshness_status"] == "seeded_demo"
    assert row["has_real_data"] is False


def test_company_geography_preserves_missing_relation_fields(api_client, session: Session) -> None:
    _seed_region(session, region_id="greater_boston", display_name="Greater Boston")
    _seed_company(session, company_id="hiring_only_company", name="Hiring Only Co")
    hiring = _seed_hiring(
        session,
        company_id="hiring_only_company",
        region_id="greater_boston",
        current=True,
        freshness_expires_at=NOW + timedelta(days=7),
    )
    _link_fact(
        session,
        fact_type=FactBindingType.COMPANY_REGION_HIRING,
        fact_id=hiring.hiring_id,
        link_id="link_hiring_only",
    )

    body = api_client.get("/companies/hiring_only_company/regions").json()
    [row] = body["data"]["regions"]

    assert row["region_id"] == "greater_boston"
    assert row["presence_status"] is None
    assert row["current_hiring"] is True
    assert row["has_entry_level_access"] is False
    assert row["freshness"]["data_basis"] == "real_imported"


def test_company_geography_unknown_company_returns_not_found(api_client) -> None:
    response = api_client.get("/companies/missing_company/regions")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_company_geography_does_not_infer_regions_from_output_metadata(
    api_client, session: Session
) -> None:
    _seed_region(session, region_id="greater_boston", display_name="Greater Boston")
    _seed_company(session, company_id="ghost_company", name="Ghost Company")
    session.add(
        OutputMetadata(
            output_id="out_company_ghost",
            output_type="company_output",
            subject_id="ghost_company",
            source_version_bundle={"region_versions": {"greater_boston": 1}},
        )
    )
    session.flush()

    body = api_client.get("/companies/ghost_company/regions").json()

    assert body["data"]["regions"] == []
    assert body["data"]["count"] == 0


def test_region_sources_returns_explicit_source_evidence(api_client, session: Session) -> None:
    _seed_region_search_fixture(session)

    response = api_client.get("/regions/greater_boston/sources")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["subject_type"] == "region"
    assert body["data"]["subject_id"] == "greater_boston"
    assert body["data"]["freshness"]["data_basis"] == "real_imported"
    assert body["data"]["freshness"]["freshness_status"] == "fresh"
    assert body["data"]["freshness"]["source_count"] == 1
    assert len(body["data"]["sources"]) == 1
    [source] = body["data"]["sources"]
    assert set(source) == {
        "source_id",
        "source_type",
        "source_name",
        "url",
        "collected_at",
        "freshness_status",
        "data_basis",
    }
    assert source["source_id"] == "source_real"
    assert source["data_basis"] == "real_imported"


def test_region_sources_without_source_records_are_honest(api_client, session: Session) -> None:
    _seed_region(session, region_id="unverified_region", display_name="Unverified")

    response = api_client.get("/regions/unverified_region/sources")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["freshness"]["data_basis"] == "unknown"
    assert body["data"]["freshness"]["freshness_status"] == "unknown"
    assert body["data"]["freshness"]["source_count"] == 0
    assert body["data"]["sources"] == []
    assert body["data"]["warnings"] == ["Source evidence is unknown or incomplete."]


def test_region_sources_label_seeded_demo_not_real_imported(api_client, session: Session) -> None:
    _seed_region_search_fixture(session)

    body = api_client.get("/regions/greater_sf/sources").json()

    assert body["data"]["freshness"]["data_basis"] == "seeded_demo"
    assert body["data"]["freshness"]["freshness_status"] == "seeded_demo"
    assert body["data"]["sources"][0]["data_basis"] == "seeded_demo"


def test_region_sources_unknown_region_returns_not_found(api_client) -> None:
    response = api_client.get("/regions/missing_region/sources")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_company_sources_returns_explicit_source_evidence(api_client, session: Session) -> None:
    _seed_company_search_fixture(session)

    response = api_client.get("/companies/comp_ai/sources")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["subject_type"] == "company"
    assert body["data"]["subject_id"] == "comp_ai"
    assert body["data"]["freshness"]["data_basis"] == "real_imported"
    assert body["data"]["freshness"]["freshness_status"] == "fresh"
    assert body["data"]["freshness"]["source_count"] == 1
    assert len(body["data"]["sources"]) == 1
    assert body["data"]["sources"][0]["source_id"] == "source_real"
    assert body["data"]["sources"][0]["data_basis"] == "real_imported"


def test_company_sources_without_source_records_are_honest(api_client, session: Session) -> None:
    _seed_company(session, company_id="unverified_company", name="Unverified Co")

    response = api_client.get("/companies/unverified_company/sources")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["freshness"]["data_basis"] == "unknown"
    assert body["data"]["freshness"]["freshness_status"] == "unknown"
    assert body["data"]["freshness"]["source_count"] == 0
    assert body["data"]["sources"] == []
    assert body["data"]["warnings"] == ["Source evidence is unknown or incomplete."]


def test_company_sources_label_seeded_demo_not_real_imported(api_client, session: Session) -> None:
    _seed_company_search_fixture(session)

    body = api_client.get("/companies/comp_demo/sources").json()

    assert body["data"]["freshness"]["data_basis"] == "seeded_demo"
    assert body["data"]["freshness"]["freshness_status"] == "seeded_demo"
    assert body["data"]["sources"][0]["data_basis"] == "seeded_demo"


def test_company_sources_unknown_company_returns_not_found(api_client) -> None:
    response = api_client.get("/companies/missing_company/sources")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
