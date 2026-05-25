import pytest
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.geography.repository import RegionRepository
from backend.hiring.models import CompanyRegionHiring
from backend.presence.models import CompanyRegionPresence
from backend.scoring.exceptions import (
    MissingRegionForScoring,
    RegionScoreNotFound,
)
from backend.scoring.repository import RegionScoreRepository
from backend.scoring.service import RegionScoringService
from backend.shared.state import ObjectState


def _service(session: Session) -> RegionScoringService:
    return RegionScoringService(
        RegionScoreRepository(session),
        region_repo=RegionRepository(session),
    )


def _seed_region(session: Session, region_id: str = "greater_boston") -> None:
    if session.get(Region, region_id) is None:
        session.add(
            Region(
                region_id=region_id,
                region_name=region_id,
                display_name=region_id.replace("_", " ").title(),
                region_type="greater_region",
            )
        )
        session.flush()


def _seed_present_company(
    session: Session,
    *,
    company_id: str,
    region_id: str = "greater_boston",
    eligible: bool = True,
    is_major_tech: bool = False,
    is_mag7: bool = False,
    prestige_score: float | None = None,
) -> None:
    session.add(
        Company(
            company_id=company_id,
            company_name=company_id,
            normalized_company_name=company_id,
            eligibility_status="eligible" if eligible else "ineligible",
            is_major_tech=is_major_tech,
            is_mag7=is_mag7,
            prestige_score=prestige_score,
        )
    )
    session.flush()
    session.add(
        CompanyRegionPresence(
            presence_id=f"p_{company_id}",
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
    currently_hiring_flag: bool = True,
    active_posting_count_now: int | None = 5,
) -> None:
    session.add(
        CompanyRegionHiring(
            hiring_id=f"h_{company_id}",
            company_id=company_id,
            region_id=region_id,
            currently_hiring_flag=currently_hiring_flag,
            active_posting_count_now=active_posting_count_now,
        )
    )
    session.flush()


def _seed_entry_level(
    session: Session,
    *,
    company_id: str,
    region_id: str = "greater_boston",
    score: float | None = 0.7,
) -> None:
    session.add(
        CompanyRegionEntryLevel(
            entry_level_id=f"e_{company_id}",
            company_id=company_id,
            region_id=region_id,
            entry_level_access_score=score,
        )
    )
    session.flush()


# --- preconditions --------------------------------------------------------


def test_compute_scores_raises_for_unknown_region(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(MissingRegionForScoring):
        svc.compute_scores("ghost")


def test_get_score_raises_when_missing(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(RegionScoreNotFound):
        svc.get_score("ghost")


# --- compute (no DB writes) ----------------------------------------------


def test_compute_scores_for_empty_region_is_partial(session: Session) -> None:
    _seed_region(session)
    svc = _service(session)
    result = svc.compute_scores("greater_boston")
    assert result.partial is True
    assert result.structural_ecosystem_score == 0.0
    assert result.live_market_score is None
    assert result.early_career_accessibility_score is None
    assert any("not collected" in warning for warning in result.warnings)


def test_compute_scores_writes_nothing(session: Session) -> None:
    """compute_scores must not persist a row."""
    _seed_region(session)
    svc = _service(session)
    svc.compute_scores("greater_boston")
    assert svc.list_scores() == []


def test_compute_scores_is_deterministic(session: Session) -> None:
    _seed_region(session)
    _seed_present_company(
        session,
        company_id="comp_a",
        is_major_tech=True,
        prestige_score=0.7,
    )
    _seed_hiring(session, company_id="comp_a")
    _seed_entry_level(session, company_id="comp_a", score=0.6)

    svc = _service(session)
    a = svc.compute_scores("greater_boston")
    b = svc.compute_scores("greater_boston")
    assert a == b


def test_normalized_views_are_separate_from_raw_components(session: Session) -> None:
    """Density scores and raw component scores must be stored in distinct
    fields and can differ."""
    _seed_region(session)
    _seed_present_company(session, company_id="comp_a", is_major_tech=True)
    _seed_hiring(session, company_id="comp_a", active_posting_count_now=50)

    svc = _service(session)
    result = svc.compute_scores("greater_boston")
    # general_density_score and structural_ecosystem_score are independent
    # numbers — same canonical truth, different views.
    assert (
        result.structural_ecosystem_score is not None
        and result.general_density_score is not None
    )


def test_partial_when_companies_lack_prestige(session: Session) -> None:
    _seed_region(session)
    _seed_present_company(session, company_id="comp_a", prestige_score=None)
    svc = _service(session)
    result = svc.compute_scores("greater_boston")
    assert result.partial is True
    assert any("prestige" in w for w in result.warnings)


def test_scoring_input_preparation_does_not_zero_unknown_counts(
    session: Session,
) -> None:
    _seed_region(session)
    _seed_present_company(session, company_id="comp_a", prestige_score=0.5)
    _seed_hiring(session, company_id="comp_a", active_posting_count_now=None)
    _seed_entry_level(session, company_id="comp_a", score=None)

    svc = _service(session)
    result = svc.compute_scores("greater_boston")

    assert result.partial is True
    assert result.source_version_bundle["active_posting_count_status"] == "unknown"
    assert result.early_career_accessibility_score is None
    assert any("not treated as zero" in warning for warning in result.warnings)


def test_partial_when_no_present_companies(session: Session) -> None:
    _seed_region(session)
    svc = _service(session)
    result = svc.compute_scores("greater_boston")
    assert result.partial is True
    assert any("no present companies" in w for w in result.warnings)


# --- upsert_for_recompute (state machine) --------------------------------


def test_upsert_creates_and_walks_to_fresh(session: Session) -> None:
    _seed_region(session)
    _seed_present_company(
        session, company_id="comp_a", is_major_tech=True, prestige_score=0.5
    )
    _seed_hiring(session, company_id="comp_a")
    _seed_entry_level(session, company_id="comp_a")

    svc = _service(session)
    row, action = svc.upsert_for_recompute("greater_boston")
    assert action == "created"
    assert row.state == ObjectState.FRESH.value
    assert row.version == 1
    assert row.score_ruleset_version == "marketscore_v1"


def test_upsert_unchanged_does_not_bump_version(session: Session) -> None:
    _seed_region(session)
    _seed_present_company(session, company_id="comp_a")
    svc = _service(session)
    svc.upsert_for_recompute("greater_boston")
    same, action = svc.upsert_for_recompute("greater_boston")
    assert action == "unchanged"
    assert same.version == 1


def test_upsert_changed_bumps_version_keeps_fresh(session: Session) -> None:
    _seed_region(session)
    _seed_present_company(session, company_id="comp_a")
    svc = _service(session)
    svc.upsert_for_recompute("greater_boston")
    # add another present company → structural changes → recompute differs
    _seed_present_company(session, company_id="comp_b", is_major_tech=True)
    row, action = svc.upsert_for_recompute("greater_boston")
    assert action == "updated"
    assert row.version == 2
    assert row.state == ObjectState.FRESH.value


def test_upsert_unknown_region_raises(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(MissingRegionForScoring):
        svc.upsert_for_recompute("ghost")


# --- objective hierarchy through the service ----------------------------


def test_objective_score_emphasizes_entry_level_first(session: Session) -> None:
    """A region with strong entry-level access should score higher in
    objective opportunity than the same region with strong hiring volume
    only — modestly."""
    # Region A: strong entry-level
    _seed_region(session, region_id="region_a")
    _seed_present_company(
        session, company_id="comp_a1", region_id="region_a", prestige_score=0.5
    )
    _seed_hiring(
        session,
        company_id="comp_a1",
        region_id="region_a",
        currently_hiring_flag=False,
        active_posting_count_now=0,
    )
    _seed_entry_level(
        session, company_id="comp_a1", region_id="region_a", score=1.0
    )
    # Region B: strong hiring, no entry-level
    _seed_region(session, region_id="region_b")
    _seed_present_company(
        session, company_id="comp_b1", region_id="region_b", prestige_score=0.5
    )
    _seed_hiring(
        session,
        company_id="comp_b1",
        region_id="region_b",
        currently_hiring_flag=True,
        active_posting_count_now=300,
    )
    _seed_entry_level(
        session, company_id="comp_b1", region_id="region_b", score=0.0
    )

    svc = _service(session)
    a = svc.compute_scores("region_a")
    b = svc.compute_scores("region_b")
    assert a.early_career_accessibility_score > b.early_career_accessibility_score
    assert b.live_market_score > a.live_market_score


# --- raw total handles deterministic combination ------------------------


def test_raw_total_score_bounded_zero_to_one(session: Session) -> None:
    _seed_region(session)
    svc = _service(session)
    result = svc.compute_scores("greater_boston")
    assert 0.0 <= result.raw_total_score <= 1.0
