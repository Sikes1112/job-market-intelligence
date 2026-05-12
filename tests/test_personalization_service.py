"""End-to-end personalization service tests."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.hiring.models import CompanyRegionHiring
from backend.outputs.repository import OutputMetadataRepository
from backend.personalization.exceptions import MissingRegionForPersonalization
from backend.personalization.payloads import UserPreferences
from backend.personalization.service import PersonalizationService
from backend.personalization.types import CareerStage, PreferenceLevel
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore
from backend.scoring.repository import RegionScoreRepository


def _service(session: Session) -> PersonalizationService:
    return PersonalizationService(
        session=session,
        region_repo=RegionRepository(session),
        score_repo=RegionScoreRepository(session),
    )


def _assert_warning_shape(warning: dict) -> None:
    assert {"warning_code", "severity", "message", "scope_type", "scope_ref"}.issubset(
        warning
    )
    assert isinstance(warning["warning_code"], str)
    assert warning["severity"] in {"low", "medium", "high", "critical"}
    assert isinstance(warning["message"], str)
    assert warning["message"]


# --- seed helpers ---------------------------------------------------------


def _seed_region(
    session: Session, *, region_id: str = "greater_boston", display: str = "Greater Boston"
) -> None:
    session.add(
        Region(
            region_id=region_id,
            region_name=region_id,
            display_name=display,
            region_type="greater_region",
        )
    )
    session.flush()


def _seed_company(
    session: Session,
    *,
    company_id: str,
    sector_primary: str | None = "ai",
    sector_secondary: str | None = None,
    is_major_tech: bool = False,
    is_mag7: bool = False,
    prestige_score: float | None = None,
) -> None:
    session.add(
        Company(
            company_id=company_id,
            company_name=company_id,
            normalized_company_name=company_id,
            eligibility_status="eligible",
            sector_primary=sector_primary,
            sector_secondary=sector_secondary,
            is_major_tech=is_major_tech,
            is_mag7=is_mag7,
            prestige_score=prestige_score,
        )
    )
    session.flush()


def _seed_presence(
    session: Session,
    *,
    company_id: str,
    region_id: str = "greater_boston",
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


def _seed_hiring(
    session: Session,
    *,
    company_id: str,
    region_id: str = "greater_boston",
    role_family_summary: dict[str, int] | None = None,
) -> None:
    session.add(
        CompanyRegionHiring(
            hiring_id=f"h_{company_id}_{region_id}",
            company_id=company_id,
            region_id=region_id,
            currently_hiring_flag=True,
            active_posting_count_now=10,
            role_family_summary=role_family_summary,
        )
    )
    session.flush()


def _seed_score(
    session: Session,
    *,
    region_id: str = "greater_boston",
    objective: float = 0.74,
) -> None:
    session.add(
        RegionMarketScore(
            region_score_id=f"rms_{region_id}",
            region_id=region_id,
            objective_opportunity_score=objective,
            score_ruleset_version="marketscore_v1",
        )
    )
    session.flush()


# --- preconditions --------------------------------------------------------


def test_discover_raises_for_unknown_region(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(MissingRegionForPersonalization):
        svc.discover(UserPreferences(region_ids=["ghost"]))


# --- happy path ----------------------------------------------------------


def test_discover_returns_ranked_regions_and_companies(session: Session) -> None:
    _seed_region(session)
    _seed_company(
        session,
        company_id="comp_a",
        sector_primary="ai",
        is_major_tech=True,
    )
    _seed_presence(session, company_id="comp_a")
    _seed_hiring(
        session,
        company_id="comp_a",
        role_family_summary={"product": 5, "ai_cloud_adjacent": 5},
    )
    _seed_score(session)

    svc = _service(session)
    result = svc.discover(
        UserPreferences(
            region_ids=["greater_boston"],
            role_targets=["product"],
            industry_preferences=["ai"],
            prestige_preference=PreferenceLevel.HIGH,
            brand_preference=PreferenceLevel.MEDIUM,
        )
    )
    assert len(result.personalized.ranked_regions) == 1
    region = result.personalized.ranked_regions[0]
    assert region.region_id == "greater_boston"
    # objective score from RegionMarketScore is exposed unchanged
    assert region.objective_opportunity_score == 0.74

    assert len(result.personalized.ranked_companies) == 1
    company = result.personalized.ranked_companies[0]
    assert company.company_id == "comp_a"
    assert 0.0 <= company.personal_company_score <= 1.0
    # All four component scores returned
    assert 0.0 <= company.role_fit <= 1.0
    assert 0.0 <= company.industry_fit <= 1.0
    assert 0.0 <= company.prestige_fit <= 1.0
    assert 0.0 <= company.brand_fit <= 1.0


def test_discover_ranks_higher_role_match_first(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="match", sector_primary="ai")
    _seed_company(session, company_id="other", sector_primary="hardware")
    _seed_presence(session, company_id="match")
    _seed_presence(session, company_id="other")
    _seed_hiring(
        session,
        company_id="match",
        role_family_summary={"product": 10},
    )
    _seed_hiring(
        session,
        company_id="other",
        role_family_summary={"ai_cloud_adjacent": 10},
    )
    _seed_score(session)

    svc = _service(session)
    result = svc.discover(
        UserPreferences(
            region_ids=["greater_boston"],
            role_targets=["product"],
            industry_preferences=["ai"],
        )
    )
    ranked = result.personalized.ranked_companies
    # `match` wins on both role and industry; `other` matches neither.
    assert ranked[0].company_id == "match"
    assert ranked[1].company_id == "other"
    assert ranked[0].personal_company_score > ranked[1].personal_company_score


def test_discover_handles_missing_role_family_with_warning(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a")
    _seed_hiring(session, company_id="comp_a", role_family_summary=None)
    _seed_score(session)

    svc = _service(session)
    result = svc.discover(
        UserPreferences(
            region_ids=["greater_boston"], role_targets=["product"]
        )
    )
    for warning in result.warnings:
        _assert_warning_shape(warning)
    codes = [w["warning_code"] for w in result.warnings]
    assert "missing_role_family_summary" in codes


def test_discover_warns_on_missing_score(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a")
    _seed_hiring(session, company_id="comp_a", role_family_summary={"product": 5})
    # No RegionMarketScore.

    svc = _service(session)
    result = svc.discover(
        UserPreferences(region_ids=["greater_boston"], role_targets=["product"])
    )
    region = result.personalized.ranked_regions[0]
    assert region.objective_opportunity_score is None
    for warning in result.warnings:
        _assert_warning_shape(warning)
    codes = [w["warning_code"] for w in result.warnings]
    assert "region_score_missing" in codes


def test_discover_warns_on_no_present_companies(session: Session) -> None:
    _seed_region(session)
    _seed_score(session)

    svc = _service(session)
    result = svc.discover(UserPreferences(region_ids=["greater_boston"]))
    for warning in result.warnings:
        _assert_warning_shape(warning)
    codes = [w["warning_code"] for w in result.warnings]
    assert "no_present_companies_for_region" in codes
    assert result.personalized.ranked_companies == []


def test_discover_is_deterministic(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a", sector_primary="ai")
    _seed_presence(session, company_id="comp_a")
    _seed_hiring(
        session,
        company_id="comp_a",
        role_family_summary={"product": 5},
    )
    _seed_score(session)

    svc = _service(session)
    prefs = UserPreferences(
        region_ids=["greater_boston"],
        role_targets=["product"],
        industry_preferences=["ai"],
        prestige_preference=PreferenceLevel.MEDIUM,
        brand_preference=PreferenceLevel.LOW,
        career_stage=CareerStage.ENTRY_LEVEL,
    )
    a = svc.discover(prefs)
    b = svc.discover(prefs)
    assert (
        a.personalized.ranked_companies[0].personal_company_score
        == b.personalized.ranked_companies[0].personal_company_score
    )


def test_discover_respects_limit(session: Session) -> None:
    _seed_region(session)
    for i in range(5):
        cid = f"comp_{i}"
        _seed_company(session, company_id=cid, sector_primary="ai")
        _seed_presence(session, company_id=cid)
        _seed_hiring(session, company_id=cid, role_family_summary={"product": i + 1})
    _seed_score(session)

    svc = _service(session)
    result = svc.discover(
        UserPreferences(
            region_ids=["greater_boston"],
            role_targets=["product"],
            limit=2,
        )
    )
    assert len(result.personalized.ranked_companies) == 2


# --- separation of concerns ---------------------------------------------


def test_discover_does_not_mutate_canonical_truth(session: Session) -> None:
    _seed_region(session)
    region = session.get(Region, "greater_boston")
    _seed_company(session, company_id="comp_a", is_major_tech=True)
    company = session.get(Company, "comp_a")
    _seed_presence(session, company_id="comp_a")
    _seed_hiring(session, company_id="comp_a", role_family_summary={"product": 5})
    _seed_score(session, objective=0.74)
    score = session.get(RegionMarketScore, "rms_greater_boston")

    region_version = region.version
    company_version = company.version
    score_version = score.version
    score_objective = score.objective_opportunity_score

    svc = _service(session)
    svc.discover(
        UserPreferences(
            region_ids=["greater_boston"],
            role_targets=["product"],
            industry_preferences=["ai"],
        )
    )

    session.refresh(region)
    session.refresh(company)
    session.refresh(score)
    assert region.version == region_version
    assert company.version == company_version
    assert score.version == score_version
    assert score.objective_opportunity_score == score_objective


def test_discover_does_not_write_output_metadata(session: Session) -> None:
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a")
    _seed_hiring(session, company_id="comp_a", role_family_summary={"product": 5})
    _seed_score(session)

    svc = _service(session)
    svc.discover(UserPreferences(region_ids=["greater_boston"]))
    # OutputMetadata table should remain empty — personalization persists nothing.
    repo = OutputMetadataRepository(session)
    assert repo.list() == []


def test_discover_passes_through_objective_score_unchanged(session: Session) -> None:
    """If personalization secretly recomputed the objective opportunity
    score, this absurd value would not survive the round-trip."""
    _seed_region(session)
    _seed_company(session, company_id="comp_a")
    _seed_presence(session, company_id="comp_a")
    _seed_hiring(session, company_id="comp_a", role_family_summary={"product": 5})
    _seed_score(session, objective=99.0)

    svc = _service(session)
    result = svc.discover(UserPreferences(region_ids=["greater_boston"]))
    assert result.personalized.ranked_regions[0].objective_opportunity_score == 99.0
