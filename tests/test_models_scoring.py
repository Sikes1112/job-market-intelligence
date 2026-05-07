import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.geography.models import Region
from backend.scoring.models import RegionMarketScore


def _seed_region(session: Session) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.flush()


def test_region_market_score_round_trip(session: Session) -> None:
    _seed_region(session)
    score = RegionMarketScore(
        region_score_id="rms_1",
        region_id="greater_boston",
        structural_ecosystem_score=0.72,
        live_market_score=0.68,
        objective_opportunity_score=0.74,
        raw_total_score=0.71,
        general_density_score=0.76,
        tech_market_density_score=0.73,
        early_career_accessibility_score=0.79,
        score_ruleset_version="marketscore_v6",
        normalization_profile_id="norm_v5",
        source_version_bundle={
            "company_universe": "company_universe_v45",
            "presence": "presence_v33",
            "hiring": "hiring_v71",
            "entry_level": "entry_v29",
        },
    )
    session.add(score)
    session.flush()
    fetched = session.get(RegionMarketScore, "rms_1")
    assert fetched is not None
    assert fetched.objective_opportunity_score == 0.74
    assert fetched.source_version_bundle["hiring"] == "hiring_v71"
    assert fetched.score_ruleset_version == "marketscore_v6"


def test_region_market_score_components_default_to_null(session: Session) -> None:
    """Partial scoring must be representable: missing components stay NULL."""
    _seed_region(session)
    score = RegionMarketScore(region_score_id="rms_2", region_id="greater_boston")
    session.add(score)
    session.flush()
    fetched = session.get(RegionMarketScore, "rms_2")
    assert fetched is not None
    assert fetched.structural_ecosystem_score is None
    assert fetched.objective_opportunity_score is None
    assert fetched.early_career_accessibility_score is None


def test_region_market_score_unique_per_region(session: Session) -> None:
    _seed_region(session)
    session.add(RegionMarketScore(region_score_id="rms_a", region_id="greater_boston"))
    session.flush()
    session.add(RegionMarketScore(region_score_id="rms_b", region_id="greater_boston"))
    with pytest.raises(IntegrityError):
        session.flush()
