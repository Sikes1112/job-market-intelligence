from datetime import UTC, datetime

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.outputs.metadata import (
    aggregate_freshness_expires_at,
    aggregate_freshness_from_iterables,
    company_source_version_bundle,
    comparison_source_version_bundle,
    region_source_version_bundle,
)
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore


def test_aggregate_freshness_returns_none_when_all_none() -> None:
    assert aggregate_freshness_expires_at(None, None) is None


def test_aggregate_freshness_returns_minimum_non_null() -> None:
    a = datetime(2026, 5, 7, 10, tzinfo=UTC)
    b = datetime(2026, 5, 7, 8, tzinfo=UTC)
    c = datetime(2026, 5, 7, 12, tzinfo=UTC)
    assert aggregate_freshness_expires_at(a, None, b, c) == b


def test_aggregate_from_iterables_flattens() -> None:
    a = datetime(2026, 5, 7, 10, tzinfo=UTC)
    b = datetime(2026, 5, 7, 8, tzinfo=UTC)
    assert aggregate_freshness_from_iterables([a], [None, b]) == b


# --- region bundle --------------------------------------------------------


def test_region_source_version_bundle_is_deterministic() -> None:
    region = Region(
        region_id="r1",
        region_name="r1",
        display_name="R1",
        region_type="greater_region",
    )
    region.version = 3
    score = RegionMarketScore(region_score_id="s1", region_id="r1")
    score.version = 7
    score.score_ruleset_version = "marketscore_v1"
    company = Company(
        company_id="c1",
        company_name="C1",
        normalized_company_name="c1",
    )
    company.version = 2
    presence = CompanyRegionPresence(
        presence_id="p1",
        company_id="c1",
        region_id="r1",
        presence_status="present",
    )
    presence.version = 1
    hiring = CompanyRegionHiring(
        hiring_id="h1", company_id="c1", region_id="r1"
    )
    hiring.version = 4
    entry = CompanyRegionEntryLevel(
        entry_level_id="e1", company_id="c1", region_id="r1"
    )
    entry.version = 5

    bundle_a = region_source_version_bundle(
        region=region,
        region_market_score=score,
        present_companies=[company],
        presence_rows=[presence],
        hiring_rows=[hiring],
        entry_level_rows=[entry],
    )
    bundle_b = region_source_version_bundle(
        region=region,
        region_market_score=score,
        present_companies=[company],
        presence_rows=[presence],
        hiring_rows=[hiring],
        entry_level_rows=[entry],
    )
    assert bundle_a == bundle_b
    assert bundle_a == {
        "region_version": 3,
        "region_market_score_version": 7,
        "score_ruleset_version": "marketscore_v1",
        "company_versions": {"c1": 2},
        "presence_versions": {"p1": 1},
        "hiring_versions": {"h1": 4},
        "entry_level_versions": {"e1": 5},
    }


def test_region_bundle_handles_missing_score() -> None:
    region = Region(
        region_id="r1",
        region_name="r1",
        display_name="R1",
        region_type="greater_region",
    )
    bundle = region_source_version_bundle(
        region=region,
        region_market_score=None,
        present_companies=[],
        presence_rows=[],
        hiring_rows=[],
        entry_level_rows=[],
    )
    assert bundle["region_market_score_version"] is None
    assert bundle["score_ruleset_version"] is None
    assert bundle["company_versions"] == {}


# --- company bundle -------------------------------------------------------


def test_company_source_version_bundle_captures_versions() -> None:
    company = Company(
        company_id="c1", company_name="C1", normalized_company_name="c1"
    )
    company.version = 9
    region = Region(
        region_id="r1",
        region_name="r1",
        display_name="R1",
        region_type="greater_region",
    )
    region.version = 1
    presence = CompanyRegionPresence(
        presence_id="p1",
        company_id="c1",
        region_id="r1",
        presence_status="present",
    )
    presence.version = 2
    bundle = company_source_version_bundle(
        company=company,
        regions=[region],
        presence_rows=[presence],
        hiring_rows=[],
        entry_level_rows=[],
    )
    assert bundle["company_version"] == 9
    assert bundle["region_versions"] == {"r1": 1}
    assert bundle["presence_versions"] == {"p1": 2}


# --- comparison bundle ---------------------------------------------------


def test_comparison_source_version_bundle_includes_both_sides() -> None:
    region_a = Region(
        region_id="a",
        region_name="a",
        display_name="A",
        region_type="greater_region",
    )
    region_a.version = 1
    region_b = Region(
        region_id="b",
        region_name="b",
        display_name="B",
        region_type="greater_region",
    )
    region_b.version = 2
    score_a = RegionMarketScore(region_score_id="sa", region_id="a")
    score_a.version = 3
    score_a.score_ruleset_version = "marketscore_v1"
    bundle = comparison_source_version_bundle(
        comparison_subject_id="a__b",
        region_a=region_a,
        region_b=region_b,
        score_a=score_a,
        score_b=None,
    )
    assert bundle["comparison_subject_id"] == "a__b"
    assert bundle["region_a"]["region_version"] == 1
    assert bundle["region_a"]["region_market_score_version"] == 3
    assert bundle["region_b"]["region_market_score_version"] is None
